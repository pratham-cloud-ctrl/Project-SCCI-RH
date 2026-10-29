"""Consolidate the exact260 native reference objects into a mechanical BOM."""
from pathlib import Path
import csv,json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
reference=list(csv.DictReader((HERE/'reference/mechanical-bom.csv').open(encoding='utf-8',newline='')))
hc=json.loads((HERE/'harness/contract.json').read_text())
hr=json.loads((HERE/'harness/geometry-receipt.json').read_text())
mates={m['label']:m for m in hc['mates']}
rows=[]
for part in reference:
    rows.append(dict(label=part['label'],category=part['category'],quantity=part['quantity'],
                     material_or_family=part['material_allocation'],
                     source_document='cad/stage5/reference/SCCI_RH_reference_assembly.FCStd',
                     electrical_reference='',qualification='Nominal digital geometry; no physical qualification'))
for part in hr['parts']:
    label=part['label'];mate=mates.get(label)
    rows.append(dict(label=label,category=mate['category'] if mate else 'passive_cable_interface',quantity=1,
                     material_or_family=mate['candidate_family'] if mate else ('Nominal elastomer grommet allocation' if label.startswith('Grommet') else 'Nominal insulating rear insert allocation'),
                     source_document=hc['native'],electrical_reference=f'{mate["board"]}:{mate["pcb_reference"]}' if mate else '',
                     qualification='Nominal envelope; material, ratings, retention and process unqualified'))
assert len(rows)==260 and len({r['label'] for r in rows})==260
combined=json.loads((HERE/'combined-assembly-receipt.json').read_text())
assert {r['label'] for r in rows}=={r['label'] for r in combined['parts']}
with (HERE/'MECHANICAL_BOM.csv').open('w',encoding='utf-8',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print('Consolidated260actualreferenceobjects;electroniccomponentBOMremainsseparate.')
