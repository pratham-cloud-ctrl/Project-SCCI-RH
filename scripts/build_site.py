from pathlib import Path
import csv,json,math
ROOT=Path(__file__).resolve().parents[1]
def trace(name):
    with (ROOT/'results'/name).open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
    step=max(1,len(rows)//450)
    return [{k:float(v) if math.isfinite(float(v)) else None for k,v in row.items()} for row in rows[::step]]
data={'summary':json.loads((ROOT/'results'/'summary.json').read_text()),
      'motor':trace('motor_example_trace.csv'),'pressure':trace('pressure_example_trace.csv'),
      'fault':trace('pressure_fault_trace.csv')}
template=(ROOT/'site'/'template.html').read_text(encoding='utf-8')
(ROOT/'site'/'index.html').write_text(template.replace('__SCCI_RH_DATA__',json.dumps(data,separators=(',',':'),allow_nan=False)),encoding='utf-8')
print('Self-contained study data embedded in site/index.html.')
