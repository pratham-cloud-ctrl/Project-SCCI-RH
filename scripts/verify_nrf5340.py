"""Independent read-only ELF, source, peripheral and native-interface audit.

Does not execute/emulate target peripherals or import the build/test producers.
--write-report intentionally saves the current audit after reviewing a new build.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'firmware/nrf5340'
REPORT=ROOT/'provenance/stage4-nrf5340-verification.json'


def sha(path, text=False):
    data=path.read_bytes()
    if text:data=data.replace(b'\r\n',b'\n').replace(b'\r',b'\n')
    return hashlib.sha256(data).hexdigest()


def elf_image(path):
    raw=path.read_bytes()
    header=struct.unpack_from('<16sHHIIIIIHHHHHH',raw)
    assert header[0][:7]==b'\x7fELF\x01\x01\x01','32-bit little-endian ELF required'
    assert header[1]==2 and header[2]==40,'ARM executable required'
    assert header[4]&1,'Thumb entry required'
    assert header[11]==40,'ELF32 section header size'
    sections=[struct.unpack_from('<IIIIIIIIII',raw,header[6]+i*40) for i in range(header[12])]
    names=sections[header[13]]
    table=raw[names[4]:names[4]+names[5]]
    def cstr(data,offset):return data[offset:data.index(0,offset)].decode('utf-8')
    allocated=[];functions={}
    for s in sections:
        name=cstr(table,s[0])
        if s[2]&2 and s[5]:allocated.append(dict(name=name,address=s[3],size=s[5],type=s[1],flags=s[2]))
        if s[1]!=2:continue
        strings=sections[s[6]];st=raw[strings[4]:strings[4]+strings[5]]
        assert s[9]==16,'ELF32 symbol entries'
        for off in range(s[4],s[4]+s[5],16):
            n,v,size,info,other,idx=struct.unpack_from('<IIIBBH',raw,off)
            if info&15==2 and size and idx:
                functions[cstr(st,n)]=dict(address=v,size=size)
    ram=[s for s in allocated if 0x20000000<=s['address']<0x20080000]
    flash=[s for s in allocated if s['address']<0x100000]
    assert ram and flash,'application RAM and flash sections present'
    assert all(s['address']+s['size']<=0x20080000 for s in ram),'RAM overflow'
    flash_end=0
    # Physical LOAD addresses include initialized RAM's flash image.
    for i in range(header[10]):
        p=struct.unpack_from('<IIIIIIII',raw,header[5]+i*header[9])
        if p[0]==1 and p[4] and p[3]<0x100000:flash_end=max(flash_end,p[3]+p[4])
    ram_extent=max(s['address']+s['size'] for s in ram)-0x20000000
    return dict(entry=header[4],allocated_sections=allocated,
                RAM_allocated_section_bytes=sum(s['size'] for s in ram),RAM_extent_bytes=ram_extent,
                flash_LOAD_extent_bytes=flash_end,functions=functions)


def audit():
    checks=0
    def check(value,reason):
        nonlocal checks
        checks+=1
        if not value:raise AssertionError(reason)
    receipt=json.loads((ROOT/'provenance/stage4-nrf5340-build.json').read_text())
    check(receipt['status']=='scci_rh_application_cross_compiled_and_linked','successful actual SCCI_RH build')
    check(receipt['board']=='nrf5340dk/nrf5340/cpuapp','application-core target')
    check(not receipt['flashed_or_executed'] and not receipt['hardware_timing_verified'],'evidence bounds')
    source_bindings={}
    for name,h in receipt['source_sha256_lf'].items():
        check(sha(ROOT/name,True)==h,'built source '+name)
        source_bindings[name]=h
    for name,h in receipt['artifact_sha256'].items():
        # Binary artifacts exact; Git normalizes text exports to LF.
        path=ROOT/name
        actual=sha(path,path.suffix not in ('.elf','.bin'))
        exact=sha(path)
        check(h in (actual,exact),'build export '+name)
    image=elf_image(BASE/'artifacts/scci_rh.elf')
    for name in ['main','scci_rh_backend_init','scci_rh_backend_service','scci_rh_backend_stop',
                 'scci_rh_runtime_init','scci_rh_runtime_trip','scci_rh_runtime_sbp','scci_rh_runtime_event',
                 'scci_rh_runtime_rearm','scci_rh_runtime_route_readback','scci_rh_runtime_phase_start']:
        check(name in image['functions'],'linked production function '+name)
    map_text=(BASE/'artifacts/scci_rh.map').read_text()
    ram_region=re.search(r'^RAM\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)',map_text,re.MULTILINE)
    check(ram_region is not None,'actual linker RAM region')
    ram_origin,ram_capacity=[int(v,16) for v in ram_region.groups()]
    check(ram_origin==0x20000000 and ram_capacity<=524288,'application SRAM allocation')
    check(image['RAM_extent_bytes']<=int(.8*ram_capacity),'20 percent actual linker RAM headroom')
    check(0<image['flash_LOAD_extent_bytes']<=1048576,'1 MiB application flash')
    config=(BASE/'artifacts/build.config').read_text()
    for item in ['CONFIG_SOC_NRF5340_CPUAPP=y','CONFIG_UART_INTERRUPT_DRIVEN=y',
                 'CONFIG_NRFX_SPIM=y','CONFIG_FPU=y']:
        check(item in config,'linked Kconfig '+item)
    check('CONFIG_BT=y' not in config,'wired profile does not enable radio')
    cmake=(BASE/'app/CMakeLists.txt').read_text()
    check('../core/scci_rh_runtime.c' in cmake,'production shared core in actual target')
    pins=(BASE/'app/src/scci_rh_pins.h').read_text()
    pin_values={name:int(value) for name,value in re.findall(r'\b(PIN_[A-Z0-9_]+)\s*=\s*(\d+)',pins)}
    check(len(pin_values)==46 and set(pin_values.values())==set(range(2,48)),'46 distinct carrier GPIOs; LF pins retained')
    check([pin_values[k] for k in ['PIN_RAW_SCK','PIN_RAW_MOSI','PIN_RAW_MISO','PIN_RAW_CS']]==[8,9,10,11],'dedicated SPIM4 pins')
    check(pin_values['PIN_UART_TX']==44 and pin_values['PIN_UART_RX']==45,'UARTE0 overlay pins')
    overlay=(BASE/'app/app.overlay').read_text()
    check('NRF_PSEL(UART_TX, 1, 12)' in overlay and 'NRF_PSEL(UART_RX, 1, 13)' in overlay,'actual UART devicetree')
    check('current-speed = <1000000>' in overlay,'UART nominal baud')
    check('&nfct { status = "disabled"; };' in overlay,'NFCT node disabled for GPIO ownership')
    check('&uicr' in overlay and 'nfct-pins-as-gpios;' in overlay,'actual SDK NFC pin protection policy')
    commands=json.loads((BASE/'artifacts/compile-records.json').read_text())
    by_name={Path(c['file'].replace('\\','/')).name:c['command'] for c in commands}
    for name in ['main.c','scci_rh_backend.c','scci_rh_runtime.c','system_nrf5340_application.c']:
        check(name in by_name,'actual compile record '+name)
        check('-mcpu=cortex-m33' in by_name[name] and '-mthumb' in by_name[name],'actual M33 compiler arguments '+name)
    check(re.search(r'-DNRF_CONFIG_NFCT_PINS_AS_GPIOS(?:=1)?(?:\s|$)',by_name['system_nrf5340_application.c']) is not None,'compiled SystemInit UICR GPIO policy')
    with (ROOT/'docs/stage4/nrf5340-pin-map.csv').open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
    csvpins={32*int(r['pin'][1])+int(r['pin'].split('.')[1]) for r in rows}
    check(len(rows)==46 and csvpins==set(pin_values.values()),'documented GPIO coverage')
    manifest={};xml={};endpoint_rows=[]
    for row in rows:
        for endpoint in row['connection'].split(';'):
            package,port=endpoint.split(':',1)
            if package=='carrier':
                check('165' in port,'explicit proposed sideband carrier');continue
            if package not in manifest:
                directory=ROOT/'electronics/stage4'/package
                manifest[package]={p['ref']:p for p in json.loads((directory/'connectivity.json').read_text())['parts']}
                filename={'recording-front-end':'recording_front_end','current-driver':'current_driver','contact-router':'contact_router','monitoring-transport':'monitoring_transport'}[package] if package!='supervision' else 'supervision'
                xml[package]={}
                for net in ET.parse(directory/(filename+'.xml')).getroot().findall('./nets/net'):
                    for node in net.findall('node'):xml[package][node.attrib['ref'],node.attrib['pin']]=net.attrib['name']
            ref,pin=port.split('.')
            net=manifest[package][ref]['nets'][pin]
            check(net is not None and xml[package][ref,pin].lstrip('/')==net,'native endpoint '+endpoint)
            endpoint_rows.append(dict(GPIO=row['pin'],signal=row['signal'],endpoint=endpoint,native_net=net))
    code=(BASE/'app/src/scci_rh_backend.c').read_text()
    for instance in range(1,5):check(f'NRF_SPIM{instance}' in code,'actual SPIM instance '+str(instance))
    check('DT_NODELABEL(uart0)' in code,'UART0 avoids SPI1â€“4 instance sharing')
    check('NRF_TIMER_EVENT_COMPARE2' in code and 'NRF_TIMER_TASK_CAPTURE1' in code,'timer compare/capture wiring')
    check('TASKS_CLR[0]' in code and 'TASKS_CLR[1]' in code and 'nrfx_gppi_ep_attach' in code,'two GPIO hardware cutoff subscriptions')
    check('nrfx_gppi_conn_alloc' in code and 'nrfx_gppi_conn_enable' in code,'shared SDK DPPI allocator avoids UART connection collision')
    test=json.loads((BASE/'runtime-tests.json').read_text())
    for name,h in test['source_sha256_lf'].items():check(sha(BASE/name,True)==h,'tested core binding '+name)
    check(test['compiled_results']['passed'],'compiled production core scenarios')
    paths=[ROOT/'docs/stage4/nrf5340-pin-map.csv',ROOT/'docs/stage4/nrf5340-component-and-peripheral-review.md',
           ROOT/'scripts/verify_nrf5340.py',BASE/'runtime-tests.json']
    source_bindings.update({p.relative_to(ROOT).as_posix():sha(p,True) for p in paths})
    # These are wire/loop lower bounds, not measured execution times or WCET.
    timing=dict(raw_40clock_wire_us=40/16e6*1e6,raw_requested_slot_us=100,
                RHD_19slot_lower_bound_us=19*8,RHD_requested_frame_us=1000,
                sideband_32clock_delay_allocation_us=32*2,
                uninterrupted_RHD_fits_between_raw_slots=False,
                continuous_requested_cadences_proved=False,physical_WCET_or_jitter_measured=False,
                policy='actual aperture brackets and missed-slot/gap counters required; never reconstruct a missed measurement as valid')
    return dict(schema='scci_rh.stage4.nrf5340-independent-verification.v1',date='2026-10-28',original_design_date='2026-10-14',passed=True,checks=checks,
                evidence='independent ELF32 parser, source/export bindings, GPIO/native/XML and peripheral ownership checks; no target execution',
                elf_sha256=sha(BASE/'artifacts/scci_rh.elf'),entry_hex=hex(image['entry']),
                RAM_allocated_section_bytes=image['RAM_allocated_section_bytes'],RAM_extent_bytes=image['RAM_extent_bytes'],
                RAM_physical_capacity_bytes=524288,RAM_linker_capacity_bytes=ram_capacity,
                RAM_20percent_headroom_pass=True,flash_LOAD_extent_bytes=image['flash_LOAD_extent_bytes'],
                compiled_core_tests=test['compiled_results'],GPIO_count=46,native_endpoint_checks=len(endpoint_rows),
                endpoint_bindings=endpoint_rows,timing_review=timing,
                linked_scci_rh_functions={k:v for k,v in sorted(image['functions'].items()) if k.startswith('scci_rh_') or k=='main'},
                source_sha256_lf=source_bindings)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-report',action='store_true');args=parser.parse_args()
    result=audit()
    if args.write_report:REPORT.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    else:
        saved=json.loads(REPORT.read_text())
        if result!=saved:raise AssertionError('audit differs; intentional review/regeneration required')
    print(json.dumps({k:result[k] for k in ['passed','checks','RAM_extent_bytes','flash_LOAD_extent_bytes','GPIO_count','native_endpoint_checks']},sort_keys=True))


if __name__=='__main__':main()
