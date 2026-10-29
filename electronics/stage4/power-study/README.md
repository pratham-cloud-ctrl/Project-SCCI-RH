# SCCI_RH-S4-PWR quantitative study

This package binds the actual six native KiCad connectivity manifests to a finite
electrical and resource budget. It is a digital reference. Its load caps,
efficiencies, battery derating, source resistance, capacitor derating and thermal
paths are declared assumptions. The results do not establish measured device
power, converter stability, implant temperatures or a compact implant package.

The central result is a **conditional 2.615 W active allocation**, corresponding
to **5.886 hours** from the selected external 19.24 Wh battery when 80% of its
nominal energy is assumed usable. The reference pack alone is **99 g and
67 × 37 × 21 mm**. A continuously implanted, compact version requires a different
power and packaging implementation; the current lumped thermal cases fail the
selected 2 K rise allocation. The future SCCI mechanism remains a conditional
concept rather than a claim that this reference board fits inside the body.

The design and assumptions are explained in
[power-budget.md](../../../docs/stage4/power-budget.md). The
[native KiCad package](../power/README.md) supplies the circuit; its full primary
component and sequencing review are separate from these equations.

## Reproduce and audit

Run from the repository root with Python 3.10 or later; these scripts use only
the standard library:

```text
python electronics/stage4/power-study/budget_study.py
python electronics/stage4/power-study/verify_budget.py
python electronics/stage4/power-study/sequence_study.py --check
python electronics/stage4/power-study/verify_integration.py
```

Both commands are read-only by default. The first reconstructs the saved
calculation and checks every field against [budget-results.json](budget-results.json).
The second independently reads the saved data, source manifests and component
counts; it does not import the producer. Its checks cover current sums, rail
power, loss conservation, isolated-rail loading, input load lines, capacitor
charge and energy, runtime, thermal arithmetic and resource accounting.

Only intentional regeneration uses `budget_study.py --write-results`.
`verify_budget.py --write-report` saves [budget-verification.json](budget-verification.json).
Regenerate after an intentional native change, then independently recheck. A
hash mismatch is a failed binding, not permission to overwrite results silently.

## What the saved cases mean

- Recording/observe and restricted stimulation use every nonstimulation rail at
  its declared load cap. They are allocation cases, not typical-current estimates.
- Stimulation adds two aligned 3 mA sources, two 200 microsecond phases at 100 Hz.
  This example does not implement the broader 48 V/20 mA concept envelope.
- The supervision-only row is a **lower bound for the supervisor loads**. It
  excludes disabled host feedthrough and leakage. LT8330 boost outputs retain a
  path from their input through the inductor and diode even when disabled.
- Converter efficiency is varied explicitly. The isolated module's 81% typical
  full-load efficiency is not used as a low-load guarantee. Its 60 mA typical
  no-load current is allocated as an additional 0.3 W; loaded LDO ground current
  is allocated at 1 mA per device.
- A 30 microfarad effective 24 V reservoir loses 80.6 mV for two aligned
  200 microsecond phases with no converter replenishment and the selected ESR.
  Smaller-capacitor cases that cross the selected rail boundary remain rejected.
- Capacitor startup energy includes 423 populated capacitors in all six packages.
  Its selected charge-time slopes are not peak inrush predictions or native
  sequencing guarantees. The 2 A fuse is not a current clamp.

The saved failures are part of the result: untrimmed AFE rail startup can fail
closed; the old 100 mA cell cap is exceeded; 450,000 conversions/s do not fit two
ADS8866 devices; continuous 4 ksample/s framed raw data do not fit a 1 Mbit/s
service; and all selected lumped thermal cases exceed 2 K. Explicit selected or
trimmed rail assumptions let the conditional digital reference proceed without
relabeling these failures as validated performance.

The separate [sequence study](sequence-results.json) audits 1,536 native gate
outputs across all 256 input combinations, 12 finite histories/182 assertions,
and 320 threshold/divider KCL corners. The [integration audit](integration-verification.json)
checks 32 new power wires and the combined 134-wire plan against actual XML and
pin manifests, including open-drain fault wiring and separated ground domains.
Neither ideal event logic nor a gross reference window earns physical shutdown
latency or precision calibration. The 6.4 V electrical calculation does not
grant cold start below the battery window's qualified rising threshold.

![Power and runtime](figures/power-and-runtime.png)

![Finite retained constraints](figures/power-constraints.png)
