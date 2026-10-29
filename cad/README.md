# Mechanical design

The current engineering package is [Stage 5 mechanical assembly and packaging](stage5/README.md):
actual eight-board source geometry, a complete native reference assembly,
editable chassis/mounting interfaces, and a separate detailed conditional
future implanted-interface concept. Its [drawing set](stage5/drawings/SCCI_RH_Stage5_Mechanical_Review.pdf)
and explicit launchers are the current entry points.

The [Stage 2 allocation](stage2/SCCI_RH_stage2_allocation.FCStd) and the original
desktop models below remain preserved historical inputs.

## Historical v1.0 subsystem enclosure

The 100 x 70 x 32 mm desktop enclosure makes the digital electronics tangible.
It is distinct from the proposed future implanted interface. It has no claim to
sterility, hermetic sealing, biocompatibility, anatomical fit or implantation.

`build_scci_rh.py` is the authoritative parametric source (millimetres). Install
build123d 0.13 and run `python cad/build_scci_rh.py`. Native STEP solids and STL meshes
are in `exports/`; `geometry-checks.json` records validity, round-trip error and
PCB/base and lid/base overlap. The PCB envelope is 80 x 50 x 1.6 mm, with 3.2 mm
mounting holes at ±30 mm, ±15 mm about its centre. Its bottom is at z=8 mm.

The two-piece shell has a 2 mm floor, 2.5 mm walls, four PCB bosses, four lid
fastener bosses, a status window and instrument cable openings. The boss pilot
holes are illustrative self-tapping screw holes; procurement/fastener torque
and printed-part tolerances have not been tested. Nominal lid rim clearance is
0.5 mm per side. The openings are instrument cable passages, not verified
connector-specific mechanical fits. Cable strain relief remains a fabrication
iteration task.

The separate eight-contact paddle and eight-contact open surface cuff visualize
distinct stimulation and recording lead concepts. Their dimensions, cuff radius
and contact pitch are arbitrary editable parameters, not evidence-based electrode
prescriptions. The cuff is an open 270-degree, 18 mm long cylindrical surface
with nominal 6 mm inner radius. The paddle is 10 x 40 x 0.8 mm. Recording and
stimulation placements are separate hypotheses in the architecture document;
these models do not establish anatomical fit, tissue pressure or chronic access.

Blender sources and images are presentation assets. Engineering dimensions
come from the parametric solid model and KiCad board. Before fabrication,
check tolerances, component envelopes, cable bend radii, thermal conditions,
fasteners, routing clearances and all electrical safety requirements.
