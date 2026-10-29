# Project SCCI RH 1.0.0 — digital engineering release

This release connects a proposed invasive spinal recording/stimulation architecture
to a source-grounded paper, two reproducible synthetic application studies,
host-tested pulse logic, a routed electrical reference, and editable mechanical
and presentation assets.

Start with the [20-page paper](../output/pdf/SCCI_RH_engineering_paper.pdf), then open
the [local interactive walkthrough](../site/index.html) and the
[72-second captioned video](../media/SCCI_RH_walkthrough.mp4). Native KiCad, FreeCAD,
Blender, STEP and STL files accompany the code and recorded results.

The computational contribution separates stimulation-on assistance from assumed
retained learning, tests a zero-benefit control and exposes latency failures.
The physiological study explores synthetic pressure feedback under bounded
actuation and sensor faults. Their numerical improvements are conditional model
outcomes rather than human performance predictions.

Electrical review exposed a large modeled switching transient. Revision B adds
two 12 kΩ output resistors in the native schematic and PCB. Generic-device
transients support improvement under the documented test cases, with stored
polarization and compliance limits explicitly retained. Revision A evidence is
preserved for an inspectable design history.

The [verification record](../provenance/verification.json) reports 14 passing
Python tests, 23 compiled-C assertions, clean ERC/DRC/parity checks, selected
electrical-model checks and nominal CAD intersection checks. Evidence, claims,
decisions, source versions and AI contributions are recorded alongside artifacts.

No implant was built or tested. Electrode-to-state decoding, stimulation-to-plant
calibration, chronic access, implant electronics and biological effectiveness
remain future research questions. The reference board uses external acquisition
and sequencing interfaces; the rendered enclosure represents a desktop device.
