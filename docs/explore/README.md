# Explore Project SCCI RH

[Project home](../../README.md) · [Theory](theory.md) · [CAD](cad.md) · [Electronics](electronics.md) · [Firmware](firmware.md) · [Review](reviewer-guide.md)

Project SCCI RH asks what implanted spinal recording, interpretation and selective
stimulation could enable. This guide connects that future idea to the actual
research, code, circuits and mechanical files you can inspect today.

**[Open the interactive build inspector](https://pratham-cloud-ctrl.github.io/Project-SCCI-RH/)**
for 3D assemblies, eight boards, all copper layers and 80 schematic sheets.
No CAD installation or viewer account is required. Use its
[download panel](https://pratham-cloud-ctrl.github.io/Project-SCCI-RH/?view=downloads)
for standard STEP solids and complete native FreeCAD/KiCad packages.

## Start with your interest

| Guide | You will find | First thing to open |
|---|---|---|
| **[01 · Theory & mechanisms](theory.md)** | The two use cases, consumer journey, scientific precedents and explicit assumptions | [Integrated illustrated paper](../../output/pdf/Project_SCCI_RH_Integrated_Manuscript.pdf) |
| **[02 · CAD & 3D](cad.md)** | Reference chassis, future implanted interface, exploded views and editable models | [Mechanical review sheets](../../cad/stage5/drawings/SCCI_RH_Stage5_Mechanical_Review.pdf) |
| **[03 · Electronics & KiCad](electronics.md)** | Eight-board gallery, circuit roles, native schematics and PCB layouts | [Full schematic PDF](../../electronics/stage4/integrated-pcb/integration/master/SCCI_RH_integrated.pdf) |
| **[04 · Firmware & software](firmware.md)** | Current target image, production control logic, companion interfaces and tests | [Current firmware package](../../firmware/nrf5340/uart-revision/README.md) |
| **[05 · Evidence & reproduction](reviewer-guide.md)** | A short walkthrough, results, claim limits and exact reproduction routes | [Requirements and claims](../stage6/requirements-claims-trace.csv) |

## See the design before opening an application

| Future implanted interface | Full-size reference assembly |
|:---:|:---:|
| [![Conditional future interface with separate leads](assets/cad-future-exploded.jpg)](cad.md#future-implanted-interface) | [![Reference chassis and boards in exploded view](assets/cad-reference-exploded.jpg)](cad.md#full-scale-reference-assembly) |
| Proposed compact can, internal allocations and 36 mapped ports. | Actual board-scale electronics, enclosure, mounting and mating interfaces. |

The guides provide image previews, browser inspection and native source links
side by side. GitHub may show a size warning instead of rendering a native file;
use the inspector for viewing and the complete downloads for local editing.
The supplied packages preserve local libraries and feature modules. Opening a
native-file link on GitHub does not launch a local CAD application.

## Three ways through the project

1. **Understand the idea:** read [theory](theory.md), then the paper’s mechanisms
   and assumptions. Follow one modeled result back to its source.
2. **Inspect the engineering:** browse [CAD](cad.md) and [electronics](electronics.md),
   then trace an observation or stimulation command through [firmware](firmware.md).
3. **Review the evidence:** take the [reviewer walkthrough](reviewer-guide.md),
   inspect the claims and run the finite verification checks.

Use the [repository map](repository-map.md) when you want the exact source path.
The [engineering release](https://github.com/pratham-cloud-ctrl/Project-SCCI-RH/releases/tag/v2.0.1)
provides the manuscript, mechanical drawing set, source ZIP and checksums.

## Reading the claims

**Established by the project:** its stated digital artifacts, finite model and
software results, target linkage and native-design checks.

**Future premises:** useful chronic spinal information, learner-specific
recruitment, favorable retained human learning and a qualified miniaturized implant.
The full-size reference and future implanted package are separate embodiments.

AstroSam’s [Mind-Link](https://github.com/sam-astro/Mind-link) inspired the format.
SCCI_RH’s spinal architecture and artifacts have their own documented provenance;
see [contributions](../stage6/contributions.md) and [current status](../../CURRENT_STATUS.md).
