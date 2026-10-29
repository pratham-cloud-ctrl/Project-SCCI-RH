# Start here: Project SCCI RH

**[Inspect the actual build in your browser](https://pratham-cloud-ctrl.github.io/Project-SCCI-RH/)**
or use its [standard/native downloads](https://pratham-cloud-ctrl.github.io/Project-SCCI-RH/?view=downloads).
The browser view requires no CAD installation; the downloads support local
engineering inspection and editing.

**[Open the visual Explore hub](docs/explore/README.md)** for the easiest reading
route. Choose [theory](docs/explore/theory.md), [CAD & 3D](docs/explore/cad.md),
[electronics & KiCad](docs/explore/electronics.md), or [firmware](docs/explore/firmware.md).
The [reviewer guide](docs/explore/reviewer-guide.md) offers a five-minute overview
and reproduction instructions; the [repository map](docs/explore/repository-map.md)
locates the current source files.

The detailed engineering reading order follows below.

Project SCCI RH is an entirely digital research and engineering concept for invasive
spinal recording, interpretation, selective stimulation and feedback. Both
expert-informed retained motor learning and function-specific physiological
regulation are central. AstroSam's Mind-Link inspired the progression from a
future idea to inspectable engineering; SCCI_RH contributes its own spinal design.

## 1. Read the integrated account

- [Integrated illustrated manuscript](output/pdf/Project_SCCI_RH_Integrated_Manuscript.pdf): 28 pages connecting scientific premises, mathematical models, actual engineering and verification.
- [Editable manuscript and builder](manuscript/stage6/manuscript.md): complete source, figures and reproducible typesetting alongside it.
- [Current scope and completed stages](CURRENT_STATUS.md): what exists and which capabilities remain conditional.
- [Primary-source evidence audit](docs/stage6/evidence-review.md): 18 references, populations, access methods and limits.
- [Original 28-page hypothesis paper](docs/stage6/original-hypothesis/README.md): unchanged archival input and its verified digest.

## 2. Understand the two mechanisms

- [Motor and physiological mechanisms](docs/stage3/conditional-concept.md): expert reference alignment, learner-specific practice and selected pressure feedback.
- [Assumption ledger](docs/stage3/conditional-concept/assumption-ledger.csv): adopted premises and what would invalidate their use.
- [Current claims and requirements](docs/stage6/requirements-claims-trace.csv): all 36 original requirements receive an explicit evidence-scoped disposition.

Expert voltage is not replayed as a skill. Assistance during practice and later
stimulation-OFF learning are different outcomes. Pressure support uses external
pressure feedback and selected pressor authority; it is not universal body control.

## 3. Open the actual electronics and software

- [Current corrected carrier firmware](firmware/nrf5340/uart-revision/README.md): UART frame scheduling fix, regression evidence and rebuilt target image; the original image remains a historical checkpoint.
- [KiCad board index](electronics/stage4/integrated-pcb/BOARD_INDEX.md): eight routed populated boards, the 80-sheet hierarchy, fabrication references and native files.
- [Preserved BT40F/nRF5340 image checkpoint](electronics/stage4/integrated-pcb/firmware-profile/README.md): original ELF/HEX/BIN, configuration and exact historical carrier scope.
- [Integrated replay methods](docs/stage6/integration-verification.md): compiled production C core, companion/body adapters, actual results and fault boundaries.
- [Integration experiment entry](experiments/stage6/README.md): runnable reproduction and compiler requirements.

The target acquires neural data in OBSERVE and inhibits it while stimulation is
armed. The replay's live synthetic spinal features and current-to-recruitment
mapping are explicit conditional adapters. No target peripherals or hardware
have been physically executed.

## 4. Open the mechanical assembly

Start with the [native CAD package](cad/stage5/README.md). Its explicit Windows
launchers open FreeCAD directly without relying on file associations.
Use the [portable current launcher](cad/CURRENT_CAD.md) on another Windows computer
or to select your installed FreeCAD executable.

- [Complete reference launcher](cad/stage5/OPEN_REFERENCE_ASSEMBLY.cmd): actual eight-board assembly, 260 physical objects, session-only cutaway.
- [Future implanted-interface source](cad/stage5/future-interface/README.md): 230 physical parts, 36 mapped ports, separate leads and six allocations.
- [Six mechanical review sheets](cad/stage5/drawings/SCCI_RH_Stage5_Mechanical_Review.pdf): dimensions, service, interfaces and evidence boundaries.
- [Mating and wiring source](cad/stage5/harness/README.md): actual terminal identities, nominal housings and planning annotations.

The 600 x 310 x 240 mm reference keeps all boards at 1:1 scale. The separate
60 x 58 x 14 mm future can/header requires redesigned miniaturized electronics
and chronic thermal/interface qualification. Its appearance does not imply the
existing boards fit inside it.

## 5. Reproduce and check

Use a full Git clone at tag `v2.1.0` for history/blob verification. Install the
dependencies in [requirements-lock.txt](requirements-lock.txt) in a Python 3.12
environment. Read the experiment entry for a C11 compiler, then run:

```text
python scripts/verify_manifest.py
python scripts/verify_stage6_release.py
python firmware/nrf5340/uart-revision/verify_revision.py
python scripts/stage6/verify_digital_path.py
python scripts/verify_stage5_mechanics.py
python scripts/verify_integrated_pcb.py
```

Portable native-receipt checks bind actual prior CAD operations; they do not
emulate KiCad or FreeCAD. Native regeneration requires the application runtimes.
The source ZIP is an exchange copy without `.git` history. The GitHub release
checksum list verifies the downloadable PDFs and ZIP separately.

## 6. Explain and extend the work

- [Defence and learning guide](docs/stage6/defence-guide.md): consumer mechanisms, technical questions and honest answers.
- [Contribution record](docs/stage6/contributions.md): student conception/steering and substantial AI assistance.
- [Release plan and reproduction](docs/stage6/release-plan.md): artifacts, checks and limits.
- [Digital exit review](docs/stage6/exit-review.md): finite completion criteria.

The original negative studies and historical v1.0.0 subsystem remain preserved.

The [17 October whole-project review](docs/review-v2.0.1/README.md) records the
scope, concrete corrections, current verification and accepted future premises.
Current engineering values take precedence over superseded allocations. Video
and website revision were parked and are not current release deliverables.
