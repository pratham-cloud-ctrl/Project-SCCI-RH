"""Inventory exact source land patterns and genuine package model dependencies."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT / 'electronics/stage4/integrated-pcb'
KICAD_MODELS = Path(r'E:\project workspace assests\EDA\KiCAD\share\kicad\3dmodels')

def inventory():
    system = json.loads((PKG/'integration/system.json').read_text())
    items = {}
    for c in system['components']:
        key = c['source_package'] + '/' + c['footprint']
        if key in items:
            continue
        lib, name = c['footprint'].split(':', 1)
        path = ROOT/'electronics/stage4'/c['source_package']/(lib+'.pretty')/(name+'.kicad_mod')
        if not path.exists():
            path = PKG/'controller-carrier'/(lib+'.pretty')/(name+'.kicad_mod')
        if not path.exists():
            path = KICAD_MODELS.parent/'footprints'/(lib+'.pretty')/(name+'.kicad_mod')
        text = path.read_text(encoding='utf-8')
        models = re.findall(r'\(model\s+"([^"]+)', text)
        items[key] = {'footprint':c['footprint'], 'source':str(path), 'references':[], 'models':[]}
        for model in models:
            resolved = model.replace('${KICAD10_3DMODEL_DIR}', str(KICAD_MODELS))
            items[key]['models'].append({'reference':model, 'resolved':resolved, 'exists':Path(resolved).exists()})
    for c in system['components']:
        items[c['source_package']+'/'+c['footprint']]['references'].append(c['reference'])
    result = {'schema':'scci_rh.footprint-inventory.v1', 'scope':'Preserved source footprint dependency inventory, including missing original model references. Final populated board model assignments are audited separately in each board routing and export receipt.', 'components':len(system['components']), 'distinct_patterns':len(items), 'items':items}
    (PKG/'layout/footprint-inventory.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'components':result['components'],'patterns':len(items),'missing_models':[(k,len(v['references'])) for k,v in items.items() if not v['models']],'unresolved_models':[(k,m['reference']) for k,v in items.items() for m in v['models'] if not m['exists']]},indent=2))
    return result

if __name__ == '__main__':
    inventory()
