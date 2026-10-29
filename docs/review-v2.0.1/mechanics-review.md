# Mechanical and CAD handoff review

Reviewed **17 October 2026** against the original goal: give the proposed SCCI
an inspectable physical identity while keeping the completed reference
electronics and future miniaturized implant clearly distinguished. Both
expert-informed retained learning and function-specific physiological feedback
remain conditional applications of the same recording/stimulation architecture.

## Finding fixed

Most original Stage 5 launchers assumed the original laptop's FreeCAD path.
Two reference launchers already accepted `SCCI_RH_FREECAD_EXE`, but that setting
did not consistently work across the current assembly and future-interface
entry points. This obstructed a reviewer using another Windows installation.

The new [current CAD entry](../../cad/CURRENT_CAD.md) provides one menu and four
explicit modes, resolves the configured executable, PATH and common Windows
installations, and retains this laptop's known installation as a fallback.
Invalid explicit settings produce an actionable error. Repository source paths
are relative to the launcher, including folders containing spaces. The original
Stage 5 sources and launchers are preserved unchanged.

Five discovery/selection scenarios passed with **Windows PowerShell 5.1** and
**PowerShell 7.6.5**. Tests invoke real child PowerShell processes in probe mode;
they do not execute the mock programs or claim to launch CAD on Linux.

## Completed checks

| Check | Result and scope |
|---|---|
| Current Stage 5 checkpoint | **12,996 checks passed**, including exact source bindings to the saved native inspection and exchange-file receipts |
| Fresh FreeCAD application inspection: combined reference | **260 physical objects, 1,920 solids**, eight original PCB compounds containing **1,668 solids**; no invalid or null physical shapes |
| Fresh FreeCAD application inspection: future interface | **230 physical objects/solids**, six internal allocations and four construction shapes; no invalid or null physical shapes |
| Native chassis bounds | Base, lid and feet reproduce the **600 x 310 x 240 mm** enclosure extent, before local cable protrusions |
| Port and packaging boundary | **36 functional ports** remain identified; recording reference/body bias are distinct from stimulation returns, and the bridge maps outputs after the independent disconnect guards |
| Actual application views | Newly captured reference cutaway and fitted future-interface screenshots visually inspected |
| Source preservation | Both native source hashes match their frozen Stage 5 receipts; no source geometry was edited or saved |

The [machine-readable current review](mechanics-native-review.json) records the
source hashes and native measurements. The combined-model validity operation
outlasted the MCP response window; it completed inside FreeCAD, wrote its result,
and that completed result was then retrieved successfully through the bridge.
It was not rerun or reported as a pass from the initial timeout.

![Fresh native reference cutaway](mechanics-reference-native.png)

![Fresh native future-interface view](mechanics-future-native.png)

## Accepted boundaries

The full reference contains the actual boards at their original scale. Those
boards do **not** fit the separate **60 x 58 x 14 mm** future can/header. Its
battery, electronics, HV storage, insulation and antenna reservations remain
miniaturization premises. Lead anatomy, hermetic sealing, chronic thermal
performance and biological efficacy remain unqualified.

The existing exact clearance/interference results remain valid by unchanged
source bindings; this review did not remeasure every expensive material pair.
Harness centerlines remain planning paths, not a packed physical loom or wire
cut list. No mechanical redesign was justified by this review's findings.
