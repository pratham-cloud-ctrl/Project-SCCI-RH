"""Publish inspectable BOM/source mapping and explicit physical loom endpoints."""
import csv,json
from collections import defaultdict
from build_integration import HERE,ROOT
def main():
    s=json.loads((HERE/'system.json').read_text(encoding='utf-8'))
    fields=['board','reference','value','footprint','datasheet','dnp','source_package','source_ref','source_sheet','pcb_path','master_path','integration_added']
    with (HERE/'populated-bom.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for c in s['components']:
            row={k:c.get(k,'') for k in fields};row['integration_added']=bool(c.get('added'));writer.writerow(row)
    by_ref={c['reference']:c for c in s['components']};connectors={};net_touches=defaultdict(set);wires=[]
    for i,row in enumerate(s['wires'],1):
        wire={'id':f'W{i:03d}','net':row['integrated_net'],'purpose':row['purpose'],'ends':[]}
        for side in ['from','to']:
            board,ref,pin=row[side+'_package'],row[side+'_harness_ref'],row[side+'_harness_pin']
            identity=board+':'+ref;component=by_ref[ref]
            connection=connectors.setdefault(identity,{'board':board,'pcb_reference':ref,'value':component['value'],'PCB_header_footprint':component['footprint'],'pins_used':{},'mate_requirement':'Opposite-gender 2.54 mm header mate matching full native connector pin count; final locking/crimp part and wire gauge unselected.'})
            point=connection['pins_used'].setdefault(pin,{'net':row['integrated_net'],'wire_ids':[]})
            assert point['net']==row['integrated_net']
            point['wire_ids'].append(wire['id']);net_touches[row['integrated_net']].add((board,ref,pin))
            wire['ends'].append({'board':board,'reference':ref,'pin':pin})
        wires.append(wire)
    splices=[]
    for net,points in sorted(net_touches.items()):
        if len(points)>2:
            splices.append({'net':net,'terminals':[{'board':b,'reference':r,'pin':p} for b,r,p in sorted(points)],'construction_requirement':'One electrically continuous harness node with insulated branch/splice connections; duplicated CSV edges are an auditable connectivity plan, not multiple wires forced into one socket.'})
    out={'schema':'scci_rh.integrated-harness.v1','wire_plan_rows':len(wires),'PCB_connector_mates_required':len(connectors),'branch_nodes':len(splices),'connectors':list(connectors.values()),'wires':wires,'splices':splices,'limits':['Digital harness connectivity and mating geometry allocation only','Wire lengths, locking part numbers, crimp/solder process, shielding and current/voltage ratings remain unqualified','Do not connect source circuit output taps directly without their new physical PCB headers','HOST, AFE and companion return domains are distinct; no unlisted ground bridge is permitted']}
    (HERE/'harness.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if isinstance(v,int)}))
if __name__=='__main__':main()
