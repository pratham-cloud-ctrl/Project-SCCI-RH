# Repository map

[Explore](README.md) · [Theory](theory.md) · [CAD](cad.md) · [Electronics](electronics.md) · [Firmware](firmware.md)

This map separates the current reading path from the project's preserved development history. Engineering files retain their original locations so source hashes, native references and earlier results remain traceable.

## The current project

| What you want | Where to go |
|---|---|
| Understand the project in a few minutes | [Explore hub](README.md), then [theory](theory.md) |
| Read the complete illustrated account | [Integrated 29-page manuscript](../../output/pdf/Project_SCCI_RH_Integrated_Manuscript.pdf) |
| Inspect mechanical assemblies without software | [CAD gallery and downloads](cad.md) |
| Open current KiCad boards and schematics | [Electronics guide](electronics.md), then the [eight-board index](../../electronics/stage4/integrated-pcb/BOARD_INDEX.md) |
| Find the corrected target firmware | [Firmware guide](firmware.md), then the [UART revision](../../firmware/nrf5340/uart-revision/README.md) |
| Reproduce the digital integration | [Integration experiment](../../experiments/stage6/README.md) |
| Check claims, sources and assumptions | [Evidence review](../../docs/stage6/evidence-review.md) and [requirement dispositions](../../docs/stage6/requirements-claims-trace.csv) |
| Understand the student's and AI's contributions | [Contribution record](../../docs/stage6/contributions.md) |

```text
Project-SCCI-RH/
├── docs/explore/                  Viewer guides and this map
├── manuscript/stage6/             Editable paper, figures and builders
├── output/pdf/                    Integrated manuscript PDF
├── electronics/stage4/
│   └── integrated-pcb/            Current eight-board design and exports
├── firmware/nrf5340/
│   ├── core/                     Portable production control logic
│   ├── app/                      Target application source
│   └── uart-revision/            Current correction, image and checks
├── cad/stage5/
│   ├── reference/                True-scale reference chassis sources
│   ├── future-interface/         Conditional compact implant identity
│   ├── harness/                  Mating interfaces and route planning
│   ├── drawings/                 Mechanical review PDF
│   └── renders/                  Assembled and exploded views
├── experiments/stage6/            Integrated replay instructions
├── results/stage6/                Replay outputs and verification
├── docs/stage6/                   Evidence, claims and release rationale
├── scripts/                      Builders, inspectors and verification
└── provenance/                   Source identity and manifests
```

## Preserved history

[Stage 1](../../docs/stage1/README.md), [Stage 2](../../docs/stage2/README.md) and [Stage 3](../../docs/stage3/README.md) retain the reasoning that led to the current architecture. Original negative results remain part of the evidence. Earlier CAD under `cad/stage2/` and early electronics revisions describe dated allocations; use the current viewer guides for the delivered assembly.

The [original 28-page hypothesis paper](../../docs/stage6/original-hypothesis/README.md) is an unchanged research input. It is distinct from the updated integrated manuscript. The [v2.0.1 review](../../docs/review-v2.0.1/README.md) records subsequent corrections; old image checkpoints are preserved alongside the corrected firmware.

[v1.0.0](https://github.com/pratham-cloud-ctrl/Project-SCCI-RH/releases/tag/v1.0.0) is a historical subsystem release. Current whole-project release downloads are on the [release page](https://github.com/pratham-cloud-ctrl/Project-SCCI-RH/releases/latest). A source ZIP provides files; a full Git clone also provides the history needed for Git-blob verification.

`site/` and `media/` retain earlier presentation material. Website/video revision was parked; these directories are not the current project entry. Local `tmp/`, build environments and recovery backups are working material, not published deliverables.
