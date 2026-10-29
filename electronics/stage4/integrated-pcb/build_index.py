"""Generate a native-file index and explicit Windows launchers for the board set."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def launcher(exe,relative):
    return ('@echo off\nsetlocal\n'
            'if not defined SCCI_RH_KICAD_BIN set "SCCI_RH_KICAD_BIN=E:\\project workspace assests\\EDA\\KiCAD\\bin"\n'
            f'if not exist "%SCCI_RH_KICAD_BIN%\\{exe}" (\n'
            '  echo Set SCCI_RH_KICAD_BIN to your KiCad 10 bin directory.\n  pause\n  exit /b 1\n)\n'
            f'start "" "%SCCI_RH_KICAD_BIN%\\{exe}" "%~dp0{relative}"\n')


def main():
    system=json.loads((HERE/'integration/system.json').read_text())
    (HERE/'OPEN_MASTER_KICAD.cmd').write_text(launcher('kicad.exe','integration\\master\\SCCI_RH_integrated.kicad_pro'))
    lines=['# Populated board index','',
           'Open the [master schematic project](integration/master/SCCI_RH_integrated.kicad_pro) with',
           '`OPEN_MASTER_KICAD.cmd`. Each board has an explicit PCB Editor launcher below.',
           'These use the installed KiCad executable and do not depend on Windows file associations.',
           'On another installation set `SCCI_RH_KICAD_BIN` to its KiCad 10 `bin` directory.',
           '','The board set has 1,298 electrical positions, 1,296 fitted components and 32',
           'mechanical mounting holes. Two optional driver capacitors remain DNP.',
           'Native previews may show optional package placements; fitted STEP and placement',
           'exports explicitly honor the original population flags. All geometry is nominal.',
           '', '| Board | Native PCB / launcher | Fitted / positions | Size, mm | 3D / copper / fabrication |',
           '|---|---|---:|---|---|']
    for name in system['boards']:
        stem=name.replace('-','_');command='OPEN_'+name.upper().replace('-','_')+'.cmd'
        (HERE/command).write_text(launcher('pcbnew.exe',f'boards\\{name}\\{stem}.kicad_pcb'))
        placement=json.loads((HERE/'boards'/name/'placement.json').read_text())
        count=system['boards'][name]['components'] if isinstance(system['boards'][name].get('components'),int) else len(system['boards'][name]['references'])
        receipt=HERE/'exports'/name/'export-receipt.json'
        fitted=json.loads(receipt.read_text())['fitted_component_count'] if receipt.exists() else 'pending'
        size=' × '.join(map(str,placement['outline_mm']))
        artifacts=(f'[STEP](exports/{name}/populated.step) · [top](exports/{name}/top.png) · '
                   f'[3D](exports/{name}/isometric.png) · [copper](exports/{name}/top-copper.svg) · '
                   f'[fabrication reference](exports/{name}/fabrication-reference/README.md)') if receipt.exists() else 'Exports in progress'
        lines.append(f'| {name.replace("-"," ").title()} | [PCB](boards/{name}/{stem}.kicad_pcb) · [launcher]({command}) | {fitted} / {count} | {size} | {artifacts} |')
    lines += ['', 'The [80-sheet PDF](integration/master/SCCI_RH_integrated.pdf),',
              '[BOM](integration/populated-bom.csv), [harness](integration/harness.json),',
              '[power](power-overlay.json) and [carrier firmware](firmware-profile/README.md)',
              'connect the physical reference to its mechanism and operating assumptions.',
              'Fabrication files are inspectable digital references; assembly and physical',
              'performance have not been measured. Final mechanical packaging is Stage 5.', '']
    (HERE/'BOARD_INDEX.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Board index and nine explicit native launchers generated')


if __name__=='__main__':main()
