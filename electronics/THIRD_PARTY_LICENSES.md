# KiCad library material

The local footprint collection in `scci_rh.pretty/` and STEP component geometry in
`models3d/` are snapshots from the KiCad community libraries supplied with the
KiCad 10.0.6 installation used for this project. The library commit was not
recorded by that installation; no upstream commit identity is claimed.

Copyright belongs to the respective KiCad library contributors. These copied
library collections retain **CC BY-SA 4.0 with the KiCad libraries exception**.
This is separate from the license covering Project SCCI RH's original source.
The exception applies to electronic designs and generated design exports; it
does not remove the license of redistributed library collections.

Sources:

- [KiCad footprints](https://gitlab.com/kicad/libraries/kicad-footprints)
- [KiCad 3D packages](https://gitlab.com/kicad/libraries/kicad-packages3D)
- [KiCad library license](https://www.kicad.org/libraries/license/)
- [CC BY-SA 4.0 legal text](https://creativecommons.org/licenses/by-sa/4.0/legalcode)

Local changes: the model references in footprint files point to project-local
`models3d/` files; geometry and pin numbering are otherwise retained. The native
schematic's `SCCI_RH.kicad_sym` symbols were written for this project from documented
device pin functions; they are not a copy of KiCad's symbol artwork.

The original KiCad library license notice is included in
`KICAD_LIBRARIES_LICENSE.md`. Attribution and license terms travel with the
copied collection.

The same attribution and library terms cover project-local footprint snapshots
under `stage4/*/*.pretty/`, including `stage4/monitoring-transport/scci_rh_transport.pretty/`.
Those footprint copies retain their source pad geometry and numbering. Stage 4
custom symbols are project-authored pin/function drawings; manufacturer
datasheets are linked as technical references, rather than redistributed here.

ngspice 46 was used from the installed KiCad distribution. No ngspice binary is
redistributed here. See [ngspice](https://ngspice.sourceforge.io/) for its source
and license. The included circuit netlist and generic model parameters are
Project SCCI RH work, and are not manufacturer device models.
