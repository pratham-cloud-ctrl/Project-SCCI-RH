# Observed response applicability at the fixed motor profile

**8 October 2026. Digital model verification; no human recruitment, selective spinal control or learning efficacy is established.**

This study closes part of the response-domain gap between the original individual full-train calibration and the proposed learner-specific controller. It asks whether an observed map remains useful for lower whole-pulse densities, withheld route combinations and a changed response context. It keeps the delivered-charge uncertainty, wrong-sign and null-response cases visible.

The study uses the existing [motor capture/calibration mechanism](../../src/scci_rh/stage3/motor.py) and [reduced electrical adapter](../../src/scci_rh/stage3/electrical.py). The [new response-domain module](../../src/scci_rh/stage3/response_validation.py) contains the observable identification and finite applicability tests. It does not change the original motor studies.

## Frozen experiment and information boundary

There are four subject seeds, two delivery branches and three biological variants: nominal, no authority and adverse negative-route sign. The conditional branch uses the declared 5 ms onset and assumed nominal delivery. The actual branch uses nominal 35 ms onset and the implemented independent electrical monitor. Both use the separately verified midpoint body scheme at 2.5 ms, while decisions remain 200 Hz and complete stimulation profiles remain at most 40 Hz per source.

The profile is fixed at the existing illustrative 3 mA, 200 microseconds per phase and 24 V command. These are model inputs, not a treatment recommendation. This study provides no validation for changing current, phase width, anatomical access or profile timing.

Each 2.5 s rest capture applies its predetermined train from 0.25 to 2.0 s. The observed baseline uses physical position support from 0.05 to 0.20 s. The held-out plateau uses physical support from 1.50 to 1.90 s. External packet availability remains distinct from physical support. Plasticity is disabled.

Training uses four individual routes at full density. Subsequent recordings use six patterns: individual positive and negative routes for each source, both positive routes together, and left positive with right negative. Each pattern is tested at quarter, half and full requested density. A sigma-delta selector admits whole fixed profiles only on 25 ms frame boundaries. A finite 70-frame active interval admits 17 quarter-density, 35 half-density or 70 full-density frames; the fractional remainder does not create a catch-up pulse.

Every training, envelope-estimation, same-context held-out and changed-context capture has a distinct recording ID. The private subject seed stays the same within a study. Thus body/lead-field identity is shared while the sensor-noise realizations differ. Recording IDs are not independent human subjects.

Only these records enter response fitting and residual assessment:

- Observed external position, physical support, availability and validity.
- Declared command frame, source and signed route identity.
- Independently monitored phase charge, uncertainty and its qualification name.

Actual charge, hidden recruitment threshold, hidden response matrix and simulator position are retained in explicitly named evaluator fields. The observable schema rejects those fields. The assumed-monitor quality `ASSUMED_NOMINAL` is conditionally usable by the artificial study; it does not become verified electrical evidence.

## Effective map and delivery uncertainty

Four empirical route columns describe observed plateau displacement divided by measured reference-dose fraction. The reference charge is 600 nC for the selected profile. The fit never subtracts the simulator's hidden recruitment threshold. It estimates the combined effective response at this one profile.

The map's uncertainty propagates the predeclared 9.5 mm calibration position allowance and the independent dose interval through the observed denominator. Coherent systematic charge uncertainty is averaged as an interval; repeated pulses do not reduce it as square-root sample noise. A positive/negative route pair forms the same two-source signed authority representation used for a smallest-singular-value margin. Null, inconsistent-sign, monitor-invalid and nonpositive authority margins remain unqualified.

Predictions use only monitored charges from complete frames preceding the observation's physical support. A trailing 250 ms held-frame dose history is multiplied by the frozen empirical route map. The associated correction allowance includes map uncertainty times measured dose, map magnitude times current monitor-dose uncertainty **and the product of map and dose uncertainty**. The last term is necessary when both uncertain factors vary together. An independent enumeration of product-interval corners verifies the implemented bound. The independent pulse adapter remains an offline waveform characterization; this study does not qualify live charge-packet transport or continuous routing.

## Residual envelopes and withheld checks

For each finite pattern/density pair, one new capture estimates a residual envelope. Its lower and upper components are the observed residual extrema expanded by the propagated systematic allowance. A second recording tests that frozen envelope in the same response context. A third recording uses the same frozen map and envelope under a private response-context change: 65% gain and declared asymmetric 40% cross coupling. Those context parameters are never supplied to identification or used to refit the held-out prediction.

The correction allocation is frozen at **25 mm**. The separate empirical joint-coverage allocation is frozen at **95%** of the withheld plateau samples. Both are engineering gates selected before the batch; neither is a physiological tolerance. Applicability requires a qualified map and monitor, an envelope within 25 mm, at least 95% observed joint coverage and no observed held-out residual above 25 mm.

The samples are temporally correlated. Empirical extrema and observed coverage are not confidence intervals, a guaranteed error bound or population coverage. A small null-response residual cannot qualify missing control authority. A changed-context pass means only that this specific withheld capture met the declared finite gates. It does not establish universal posture adaptation or an online context-change detector.

Independent review identified a missing product term in the first implementation of the map/input uncertainty allowance. The interval-corner test was added, the bound corrected and the complete batch regenerated before integration. Preliminary envelopes from the first-order-only expression are superseded by the final receipts.

The original calibration anchor receives 24 s of exposure. The separate four-route fit adds 10 s. Envelope estimation, same-context held-out testing and changed-context testing each add 45 s. These are additional mechanism-verification resources, not secretly supplied to any original learning arm.

## Results and reproducible artifacts

The full batch contains 24 studies and 432 finite pattern/density checks in each held-out context. The [readable receipt](../../results/stage3/response-validation/response-domain-summary.json) reports every map, interval, observed coverage and rejection reason. The [compressed raw receipt](../../results/stage3/response-validation/response-domain-raw.json.gz) retains all position/monitor/command records, pulse witnesses and individual residual samples.

| Delivery branch and biological variant | Qualified observed maps | Same-context recordings meeting finite gates | Changed-context recordings meeting finite gates |
|---|---:|---:|---:|
| Conditional assumed delivery, nominal biology | 4/4 | 63/72 | 34/72 |
| Conditional assumed delivery, no authority | 0/4 | 0/72 | 0/72 |
| Conditional assumed delivery, adverse negative-route sign | 0/4 | 0/72 | 0/72 |
| Actual nominal delivery, nominal biology | 0/4 | 0/72 | 0/72 |
| Actual nominal delivery, no authority | 0/4 | 0/72 | 0/72 |
| Actual nominal delivery, adverse negative-route sign | 0/4 | 0/72 | 0/72 |

Every quarter- and half-density nominal conditional case met the finite gates. Full-density mixed routes exceeded the 25 mm envelope allocation in all four seeds. Seed 0's full-density right-negative route also exceeded it: 25.359 mm. Thus passing a narrow mixed-route residual check does not by itself earn bounded correction authority.

Among the **63 admitted same-context recordings**, the worst observed joint and component coverage was **100%**, and the largest observed residual was **7.942 mm**. Among the **34 admitted changed-context recordings**, the worst observed joint and component coverage was **96.25%** (77 of 80 plateau samples), and the largest observed residual was **23.162 mm**. The 96.25% case was seed 0, right-negative route at half density. Across all changed-context cases, observed coverage could fall to **0%**.

These figures describe the recorded samples after applying the declared gates. Acceptance of 34 changed-context captures does **not** validate transfer, a coverage guarantee, unseen response contexts or continuous adaptation. The receipt label `applicable_within_tested_domain` means that this one independently recorded finite pattern/density capture met the predeclared diagnostics; it does not authorize future use without context and observation qualification. The actual branch retains its negative authority margin, even though the independent monitor reports delivered profiles.

The executable receipt is authoritative for the final counts. An accepted density or route combination does not qualify an untested density, different stimulation profile or dynamic task. All null and adverse maps remain rejected even when their prediction residuals are small.

```text
python scripts/stage3_response_validation.py --output results/stage3/response-validation/response-domain-raw.json.gz --summary-output results/stage3/response-validation/response-domain-summary.json --jobs 2
python scripts/stage3_response_validation.py --check results/stage3/response-validation/response-domain-raw.json.gz --summary-check results/stage3/response-validation/response-domain-summary.json --jobs 2
```

The runner records only its actual source dependencies, checks that they remain unchanged throughout generation, uses fresh electrical session state per capture, writes deterministic gzip and supports a separately labeled two-study smoke replay. Numeric reconstruction uses `rtol=2e-8`, `atol=1e-11` and compares all raw witnesses.

The [ten mechanism tests](../../tests/test_stage3_response_validation.py) check complete-frame admission, observed-only fitting, prior-dose causality, physical-support/route rejection, independent held-out assessment, null/adverse behavior, actual precision rejection, post-delivery unqualified evidence and independent joint-uncertainty interval corners. They establish those software/model boundaries only.

## Remaining scope

This establishes a finite resting fixed-profile applicability study. It does not identify axonal recruitment, sensory effects, muscle forces or electrode selectivity. Dynamic practice, unseen cadence/posture, online context-change detection, current/width generalization and continuous circuit/source/artifact supervision remain separate requirements. The proposed cue controller may consume a qualified map only within an explicitly tested and independently checked domain; this study does not itself grant unrestricted correction authority.
