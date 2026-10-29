# Explore the mechanical design

[Explore](README.md) · [Theory](theory.md) · **CAD** · [Electronics](electronics.md) · [Firmware](firmware.md)

SCCI_RH has two connected physical identities: a full-size electronics reference and a separate proposed implanted interface. The images below come from the saved CAD solids. You can inspect the design here before installing any software.

**View now:** [future interface in interactive 3D](https://pratham-cloud-ctrl.github.io/Project-SCCI-RH/?design=future&view=model) · [complete reference in interactive 3D](https://pratham-cloud-ctrl.github.io/Project-SCCI-RH/?design=reference&view=model).
Rotate, select/isolate named parts, hide covers and use the explode slider. Six
nonphysical allocation volumes in the future package default off. Browser
meshes are source-derived display copies; use STEP for solid CAD interchange.

**Open in your CAD software:** [complete native FreeCAD ZIP](https://pratham-cloud-ctrl.github.io/Project-SCCI-RH/downloads/SCCI_RH_CAD_Native.zip) · [complete 260-object reference STEP ZIP](https://pratham-cloud-ctrl.github.io/Project-SCCI-RH/downloads/SCCI_RH_Reference_Complete_STEP.zip) · [future fitted STEP](https://pratham-cloud-ctrl.github.io/Project-SCCI-RH/downloads/SCCI_RH_Future_Interface.step).
The native ZIP includes the feature module and opening launchers. STEP is the
standard interchange route for compatible CAD applications; editable feature
history remains in FreeCAD.

**Start with the [six-page mechanical drawing set](../../cad/stage5/drawings/SCCI_RH_Stage5_Mechanical_Review.pdf)** for dimensions, assembly, ports and engineering boundaries.

## Full-scale reference assembly

[![Full-size eight-board reference assembly with the covers opened for inspection](assets/cad-reference-assembled.jpg)](https://raw.githubusercontent.com/pratham-cloud-ctrl/Project-SCCI-RH/main/cad/stage5/renders/reference_assembled.png)

The **600 × 310 × 240 mm** chassis, including feet, holds the eight populated boards at their original **1:1 scale**. The combined native assembly contains **260 physical objects**: board compounds, enclosure parts, mounts and mating interfaces. Individual electronic components remain part of the board compounds.

[![Exploded view of the reference chassis, populated trays and mating interfaces](assets/cad-reference-exploded.jpg)](https://raw.githubusercontent.com/pratham-cloud-ctrl/Project-SCCI-RH/main/cad/stage5/renders/reference_exploded.png)

Removable trays, covers and separate standoffs expose how the boards mount and connect. The drawing set shows their service arrangement and all 32 original board mounting axes.

| Inspect | Open |
|---|---|
| Complete editable assembly | [Native FreeCAD model](../../cad/stage5/SCCI_RH_stage5_reference_full.FCStd) |
| Mechanical parts and eight board compounds | [Reference source guide](../../cad/stage5/reference/README.md) |
| Neutral assembly and exploded exports | [Populated STEP ZIP](../../cad/stage5/reference/SCCI_RH_reference_assembly.step.zip) · [Exploded STEP ZIP](../../cad/stage5/reference/SCCI_RH_reference_exploded.step.zip) |
| Mechanical-only exchange geometry | [Mechanical STEP](../../cad/stage5/reference/SCCI_RH_reference_mechanical.step) |
| Part identities and quantities | [Combined mechanical BOM](../../cad/stage5/MECHANICAL_BOM.csv) |
| Mating housings and wiring plan | [Harness guide](../../cad/stage5/harness/README.md) · [36-port bridge](../../cad/stage5/harness/body-port-bridge.csv) |

The older populated STEP links above describe the **170-object chassis/board subassembly**. The new complete reference STEP download includes all **260 objects**, adding the mating and harness pieces shown in the complete browser model. Both sets remain available with explicit scope. Large STEP files are supplied losslessly compressed; extract before opening. The older [hash-checking extractor](../../cad/stage5/reference/EXTRACT_STEP.cmd) applies to the preserved chassis exports. The [reference inspection STL](../../cad/stage5/SCCI_RH_reference_inspection.stl) is a 36.8 MB display mesh; use the interactive inspector for browser exploration.

## Future implanted interface

[![Proposed compact spinal interface with separate recording and stimulation leads](assets/cad-future-assembled.jpg)](https://raw.githubusercontent.com/pratham-cloud-ctrl/Project-SCCI-RH/main/cad/stage5/renders/future_assembled.png)

The separate **60 × 58 × 14 mm** can/header, before leads, gives the future concept a detailed physical identity. It contains **230 physical parts and six internal allocation objects**. Its **36 ports** comprise 16 recording inputs, a recording reference, a separate body-bias contact, 16 selectable stimulation contacts and two stimulation returns.

[![Exploded view of the conditional package, lead interfaces and labelled internal allocations](assets/cad-future-exploded.jpg)](https://raw.githubusercontent.com/pratham-cloud-ctrl/Project-SCCI-RH/main/cad/stage5/renders/future_exploded.png)

**[Rotate the future model in GitHub's STL viewer](../../cad/stage5/future-interface/SCCI_RH_future_interface.stl).** This 4.8 MB mesh is within GitHub's documented 10 MB viewer limit; see the [viewer controls and limits](https://docs.github.com/en/repositories/working-with-files/using-files/working-with-non-code-files#3d-file-viewer). The mesh shows material geometry; use the images and native model for colours, identities and internal allocations.

| Inspect | Open |
|---|---|
| Editable fitted model and feature module | [FreeCAD model](../../cad/stage5/future-interface/SCCI_RH_future_interface.FCStd) · [Feature definitions](../../cad/stage5/future-interface/scci_rh_future_features.py) |
| Exchange geometry | [Fitted STEP](../../cad/stage5/future-interface/SCCI_RH_future_interface.step) · [Exploded STEP](../../cad/stage5/future-interface/SCCI_RH_future_interface_exploded.step) |
| Parts and functional contacts | [Parts inventory](../../cad/stage5/future-interface/parts.csv) · [Port map](../../cad/stage5/future-interface/port-map.csv) |
| Design rationale and edit behaviour | [Future-interface source guide](../../cad/stage5/future-interface/README.md) |

**The reference boards do not fit this compact can.** Miniaturized electronics, implanted access, energy storage, heat management, sealing and anatomical fit remain explicit future engineering conditions. The internal boxes reserve space; they are not a completed compact electronic design. Harness centerlines are planning annotations, not a qualified wire loom.

## Open and edit the native CAD

Download or clone the complete repository and install **FreeCAD 1.1 or later**. On Windows, run [OPEN_CURRENT_CAD.cmd](../../cad/OPEN_CURRENT_CAD.cmd) and choose reference, closed reference, future or exploded future. For another installation, set `SCCI_RH_FREECAD_EXE` to its executable; the [portable opening guide](../../cad/CURRENT_CAD.md) gives the exact commands.

On macOS/Linux, open the reference FCStd directly. Before opening the future model, use FreeCAD's Python console to add the supplied module directory and import its editable features:

```python
import sys
sys.path.insert(0, "/path/to/Project-SCCI-RH/cad/stage5/future-interface")
import scci_rh_future_features
```

Then open the fitted or exploded future FCStd. Replace the example path with your checkout. Keep the feature module alongside the model.

For viewing only, choose **Don't Save** when closing. Use **Save As** into a separate working copy for intentional edits. Session cutaways can mark display state as modified. Saved nominal geometry and documented clearance checks support inspection; they do not establish manufactured, implanted or biological performance.

[Mechanical verification and finite limits](../../docs/stage5/exit-review.md) · [Repository map](repository-map.md)
