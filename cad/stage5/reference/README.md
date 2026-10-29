# Stage 5 / true-scale modular reference assembly

Open `OPEN_REFERENCE.cmd` for the native FreeCAD assembly. Set `SCCI_RH_FREECAD_EXE` if FreeCAD is installed elsewhere. The launcher uses the installed application explicitly and does not depend on a Windows file association.

- **Native assembly:** `SCCI_RH_reference_assembly.FCStd`, with 170 final parts and 396 editable primitive/boolean construction features.
- **Actual electronics:** all 8 frozen populated boards, 1,296 fitted components, no geometry scaling or envelope substitution.
- **Mechanical-only exchange model:** `SCCI_RH_reference_mechanical.step`.
- **Full populated exchange model:** `SCCI_RH_reference_assembly.step.zip`.
- **Exploded exchange model:** `SCCI_RH_reference_exploded.step.zip`.
- **Dimensioned vector drawings:** `drawings/reference-layout.svg` and 8 dedicated tray mounting sheets.
- **Mounting datums:** `drawings/mounting-hole-table.csv` contains all 32 actual native PCB axes.
- **Mechanical BOM:** `mechanical-bom.csv` lists 162 mechanical pieces separately from 8 source PCB compounds.
- **Individual mechanical meshes:** `stl/`, one STL per mechanical piece. They are inspectable nominal geometry, not validated printing instructions.

Use `EXTRACT_STEP.cmd` to unpack the two populated STEP archives into `extracted/`; the script verifies the archive and uncompressed member hashes. The raw populated files are larger than GitHub's 100 MB file limit, so the repository ships lossless compressed files. No source details were reduced. `OPEN_EXPLODED.cmd` extracts and opens the exploded STEP in FreeCAD. The native assembly is much smaller because FCStd compresses its geometry internally.

The 600 × 310 × 240 mm enclosure carries two unequal bays and four 50 mm tiers. Its panels, rails, removable trays, grips, feet, posts and nominal M3 mounting hardware are actual solids. Each board uses its original four 3.2 mm mounting holes with a dedicated 10 mm insulating standoff. The controller and actual source boards retain original STEP geometry and checksum properties. Threads and material grades are explicitly unqualified. The separate root-owned harness model occupies the contract's cable service reservations.

`contract.json` defines board transforms, all mount axes, exact final object labels, exploded offsets, reserved spaces, panel openings and clearance targets. `board-datums.json` comes directly from the frozen KiCad boards. `producer-geometry.json` binds outputs, source geometry, source checksums and nominal solid-volume allocations. Independent native geometry and interference results are supplied by the Stage 5 auditor; producer assertions do not replace that check.

Rebuild board datums with KiCad's bundled Python and `extract_board_datums.py`. Build actual geometry using FreeCAD's bundled Python and `build_reference.py`. Run `style_gui.py` only in the genuine FreeCAD GUI context; it hides construction operands and applies a derived nominal palette. Run `make_drawings.py` and `finalize_receipts.py` after geometry export. Rebuilding intentionally regenerates this new Stage 5 package, never prior source boards. The full source populated STEP files remain authoritative for the electronics, and frozen earlier artifacts are not modified.

This is a digital engineering reference chassis. It does not establish implant packaging, manufacturing readiness, structural load capacity, thermal performance, grounding, EMI, ingress, electrical safety, biocompatibility or biological capability. See `docs/stage5/reference-mechanical-design.md` for the assembly method and explicit limits.
