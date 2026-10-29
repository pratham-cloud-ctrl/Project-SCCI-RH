# TPS3431 DRB0008A integrated-board land-pattern correction

The original supervision footprint placed the eight lead-pad centres at
**x = -1.1 mm and +1.1 mm**. That is a geometry error. The integrated populated
board requires **x = -1.4 mm and +1.4 mm**. The correction retains the electrical
pad numbers, nets, 0.65 mm pitch, 0.6 x 0.31 mm lead-pad size and 1.5 x 1.75 mm
exposed-pad copper. It does not require a reduced electrical clearance rule.

## Primary evidence

The [TI TPS3431 datasheet, Rev. A](https://www.ti.com/lit/ds/symlink/tps3431.pdf)
contains package drawing **DRB0008A, 4218875/A 01/2018**. In the example board
layout on PDF page 29, the horizontal 2.8 mm dimension extends between the two
dashed **pad-centre** lines. The drawing therefore specifies two rows centred
at x = +/-1.4 mm. It does not specify a 2.8 mm outer copper span. The eight lead
pads are 0.6 mm long in x and 0.31 mm wide in y, on 0.65 mm pitch. The central
thermal copper is 1.5 x 1.75 mm. The package outline on PDF page 28 is a separate
mechanical drawing; package terminal dimensions must not be substituted for the
board lands.

The saved original source footprint is
`electronics/stage4/supervision/scci_rh_sup.pretty/Texas_DRB0008A_VSON8_3x3_P0.65_EP1.5x1.75.kicad_mod`.
Its pad rows were explicitly read as +/-1.1 mm, its lead-pad size as
0.6 x 0.31 mm and its exposed pad as 1.5 x 1.75 mm. Its body outline is 3 x 3 mm.
That original file remains frozen as historical evidence; the corrected native
footprint is a deliberate override in the new integrated PCB library snapshot.

## Why native DRC caught it

For the old geometry, the inner edge of a lead pad was 1.1 - 0.6/2 = 0.8 mm from
the package centre. The exposed-pad edge was 1.5/2 = 0.75 mm away. The nominal
copper separation was therefore only **0.05 mm**, below the board's ordinary
0.15 mm clearance. This is the reported pad-7/exposed-pad failure; other lead
pads with different nets have the same geometric issue.

For the corrected geometry, the inner edge is 1.4 - 0.6/2 = 1.1 mm, so the
nominal separation is **0.35 mm**. That supports the ordinary board rule without
changing the trace clearance, suppressing a DRC finding or applying a special
pad-to-pad exception. The optional thermal-pad extensions and thermal vias shown
in TI's example are separate thermal/assembly decisions. The digital reference
retains its explicitly documented unqualified stencil and assembly process.

The integrated-board verifier checks actual lead-pad centres and dimensions,
exposed-pad size and electrical identity. A final native DRC must run again after
the corrected pad geometry and affected copper escape traces are saved. The
old DRC report cannot qualify the changed board.
