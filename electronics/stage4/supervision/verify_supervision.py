"""Read-only native pin/pad/circuit, export and MCP-revision verification.

--write-receipt intentionally refreshes after native export and visual review.
The sibling study supplies finite analog/event evidence; this does not qualify
an implant, physical fault coverage, zero current or biological effectiveness.
"""
from pathlib import Path
from collections import Counter
import argparse
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--write-receipt', action='store_true')
args = ap.parse_args()
HERE = Path(__file__).resolve().parent
m = json.loads((HERE / 'connectivity.json').read_text(encoding='utf-8'))
parts = {p['ref']: p for p in m['parts']}
assert len(parts) == len(m['parts']) == 478
tree = ET.parse(HERE / 'supervision.xml').getroot()
exported = {p.attrib['ref']: p for p in tree.findall('./components/comp')}
assert set(parts) == set(exported)
nets = {}
for net in tree.findall('./nets/net'):
    for node in net.findall('node'):
        key = node.attrib['ref'], node.attrib['pin']
        assert key not in nets, key
        nets[key] = net.attrib['name']

def pin(ref, number):
    return nets.get((ref, str(number)))

def contract(ref, expected):
    for n, net in expected.items():
        got = pin(ref, n)
        assert got == net if net is not None else got is None or got.startswith('unconnected-'), (ref, n, got, net)

checked = 0
for ref, p in parts.items():
    assert exported[ref].findtext('value') == p['value'], ref
    assert exported[ref].findtext('footprint') == p['footprint'], ref
    path = HERE / 'scci_rh_sup.pretty' / (p['footprint'].split(':')[1] + '.kicad_mod')
    pads = set(re.findall(r'\(pad "([^"]+)"', path.read_text(encoding='utf-8')))
    assert pads == set(p['nets']), (ref, pads, set(p['nets']))
    contract(ref, p['nets'])
    checked += len(p['nets'])
assert checked == 1699
counts = Counter(p['value'] for p in parts.values() if p['kind'] not in ('R', 'C', 'J'))
for value, count in {'TMUX7412FRRPR': 5, 'TPS3700DDCR': 9,
                     'TPS3431SDRBR': 1, 'LTC6993HS6-1#TRPBF': 2,
                     'TLV3202DGKR': 21, 'OPA2192IDGKR': 1,
                     'ISO6742FDWR': 1, 'BAT54WS-7-F': 4}.items():
    assert counts[value] == count, (value, counts[value])
# All eighteen source-protected S pins face the body; D faces canonical router.
for bank in range(5):
    expected = {11: 'VH_24', 2: 'GND', 3: 'GND', 17: 'GND', 10: 'GUARD_FAULT_N'}
    for leg, (s, d, sel) in enumerate(((1, 16, 15), (12, 13, 14), (9, 8, 7), (4, 5, 6))):
        k = bank * 4 + leg
        name = f'STIM{k:02d}' if k < 16 else f'RETURN{k - 16}'
        expected[s] = 'BODY_' + name if k < 18 else 'GND'
        expected[d] = 'ROUTED_' + name if k < 18 else 'GND'
        expected[sel] = 'GLOBAL_GUARD_EN' if k < 18 else 'GND'
    contract(f'U{100 + bank}', expected)
for ref, prefix in (('J100', 'ROUTED_'), ('J101', 'BODY_')):
    contract(ref, {i + 1: prefix + (f'STIM{i:02d}' if i < 16 else f'RETURN{i - 16}') for i in range(18)})
assert parts['R110']['value'] == '1k'
contract('R110', {1: 'SUP_3V3', 2: 'GUARD_FAULT_N'})
# Explicit DRB identity and thermal pad; not a generic longer exposed pad.
wd_fp = HERE / 'scci_rh_sup.pretty' / (parts['U300']['footprint'].split(':')[1] + '.kicad_mod')
assert 'EP1.5x1.75' in wd_fp.name
assert '(pad "9" smd rect (at 0 0) (size 1.5 1.75)' in wd_fp.read_text(encoding='utf-8')
contract('U300', {1: 'SUP_3V3', 2: 'WD_CWD', 3: 'HOST_RAILS_OK', 4: 'GND',
                   5: 'SUP_3V3', 6: 'WDI', 7: 'WD_ENOUT_OK', 8: 'WD_ENOUT_OK', 9: 'GND'})
contract('U301', {1: 'WDI_N', 2: 'WD_ENOUT_OK', 3: None, 4: 'GND',
                   5: 'WD_SEEN', 6: 'WD_SEEN_CLR_N', 7: 'SUP_3V3', 8: 'SUP_3V3'})
for ch in (0, 1):
    q = lambda n: f'CH{ch}_{n}'
    b = 800 + ch
    contract(f'U{b}', {1: q('REQUEST'), 2: 'GND', 3: q('SEC_SET'),
                       4: q('SEC_DIV'), 5: 'SUP_3V3', 6: q('SEC_TIMER')})
    assert parts[f'R{b * 10}']['value'] == '195.4k 0.1%'
    contract(f'U{810 + ch}', {1: q('SEC_N'), 2: q('TIMEOUT_D'), 3: None,
                             4: 'GND', 5: q('TIMEOUT'), 6: 'TIMEOUT_CLR_N', 7: 'SUP_3V3', 8: 'SUP_3V3'})
    contract(f'U{910 + ch}', {1: 'GND', 2: 'GND', 3: None, 4: 'GND',
                             5: q('BLOCK'), 6: q('BLOCK_CLR_N'), 7: q('BLOCK_PRE_N'), 8: 'SUP_3V3'})
    # Correct existing current scale uses 2.048V midpoint, not an invented2.5V.
    contract(f'U{410 + ch}', {1: q('QUIET_HI_OK'), 2: q('I_MON'), 3: 'QUIET_HI',
                             4: 'GND', 5: q('I_MON'), 6: 'QUIET_LO', 7: q('QUIET_LO_OK'), 8: 'SUP_5'})
contract('U900', {1: 'SUP_REARM', 2: 'SAFE_IDLE', 3: None, 4: 'GND', 5: 'SUP_ARMED',
                  6: 'ARM_CLR_N', 7: 'SUP_3V3', 8: 'SUP_3V3'})
# Exact dual opamp terminal sense and isolated C/D reverse-direction pin mapping.
contract('U502', {1: 'CH0_VPAIR', 2: 'CH0_DIFF_N', 3: 'CH0_DIFF_P', 4: 'GND',
                  5: 'CH1_DIFF_P', 6: 'CH1_DIFF_N', 7: 'CH1_VPAIR', 8: 'SUP_5'})
contract('U710', {1: 'SUP_3V3', 2: 'GND', 3: 'GND', 4: 'GND',
                  5: 'AFE_RAIL_OBS_OK', 6: 'AFE_BLANK_OBS_OK', 7: 'SUP_3V3', 8: 'GND',
                  9: 'AFEAGND', 10: 'AFE_3V3', 11: 'AFE_BLANK_LOCAL_OK', 12: 'AFE_RAIL_LOCAL_OK',
                  13: None, 14: None, 15: 'AFEAGND', 16: 'AFE_3V3'})
for k in range(17):
    b = 600 + k
    name = f'REC{k:02d}' if k < 16 else 'REF'
    node = f'AFE_IN{k:02d}_P' if k < 16 else 'AFE_REF'
    contract(f'J{b}', {1: node, 2: 'AFEAGND'})
    contract(f'R{b * 10}', {1: node, 2: name + '_SENSE'})
    contract(f'R{b * 10 + 1}', {1: 'AFE_3V3', 2: name + '_SENSE'})
    assert parts[f'R{b * 10}']['value'] == '10M 0.1%'
    assert parts[f'R{b * 10 + 1}']['value'] == '1M 0.1%'
    contract(f'U{b}', {1: name + '_HI_OK', 2: name + '_SENSE', 3: 'AFE_WIN_HI',
                       4: 'AFEAGND', 5: name + '_SENSE', 6: 'AFE_WIN_LO', 7: name + '_LO_OK', 8: 'AFE_P5'})
for ref in ('U700', 'U701'):
    contract(ref, {2: 'AFEAGND', 5: 'AFE_P5'})
    contract('C' + ref[1:], {1: 'AFE_P5', 2: 'AFEAGND'})
# Primary gate functions bind to actual exported pins, never descriptive equations.
for rec in m['logic_records']:
    kind, ins, out, v, g = rec['kind'], rec['inputs'], rec['output'], rec['supply'], rec['ground']
    if kind == 'inv': expected = {1: None, 2: ins[0], 3: g, 4: out, 5: v}
    elif kind == 'and3': expected = {1: ins[0], 2: g, 3: ins[1], 4: out, 5: v, 6: ins[2]}
    else: expected = {1: ins[0], 2: ins[1], 3: g, 4: out, 5: v}
    contract(rec['ref'], expected)
    contract('C' + rec['ref'][1:], {1: v, 2: g})

with (HERE / 'bom.csv').open(encoding='utf-8', newline='') as f: bom = list(csv.DictReader(f))
assert len(bom) == 478 and {p['reference'] for p in bom} == set(parts)
erc = json.loads((HERE / 'erc.json').read_text(encoding='utf-8'))
assert erc['ignored_checks'] == [] and len(erc['sheets']) == 22
assert not [v for s in erc['sheets'] for v in s['violations']]
assert len(re.findall(rb'/Type\s*/Page(?!s)\b', (HERE / 'supervision.pdf').read_bytes())) == 22
try: from pypdf import PdfReader
except ImportError: pass
else: assert len(PdfReader(HERE / 'supervision.pdf').pages) == 22
assert len(list((HERE / 'svg').glob('*.svg'))) == 22
assert len(list(HERE.glob('*.kicad_sch'))) == 22
for n in range(1, 23): assert (HERE / 'review' / f'page-{n}.png').stat().st_size > 1000
for p in (HERE / 'svg').glob('*.svg'):
    assert all(l == l.rstrip() for l in p.read_text(encoding='utf-8').splitlines())

def digest(path):
    data = path.read_bytes()
    if path.suffix not in ('.png', '.pdf'): data = data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    return hashlib.sha256(data).hexdigest()

visual = json.loads((HERE / 'visual-review.json').read_text(encoding='utf-8'))
assert visual['pages_reviewed'] == list(range(1, 23))
assert visual['pdf_sha256'] == digest(HERE / 'supervision.pdf')
assert set(visual['png_sha256']) == {f'page-{n}.png' for n in range(1, 23)}
assert all(digest(HERE / 'review' / name) == sha for name, sha in visual['png_sha256'].items())
mcp = json.loads((HERE / 'mcp-inspection.json').read_text(encoding='utf-8'))
assert mcp['erc']['total'] == mcp['erc']['errors'] == mcp['erc']['warnings'] == 0
assert mcp['guard_component']['value'] == 'TMUX7412FRRPR'
assert len(mcp['guard_pin_locations']['pins']) == 17
assert len(mcp['watchdog_pin_locations']['pins']) == 9
assert len(mcp['isolator_pin_locations']['pins']) == 16
assert set(mcp['overlaps']) == {p.name for p in HERE.glob('*.kicad_sch')}
assert all(r['overlap_count'] == 0 and not r['bounds_unresolved'] for r in mcp['overlaps'].values())
assert set(mcp['schematic_sha256']) == {p.name for p in HERE.glob('*.kicad_sch')}
assert all(digest(HERE / name) == sha for name, sha in mcp['schematic_sha256'].items()), 'MCP revision must match saved native schematics'
files = sorted(p for p in HERE.rglob('*') if p.is_file() and p.name not in ('verification.json', 'supervision.kicad_prl') and not p.name.endswith('.lck') and '__pycache__' not in p.parts)
receipt = {'schema': 'scci_rh.stage4.supervision.verification.v1', 'date': '2026-10-14',
           'scope': 'Saved native pin/pad/circuit, exports and actual MCP-revision verification; finite analog/control studies are separate',
           'components': 478, 'pin_contracts_compared': checked, 'sheets': 22, 'pdf_pages': 22,
           'erc_violations': 0, 'ignored_erc_checks': [], 'kicad_version': erc['kicad_version'],
           'guard_paths': 18, 'RHD_window_taps': 17, 'native_logic_cells': len(m['logic_records']),
           'checks': ['all478exportedvalues/footprints and1699pinconnections', 'localpadsetsandcustomDRB0008AEP1.5x1.75',
                      'all18body-facingSprotectedpathsaftercanonicalrouter', 'distinctmonitoranddriverEXT_SUPoutputs',
                      'rawrequestsecondarytimersandseparateheartbeat-seenlatch', 'quietcurrent40V/AtransferandphysicalRHDsidevoltagetaps',
                      'exactOPA2192andISO6742C/Dreversepinmaps', 'AFEthresholdbufferspowered5.30Vforstatedoffsetconditions',
                      'allnativegatepinsandlocalbypasses', 'zeroERC/noignoredchecks/22PDFandSVGpages/reviewimages',
                      'realMCPproject/pins/overlaps/ERCboundtofinalsavedrevision'],
           'hash_policy': 'ExactPNG/PDF; otherincludedtext normalizesCRLF/CRtoLF; excludesreceipt/localpreferences/cache',
           'unqualified': m['external_unimplemented'],
           'sha256': {p.relative_to(HERE).as_posix(): digest(p) for p in files}}
if args.write_receipt:
    (HERE / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
else:
    assert json.loads((HERE / 'verification.json').read_text(encoding='utf-8')) == receipt, 'Review intentional edits before refreshing receipt'
print(json.dumps({k: receipt[k] for k in ('components', 'pin_contracts_compared', 'sheets', 'erc_violations', 'guard_paths', 'RHD_window_taps', 'native_logic_cells')}))
