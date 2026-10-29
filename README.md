# Project SCCI RH

### A spinal interface concept, from scientific question to inspectable engineering

An entirely digital research and engineering project exploring **invasive spinal
cord–computer interfaces (SCCI)**: record relevant activity, interpret it,
select an individualized intervention, and observe the response.

**Two ambitions:** expert-informed practice that could improve retained motor
learning, and feedback over a selected physiological function.

**[Inspect the build in your browser](https://pratham-cloud-ctrl.github.io/Project-SCCI-RH/)** ·
[Explore the project](docs/explore/README.md) ·
[Read the paper](output/pdf/Project_SCCI_RH_Integrated_Manuscript.pdf) ·
[Download the engineering release](https://github.com/pratham-cloud-ctrl/Project-SCCI-RH/releases/tag/v2.1.0)

**No CAD software needed to inspect:** the browser inspector provides selectable
3D assemblies, all eight populated boards, interactive component/net lookup,
all four copper layers and 80 searchable schematic sheets. The
[download panel](https://pratham-cloud-ctrl.github.io/Project-SCCI-RH/?view=downloads)
also supplies standard **STEP solids**, complete **FreeCAD** files and complete
**KiCad** projects for local inspection and editing.

| Future implanted-interface concept | Full-scale engineering reference |
|:---:|:---:|
| [![Future can, header and separate recording/stimulation leads](docs/explore/assets/cad-future-assembled.jpg)](docs/explore/cad.md#future-implanted-interface) | [![Eight populated boards in the complete reference chassis](docs/explore/assets/cad-reference-assembled.jpg)](docs/explore/cad.md#full-scale-reference-assembly) |
| **60 × 58 × 14 mm**, before leads. A proposed miniaturized package. | **600 × 310 × 240 mm**, including feet. Actual board geometry at 1:1 scale. |

## Choose what you want to explore

| | Open the guide | What you can inspect |
|---|---|---|
| **01 · Theory & mechanisms** | [Understand the idea](docs/explore/theory.md) | Both application mechanisms, the assumptions behind them, evidence and mathematical models |
| **02 · CAD & 3D models** | [Explore the mechanical design](docs/explore/cad.md) | Assembled/exploded views, rotatable meshes, editable FreeCAD files, STEP exports and drawings |
| **03 · Electronics & KiCad** | [Browse the eight boards](docs/explore/electronics.md) | Board gallery, circuit roles, schematic PDF, native projects, layouts and component lists |
| **04 · Firmware & software** | [Follow the implemented logic](docs/explore/firmware.md) | Current nRF5340 image, production control code, packet handling and runnable verification |
| **05 · Evidence & reproduction** | [Review the work](docs/explore/reviewer-guide.md) | A short reviewer walkthrough, results, requirements, source records and reproduction commands |

Use the browser inspector for viewing. Links labelled **native source** lead to
engineering files that GitHub may offer only as downloads. Use the complete
packages in the inspector to open them locally; the guides explain the required
software, dependencies and how to preserve the released originals.

## The project in one loop

**Observe → interpret → calibrate → request stimulation → supervise delivery → observe response.**

For motor learning, expert performance informs a task-conditioned reference;
learner-specific calibration determines a reachable intervention during practice.
Later stimulation-OFF probes assess retention separately from assisted performance.
Expert voltage is not replayed as a skill.

For physiological feedback, a function-specific configuration observes a selected
state and requests bounded support. The worked pressure example uses an external
pressure sensor and positive spinal pressor authority. It is a selected pathway,
not a universal body-control mechanism.

## What has been delivered

| Research | Electrical & software | Mechanical |
|---|---|---|
| [28-page illustrated paper](output/pdf/Project_SCCI_RH_Integrated_Manuscript.pdf) | [Eight routed, populated KiCad boards](docs/explore/electronics.md) | [Editable reference and future-interface CAD](docs/explore/cad.md) |
| [18 primary/inspiration references](docs/stage6/evidence-review.md) | [Target-linked nRF5340 firmware](firmware/nrf5340/uart-revision/README.md) | [Six mechanical review sheets](cad/stage5/drawings/SCCI_RH_Stage5_Mechanical_Review.pdf) |
| [Conditional studies and retained negative findings](docs/explore/theory.md) | [Executed production-core digital replay](docs/stage6/integration-verification.md) | [Mapped interfaces, parts and exchange files](docs/explore/cad.md) |

The integrated replay passes **114,426 finite software assertions** and includes
**5,184 modeled motor events** and **1,200 pressure events**. Favorable, neutral
and adverse learning assumptions are retained. These are software/model results;
their implications are explained in the [theory guide](docs/explore/theory.md).

This is a completed **digital concept and engineering reference**. No physical
device execution or original human/animal experiment is claimed. Useful chronic
spinal decoding, retained human benefit and a miniaturized implanted implementation
remain conditional. The current target records in OBSERVE, inhibits neural
acquisition while armed, and has no radio image. The reference boards do not fit
the future can.

## Start, inspect, or contribute

- **First visit:** use the [Explore hub](docs/explore/README.md) or the [five-minute route](docs/explore/reviewer-guide.md#five-minute-overview).
- **Find a file:** use the [repository map](docs/explore/repository-map.md) to distinguish current entry points from historical studies.
- **Check the engineering:** use [verification and reproduction](docs/explore/reviewer-guide.md#reproduce-the-current-engineering).
- **Understand authorship:** read the [contributions](docs/stage6/contributions.md), [defence guide](docs/stage6/defence-guide.md) and [LICENSE](LICENSE).

Pratham Varma conceived and steered Project SCCI RH. AstroSam’s
[Mind-Link](https://github.com/sam-astro/Mind-link) inspired the progression from
future vision to inspectable engineering; SCCI_RH develops its own spinal architecture
and artifacts. Substantial AI assistance is documented in the contribution record.

**Engineering release:** [v2.1.0](https://github.com/pratham-cloud-ctrl/Project-SCCI-RH/releases/tag/v2.1.0).
**Browser inspection and guide refresh:** 21 October 2026. The paper and verified engineering
geometry and circuit behavior are preserved through the recorded name migration. Historical stage records remain available;
use the guides above for the current reading order. The technical inspector
supports engineering review; presentation website and video work remain parked.
