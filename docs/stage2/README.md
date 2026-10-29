# Stage 2: quantitative SCCI architecture

**8 October 2026 - provisional digital design, with explicit rejected cases.**

The reference system now has specified contacts, conversion, local computing,
programmable output, independent delivery monitoring, data contracts, energy
allocations and preliminary mechanical envelopes. This stage calculates resource
budgets. It does not deliver finished implant schematics, populated boards or
biological validation. Those are later stages of the [overhaul programme](../overhaul-plan.md).

| Read or inspect | Purpose |
|---|---|
| [Illustrated architecture brief](../../output/pdf/SCCI_RH_stage2_architecture_budgets.pdf) | Selected design, plots, admitted/rejected reference cases and package allocations |
| [Selected design and decisions](selected-design.md) | What changed, why, and the conditional operating envelope |
| [Acquisition and computation](acquisition-and-compute.md) | Signal/noise, causal filtering, channel topology, ADC/SPI, memory and cycle budgets |
| [Stimulation and biological access](stimulation-and-access.md) | Published anchors, contacts, waveform assumptions, compliance, charge and recruitment limits |
| [Timing and control](timing-and-control.md) | Information age, artifact gaps, scheduling and stale-sensing behavior |
| [Machine-readable contracts](control-contracts.json) | Eleven versioned signal/estimate/command/monitor/assessment contracts |
| [Mechanical allocation](mechanical-allocation.md) | Parametric STEP envelopes and nominal fit; no anatomical or hermetic qualification |
| [Stage 2 exit review](exit-review.md) | Goal alignment, corrected findings, twelve completion criteria and bounded handoff |
| [Functional port allocation](functional-port-map.csv) | 36 logical functions matched to preliminary CAD port labels; not a pin/net/anatomy map |
| [Calculated budgets](../../results/stage2/budget-summary.json) | Reproducible numerical results, including failures |
| [Aggregated design inputs](system-design.json) | Selected system configuration in SI units, tied to audited input dossiers |

Primary provenance is recorded in [electrical](electrical-source-audit.csv),
[biological/electrode](biological-envelope-audit.csv) and
[power/system](system-source-audit.csv) audits. Manufacturer specifications are
capacity witnesses with their actual conditions; they do not make catalog parts
qualified implant components. Numerical choices and calculated quantities remain
distinct from measurements.

The [verification progress table](verification-progress.csv) distinguishes
completed analytical cases from open identification, circuit and populated-CAD
work. In particular, S1-V-204 functional authority is only partially specified
until Stage 3 identifies and tests uncertain response bounds.

Run the budgets with `python scripts/run_architecture_budgets.py` from the repository
root. Use `--check` to compare against committed results. The Stage 2 verifier also
checks input agreement, interface IDs, failure cases and review receipts. Scientific
figures and the PDF can be rebuilt with `python scripts/build_stage2_brief.py`.
CAD has its own build123d invocation in the mechanical note.

The next stage builds the computational mechanism using **observed contact
signals**, identified learner responses and physically bounded output. It will
compare expert-informed versus learner-only policies, neural-plus-external versus
external-only sensing, and assisted performance versus unassisted retention.
The original subsystem models remain historical references.
