# Mating interfaces and cable planning

The native [mating document](SCCI_RH_mating_interfaces.FCStd) contains **83** actual
housing envelope solids: the **78** internal connectors used by the frozen
electrical harness, plus recording, guarded artificial-load output, protected
supply, isolated companion UART and SWD interfaces. Two rear inserts and five
grommet allocations are passive cable-management geometry.

Each housing follows the full native pin count, actual pin axes and board
placement. Its dimensions use the [Harwin M20-106 family](https://www.harwin.com/products/M20-1060700):
2.54 mm pitch, 14 mm height, 2.50 mm width, and nominal overall length
`2.54 * (positions - 1) + 2.74 mm`. Square 0.95 mm CAD openings surround the
nominal 0.64 mm header pins. The [manufacturer drawing](https://content.harwin.com/asset/b9496f9a-d89f-420f-aea9-abb4534be02f/DRG-00376-Technical-Drawing-Datasheet-M20-106-pdf.pdf)
supports the envelope; detailed spring contacts, plating, crimp tooling, wire
gauge, retention and ratings are not selected/qualified by this simplified CAD.

[contract.json](contract.json) binds **258** original logical wiring rows,
**47** shared branch nodes and **525** unique connector terminals. One physical
terminal must not be interpreted as several independently inserted wires.
Branched nets require an appropriately rated insulated splice arrangement.
HOST, AFE and companion returns remain separate as defined electrically.

The separate [route document](SCCI_RH_harness_routes.FCStd) contains **zero-volume
planning centerlines**. These are unsmoothed fanout/spine paths, with a proposed
5 mm bend allocation and planning lengths allowing 20% service slack plus
30 mm termination allowance, rounded up to 5 mm. The
[length estimates](wire-length-planning.csv) are **not a wire cut list** and
crossing centerlines do not prove a physically packed loom. Bend implementation,
conductor/insulator diameters, shielding, creepage, current/voltage derating and
signal integrity require a later fabrication design.

The [36-port bridge](body-port-bridge.csv) connects preserved Stage 2 function
names to AFE `J30003` and supervision `J50101`. The latter lies **after** the
independent output disconnect guards; mapping the implant concept directly to
raw router `J40007` would bypass that engineering boundary.

Run `plan_harness.py` using ordinary Python after the reference contract is
final, then `build_mating_interfaces.py` using FreeCAD Python. Reapply the saved
display macro after headless generation and rerun the independent inspectors.
