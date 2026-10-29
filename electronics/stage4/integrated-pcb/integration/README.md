# Integrated native electrical hierarchy

Open [the actual master project](master/SCCI_RH_integrated.kicad_pro) in KiCad or
[the rendered schematic PDF](master/SCCI_RH_integrated.pdf). The master contains eight
functional modules, 1,298 component positions (1,296 fitted, two DNP) and 80 sheets. This is a digital
artificial-load engineering assembly; it is not a physically qualified implant.

- [Design and mechanism](../../../../docs/stage4/integrated-pcb-design.md).
- [Final 258-row wiring table](../../../../docs/stage4/integrated-pcb-wiring.csv).
- [Carrier-only 92-row wiring table](../../../../docs/stage4/integrated-pcb-controller-wiring.csv).
- [Populated BOM and source map](populated-bom.csv).
- [Physical connector mates, wire plan and branch nodes](harness.json).
- [Two intentional legacy rearm corrections and four added tap headers](integration-changes.json).
- [Saved native export and independent verification](verification.json).
- [Actual master netlist](master/SCCI_RH_integrated.xml) and [native ERC report](master/erc.json).

The separate [per-board schematic projects](boards/) provide the layout/netlist
source for each physical board. Original component symbol UUIDs are retained;
global reference offsets and electrical net names are mapped explicitly in
`system.json`. `pcb_path` refers to the per-board project and `master_path` to the
integrated hierarchy. The populated board files and routing evidence live in
the adjacent `../boards/` package, rather than this schematic-copy directory.

The original seven source projects are read-only inputs. Source equal names are
qualified by module; only explicit audited wiring pairs join them. Added tap
headers convert earlier bare-component observations into actual board interfaces.
The earlier driver/supervisor rearm ties are superseded to match the compiled
firmware's separate rearm owners and avoid connecting processor outputs together.

The new supervision library copy also corrects the TPS3431 lead-row centres to
+/-1.4 mm according to the TI DRB0008A land drawing. The old source snapshot had
+/-1.1 mm. See the [primary drawing review](../../../../docs/stage4/tps3431-land-pattern-review.md).
This preserves pad numbers/nets while correcting geometry; no reduced clearance
exception is used and the historical source footprint remains unchanged.

Run the independent audit from the repository root:

```powershell
python electronics/stage4/integrated-pcb/integration/verify_integration.py
```

The build helpers deliberately regenerate only this new integration package.
`build_integration.py` reads the frozen native XML inputs and explicit wiring;
`build_native.py` authors actual editable schematic copies and library tables;
`export_native.py` refreshes native KiCad exports; `write_tables.py` publishes
the component and harness records. They are not invoked by read-only CI.

The native source circuitry includes physical limits and open qualification
work documented in its individual packages. Electrical equivalence does not
erase those limits or establish waveform precision, implant isolation, biological
benefit or a sustained measured firmware rate.
