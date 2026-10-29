# SCCI_RH future spinal interface — conditional mechanical embodiment

This is the compact future concept, separate from the large eight-board digital
reference assembly. It preserves the Stage 2 **60 × 58 × 14 mm** core/header
envelope and all **36** functional ports. It gives that concept a detailed,
inspectable mechanical identity; miniaturization is an explicit engineering
premise. The Stage 4 boards do not fit inside this housing.

Open **`OPEN_FUTURE_INTERFACE.cmd`** for the fitted native FreeCAD model or
**`OPEN_FUTURE_INTERFACE_EXPLODED.cmd`** for its exploded inspection view.
The launcher loads the supplied editable-feature module before opening the file.
It does not rely on Windows file associations. STEP can be opened in other CAD
systems; STL is a material-only display mesh in millimetres.

| Artifact | Purpose |
|---|---|
| `SCCI_RH_future_interface.FCStd` | Authoritative fitted native parts and editable feature history |
| `SCCI_RH_future_interface.step` | Physical concept solids only; no allocation boxes |
| `SCCI_RH_future_interface.stl` | Tessellated physical concept material; separate touching parts remain separate shells |
| `SCCI_RH_future_interface_exploded.FCStd` | Derived native inspection view, with source-part names and offsets |
| `SCCI_RH_future_interface_exploded.step` | Exploded physical parts plus explicitly named internal allocations |
| `contract.json` | Dimensions, 36-port map, part identities, hashes and inspection contract |
| `geometry-receipt.json` | Generator's actual native/exchange checks |
| `port-map.csv`, `parts.csv` | Inspectable contact and part inventories |

The can, lid, seam, RF window, header, keyed inserts/plugs, tapered boots, two
separate insulated leads, 36 ferrules, 36 ceramic sleeves, 36 pins, 36 sockets,
36 individually routed conductors and 36 distal contacts are actual solids.
Each custom physical feature exposes a complete **Specification** with editable
dimensions/points in millimetres. **CuttingParts** links retain the exact
conductor/insulator relationship. The cable/paddle union and wire subtraction
also retain native FreeCAD fuse/cut history. Recompute after editing a feature.
`DesignParameters` is a clearly labelled summary; it does not silently propagate
global changes. Regenerate for a globally consistent parameter change.

The recording lead has 16 recording contacts, a shared reference and a distinct
body-bias contact. It is not 16 bipolar electrode pairs. The stimulation lead has
16 selectable contacts and two dedicated returns. These leads are illustrated
apart for inspection; their anatomical placement, access plane, fit and lengths
are unassigned. Contact colour alone is not the mapping: every part carries its
P01–P36 identity and functional role.

Internal battery, board, component, HV-bank, insulation and antenna shapes are
reservations. Seal geometry, zero-gap nominal electrical mating surfaces,
strain-relief tapers and the RF window have no manufactured, mechanical, thermal,
RF, biocompatibility or hermeticity qualification. Current target firmware keeps
the radio off. No model establishes implanted expert-to-learner skill transfer or
autonomous physiological control.

See [the engineering rationale](../../../docs/stage5/future-package-design.md).
Rebuild from the repository root with the installed FreeCAD Python:

```powershell
& 'E:\project workspace assests\CAD\FreeCAD\bin\python.exe' cad/stage5/future-interface/build_future_interface.py
```

The generator modifies only this package's outputs. Rebuilding changes CAD file
hashes; rerun the independent Stage 5 audit and refresh the repository manifest
before accepting a new revision.
