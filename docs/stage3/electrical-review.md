# Stage 3 electrical mechanism review

8 October 2026. Independent review of the reduced electrical plant, application
adapters and numerical cross-checks. This review assesses the implemented digital
model; it does not qualify an implant or a human stimulation profile.

## Review boundary

Reviewed [electrical.py](../../src/scci_rh/stage3/electrical.py),
[electrical tests](../../tests/test_stage3_electrical.py),
[study runner](../../scripts/run_stage3_studies.py),
[ngspice cross-check](../../scripts/stage3_ngspice_check.py), the
[mathematical specification](mathematical-specification.md), and the selected
[Stage 2 contracts](../stage2/control-contracts.json).

The load is an assumed linear series resistance and lumped parallel pair
capacitance/leakage. The current-source compliance abstraction, switched passive
recovery and independent quantized observations are distinct from neural
recruitment, electrode chemistry, tissue fields and circuit servo dynamics.

## Findings and disposition

| ID | Finding | Required behavior | Disposition |
| --- | --- | --- | --- |
| E3-R-01 | A failed post-pulse recovery originally erased an already delivered body dose. | Preserve actual and measured delivery; failure affects subsequent admission. | Corrected before this review; verified in the current adapter and regression test. |
| E3-R-02 | The adapter returned `inhibit_next` but did not enforce it. | Latch the affected physical source; future requests deliver zero until an explicit independent simulator-session boundary. | Corrected during this review; the test preserves first-pulse dose, inhibits the second, separates source IDs and checks explicit session reset. |
| E3-R-03 | A single command-based uncertainty bound did not cover an increased recharge phase or some unsaturated prepolarized first phases. | Report separate valid cathodic/anodic/net measurement bounds; preserve the old expression only within its stated nominal domain. | Corrected during review; separate observed-charge bounds and adversarial regression witnesses pass. |
| E3-R-04 | Qualification checked only cathodic charge; an increased recharge phase could exceed the delivered phase cap. | Check both absolute measured phase charges plus their own uncertainty before admitting another pulse. | Corrected during review; a 12 microcoulomb recharge witness is now unqualified. |
| E3-R-05 | NaN monitor gain or offset could pass allocation comparisons. | Reject nonfinite observation parameters explicitly. | Corrected during review; both nonfinite-input witnesses are rejected. |

The explicit `begin_session` operation represents a fresh independent simulated
experiment. It is not runtime recovery of uncertain charge. Real requalification
must use monitored electrical state. Motor experiments must call the session
boundary only between independent calibration/practice/assessment simulations,
so a failed source cannot either resume silently or contaminate another paired
study arm.

The corrected controller-visible uncertainty uses each measured signed phase
integral, inversion of the 2% gain allocation, offset/quantization over the actual
sample support, and a conservative two-edge allowance with a **chosen complete
waveform peak bound of 25 mA**. The net-charge bound adds the two phase bounds.
The tighter Stage 2 rectangular-command calculation remains separately named as
a nominal witness; it is no longer supplied as the general observation bound.
This broader bound may reject response calibration or reduce declared authority.
Those outcomes must be retained rather than bypassing uncertainty to restore a
positive result.

The 25 mA full-waveform premise is an explicit model assumption. Unsaturated ADC
samples alone cannot establish it between apertures. Saturation invalidates the
charge-bound qualification; a numeric integral must not then be interpreted as
known delivered charge. A physical peak guard and its response still need circuit
verification.

## Numerical evidence

Both independent sweeps are rerunnable with
[stage3_electrical_sweep.py](../../scripts/stage3_electrical_sweep.py). The committed
[electrical-sweep.json](../../results/stage3/electrical-sweep.json) records every
case, disclosed PCG64 seed, solver settings, input, error and exclusion. Run
`python scripts/stage3_electrical_sweep.py --check results/stage3/electrical-sweep.json`
from the repository root to compare without rewriting the receipt. The ODE seed
is 5 and the current-monitor seed is 514. Numerical reproduction uses relative
tolerance 2e-6 and absolute tolerance 1e-11; each study's acceptance criteria below
are separate from those portability tolerances.

The analytical interval integrator was independently compared with a numerical
ODE solver over 150 fixed-seed random intervals with series resistance
500–2,000 ohm, pair capacitance approximately 0.5–12.6 microfarad, leakage
1 kiloohm–1 megaohm, signed current commands, initial polarization −30 to +30 V,
8/16/28/40 V usable compliance and 50–1,000 microsecond intervals. The largest
polarization discrepancy was approximately 1.47e-7 V; polarization, charge and
series-energy comparisons passed the review tolerances of 2e-7 V, 5e-11 C and
1e-8 J respectively. This is numerical
verification of the chosen equations, rather than validation of their load values.

The fresh local ngspice 46 run reproduced all four comparisons in
[ngspice-crosscheck.json](../../results/stage3/ngspice-crosscheck.json): ideal
current drive with an open interphase gap, with and without passive recovery,
at maximum timesteps 0.5 and 0.1 microsecond. All passed the chosen 2 microvolt
criterion. Maximum waveform difference was approximately 1.08e-9 V; final-voltage
refinement differences were at most 1.47e-11 V. The missing `spinit` warning is
recorded; each scripted netlist supplies its model and numerical options.

The ngspice comparison does not test compliance clipping. The independent ODE
comparison and committed compliance regression address that separate analytical
branch. Neither comparison tests a physical current-source servo, protection
latency, nonlinear interface chemistry or biological response.

The current phase-window code uses the stored actual `gap_s`, so an arbitrary
interphase gap does not silently become the nominal 100 microsecond gap.
Interrupted recharge creates no second-phase observation window. Timer phase
metadata and sampled analog current remain separately identified.

After the corrections, all 12 committed electrical tests pass. An additional
fixed-seed review sampled 500 combinations of load, rail, initial polarization,
phase width, interphase gap, recharge gain and bounded monitor error. Of these,
493 had unsaturated monitoring and satisfied the explicitly assumed full-waveform
25 mA bound. Both phase errors lay within their respective new uncertainty;
largest bound utilization was approximately 0.60. The other cases were outside
the qualifying assumptions, rather than evidence for an unrestricted bound.

The increased-recharge adversarial case had an anodic error approximately
3.17e-7 C. Its corrected bound is approximately 4.62e-7 C. A separate 16 mA,
500 microsecond pulse with 1.5 recharge gain delivers 12 microcoulomb in the
anodic phase and is now unqualified despite a compliant cathodic phase and a
small quantized residual. These witnesses address the two-phase gate independently
of nominal reference success.

## Application reductions and remaining integration

Motor delivery preserves commanded, measured and actual cathodic charge as
separate quantities. Actual delivery belongs to the simulator/body evaluator;
the controller receives qualified measurement evidence and its uncertainty.
Post-delivery failure cannot retroactively make actual charge zero.

Pressure uses a **frozen offline characterization** of an isolated 3 mA,
300 microsecond, 24 V reference pulse. An unqualified characterized profile is
rejected before admission. Every 250 ms interval admits whole frames out of
30 possible 120 Hz frames; each admitted frame preserves the three distinct
logical profiles at offsets 0/2/4 ms. Actual and measured charge ratios scale
an explicitly averaged physiological input. The adapter is not live electrical
monitoring of every pulse throughout a train.

The reset-route assumption in isolated pulse characterization does not establish
continuous shared-source/return polarization recovery, route ownership,
admission/rearm timing or power transients. Those properties must be integrated
with the circuit and sequencer in Stage 4. Pressure fraction averaging also does
not establish equivalence to amplitude modulation or a particular physiological
response under train thinning.

Readiness is a chosen open-terminal measurement bound after the passive short
has been released. It is distinct from recording recovery and from chemistry.
ADC sampling and a finite waveform assumption cannot exclude arbitrary unseen
inter-sample spikes; independent peak protection remains circuit work. Device
ratings, chronic safety, human efficacy and retained learning are not established
by this review.
