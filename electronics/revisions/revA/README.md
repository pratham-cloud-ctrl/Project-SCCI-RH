# Archived revision A: unprotected load legs

This is the initial circuit/PCB and numerical result before R14/R15 were added.
Its generic-device ngspice transient completed 6 ms and predicted a brief
**1361.3598 μA** reverse-enable peak despite approximately 100 μA settled current.
Integrated phases were +20.039515 / −20.040363 nC.

Revision B, the main project, inserts 12 kΩ resistance in each output leg and
keeps the recording channel unchanged. Its nominal generic-model peak is
102.5784 μA, with reduced load-voltage compliance. Both revisions remain digital
reference designs, not validated hardware or biological interfaces.

The archived native files preserve the original design and all embedded
schematic symbols. Their footprint and 3D-model collection is the shared
`../../scci_rh.pretty/` and `../../models3d/` collection; the main project's relative
model paths would need rebasing to reopen this archival copy with full 3D models.
The current main KiCad project is the supported editable deliverable.

`metrics.json`, `current_sink_generic.cir`, `spice_transient.csv` and
`ngspice_log.txt` preserve the numerical evidence for the discovered transient.
The archive includes no manufacturer macromodel claim.
