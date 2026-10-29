# Review the work

[Explore](README.md) · [Theory](theory.md) · [CAD](cad.md) · [Electronics](electronics.md) · [Firmware](firmware.md)

This page offers a short route through Project SCCI RH and a separate route for
reproducing its engineering checks. Reading and browsing need no software.

## Five-minute overview

1. **Understand the question.** Read the [theory guide](theory.md). Identify
   what is measured, what is inferred and what is assumed for each application.
2. **See the physical identity.** Browse [CAD](cad.md). Compare the actual
   full-scale reference with the separate future miniaturized package.
3. **Inspect one circuit.** Open the [board gallery](electronics.md) and follow
   one board to its current native schematic and layout.
4. **Trace one decision.** Read [firmware](firmware.md) and the
   [integration methods](../stage6/integration-verification.md). Separate
   production-code execution from the companion/body response models.
5. **Check the claim.** Use the [requirements trace](../stage6/requirements-claims-trace.csv)
   and [claim register](../stage6/evidence-claims.csv) to find the evidence and
   limitation behind it.

The [29-page integrated paper](../../output/pdf/Project_SCCI_RH_Integrated_Manuscript.pdf)
connects these views into one account. Its
[editable source](../../manuscript/stage6/manuscript.md) has searchable headings,
equations and links even when a PDF preview is inconvenient.

## What the example results show

| Digital result | Interpretation | Where to inspect |
|---|---|---|
| Neutral teaching: first ON error 16.668 mm, final OFF error 5.605 mm | Assistance can improve practice performance without an additional retention advantage | [Learning explanation](theory.md) and [replay summary](../../results/stage6/integration-summary.json) |
| Favorable/adverse teaching: final OFF error 2.897 / 34.845 mm | The assumed teaching law changes the retained outcome; its human value is not measured | [Model and assumptions](../../manuscript/stage6/manuscript.md#82-finite-results) |
| Pressure RMSE 11.871 versus 20 mmHg unassisted; peak 129.999 against a 120 mmHg target | A conditional feedback example with a visible recovery overshoot | [Integration methods](../stage6/integration-verification.md) |
| Eight routed boards, source-bound native inspections and compiled target artifacts | Concrete digital engineering whose physical performance remains unmeasured | [Electronics](electronics.md), [firmware](firmware.md) and [CAD](cad.md) |

These numbers belong to the Stage 6 replay's selected protocol. Earlier Stage 3
studies have their own parameters and results; they are retained in the
[development record](repository-map.md). Assertion counts describe exercised
software cases, not a biological confidence estimate.

## Reproduce the current engineering

Use a **full Git clone** when running source/history-preservation checks.
The downloadable source ZIP is useful for browsing and native editing, but
contains no `.git` history.

```sh
git clone https://github.com/pratham-cloud-ctrl/Project-SCCI-RH.git
cd Project-SCCI-RH
git checkout v2.0.1
python -m venv .venv
```

Use Python **3.12**. Activate the environment with
`.venv\Scripts\Activate.ps1` in Windows PowerShell or
`source .venv/bin/activate` on macOS/Linux. Then install the recorded dependencies:

```sh
python -m pip install -r requirements-lock.txt
```

The code-execution checks also require a C11 compiler: GCC, Clang or Zig through
the documented `CC` configuration. See the
[runtime test entry](../../firmware/nrf5340/tests/check_runtime.py) and
[integration entry](../../experiments/stage6/README.md) for compiler selection.
FreeCAD and KiCad are needed for native editing/regeneration, not for these
portable receipt checks.

| Run from the repository root | Checks |
|---|---|
| `python scripts/verify_manifest.py` | Committed Git-blob checksums |
| `python scripts/verify_stage6_release.py` | Integrated manuscript/source bindings and preserved engineering |
| `python firmware/nrf5340/uart-revision/verify_revision.py` | Current image/source audit and actual C UART framing regression |
| `python scripts/stage6/verify_digital_path.py` | Both conditional application replays through the production core |
| `python scripts/verify_integrated_pcb.py` | Saved populated-board and integrated electrical checkpoint |
| `python scripts/verify_stage5_mechanics.py` | Exact mechanical sources and prior native-inspection bindings |

Checking out `v2.0.1` reproduces the immutable engineering release. The default
branch additionally contains the newer reader guides and their navigation checks.
To check those guides from the default branch, run
`python scripts/verify_viewer_navigation.py`.

The paper can be rebuilt from its [source and builders](../../manuscript/stage6/)
in the recorded environment. A target firmware rebuild additionally requires
the Nordic SDK/toolchain; see its [build instructions](../../firmware/nrf5340/uart-revision/README.md).
No test here flashes or executes a physical board.

## Evidence, authorship and next questions

- [Primary-source review](../stage6/evidence-review.md) and [reference register](../stage6/references.json): population, access method, supported finding and inference limit.
- [Original hypothesis paper](../stage6/original-hypothesis/README.md): the unchanged starting research map.
- [Contribution record](../stage6/contributions.md): student conception/steering and substantial AI assistance.
- [Defence guide](../stage6/defence-guide.md): questions and bounded exercises for understanding and extending the work.
- [v2.0.1 review](../review-v2.0.1/README.md): concrete corrections and their evidence.
- [Published release](https://github.com/pratham-cloud-ctrl/Project-SCCI-RH/releases/tag/v2.0.1): PDFs, source archive and external download checksums.

The remaining research questions concern useful spinal information, reachable
learner-specific intervention, retained benefit, physical delivery and chronic
miniaturized operation. Their explicit status lets a reviewer assess the work
without confusing a future proposal with an experiment already performed.
