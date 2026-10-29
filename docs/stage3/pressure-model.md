# Stage 3 physiological feedback mechanism

This implemented digital model investigates one bounded SCCI_RH application: external systolic blood pressure (SBP) feedback with a proposed spinal **pressor** actuator after spinal cord injury. It does not model general body automation, direct spinal pressure decoding, healthy-consumer benefit, or independent lowering of blood pressure. The target, dynamics, recruitment, faults and calibration thresholds below are chosen model inputs. Positive simulations cannot establish a treatment or a stimulation dose.

The executable model is [pressure.py](../../src/scci_rh/stage3/pressure.py); mechanism checks are in [test_stage3_pressure.py](../../tests/test_stage3_pressure.py). It uses the selected [Stage 2 contracts](../stage2/control-contracts.json), especially S2-C-004–010, and preserves the separate electrical-monitor boundary. The older release's generic MAP abstraction is not the endpoint of this model.

## Supported mechanism and assumed dynamics

Published work supports targeted epidural stimulation as a means of eliciting pressor responses and using external pressure feedback after SCI. The 2025 implant study describes afferent recruitment, intermediary excitatory circuitry and sympathetic preganglionic neurons; its selected target is the lower thoracic spinal cord. Its implant cohort and study subsets differ, and it does not validate SCCI_RH's hypothetical recording access, chosen low-current electrical profile, or normalized train-fraction response law. The study records a pressure waveform at 200 Hz and extracts beat measures at 1 Hz. Those rates and its program-adjustment latency are different quantities. [Phillips et al., Nature Medicine, 2025](https://www.nature.com/articles/s41591-025-03614-w)

Earlier experimental work motivates the target-specific feedback concept across distinct animal and human demonstrations. It does not establish every artificial dynamic coefficient used here. [Squair et al., Nature, 2021](https://pubmed.ncbi.nlm.nih.gov/33505019/)

The chosen lumped biological chain is:

**Electrical evidence → delayed normalized train dose → thresholded recruitment → activation state → added SBP → a synthetic external cardiac waveform → causal beat extraction → transport → feedback.**

All internal pressure fields are **Pa**; plots may convert using 133.322387415 Pa/mmHg. Nominal baseline/target is 120 mmHg, and a chosen 28 mmHg stand-like disturbance begins at 180 s and ends at 340 s, with 5 s ramps. These values are simulation coordinates. The target is not a clinical recommendation. The 420 s duration covers common calibration, disturbance and recovery in every condition.

Let \(d\in[0,1]\) be actual delivered dose relative to the three-profile electrical reference, \(h\) the assumed recruitment threshold, and \(x,z\) the hidden activation and added-pressure states:

\[
r(t)=\max(0,d(t-L)-h)/(1-h),\qquad
\dot x=(r-x)/\tau_a,\qquad
\dot z=(Gx-z)/\tau_p,
\]

\[
SBP(t)=P_0-D(t)+z(t).
\]

The nominal chosen parameters are \(G=36\) mmHg/full fraction, \(\tau_a=1.5\) s, \(\tau_p=6\) s, onset delay \(L=0.8\) s, release hold 2 s and \(h=0\). On the first decreasing delayed-dose transition in a falling episode, recruitment is held at least at current activation for the chosen release delay. A subsequent increasing transition ends that falling episode; later decreases can start another release hold. This is a declared artificial hysteresis surrogate, not a physiological termination model fitted to people. Removing current does not immediately remove activation or added pressure.

Activation and pressure updates use exponential first-order steps, with a causal delay queue. The default integration step is 5 ms and sensor sampling is 200 Hz. A halved-step check addresses numerical error; it does not validate the assumed model. The artificial Stage 2 stress ranges remain 0.5–10 s activation, 1–30 s response, 0.1–10 s onset and 0.1–60 s release, 0–60 mmHg positive gain and −20–0 mmHg adverse gain.

## Delivered dose is separate from the policy request

The electrical reference retains **three distinct logical profiles** at 120 Hz and offsets 0/2/4 ms, all time-shared on physical source 0. The profile uses the chosen 3 mA, 300 µs/phase, 100 µs gap, and 250 µs zero-current rearm allocation. Source service is 0.95 ms; the minimum cyclic spacing is 2 ms. These choices do not establish effective sympathetic recruitment. Changing a train fraction preserves profile identity and routing; it must not create extra pulses, reinterpret a physical-source ceiling as a profile ceiling, or increase current to conceal absent authority.

`run_study` accepts a caller-supplied electrical adapter:

```python
delivery(requested_fraction, time_s) -> {
    "effective_fraction": ...,
    "measured_fraction": ...,
    "uncertainty_fraction": ...,
    "qualified": ...,
    "reason": ...,
}
```

Each 250 ms policy interval contains 30 possible 120 Hz reference frames. A request \(u\) admits \(\lfloor30u\rfloor\) whole frames, preserving all three logical profiles in each admitted frame. The adapter receives this quantized admitted fraction, and the trace keeps policy request, admitted fraction and frame count separately. The long-timescale body model averages that delivered frame dose; it does not resolve the exact within-interval thinning pattern or its nonlinear physiological consequences.

`effective_fraction` is simulator-only delivery derived from electrical characterization, not commanded voltage/current. `measured_fraction` is the independent monitor estimate. It may exceed [0,1] because noise and gain error must not be silently clipped. An unknown estimate is `None`, never zero. The controller receives a separate monitor view containing only measured value, uncertainty, qualification and reason. No actual-dose truth field enters the controller.

The long physiological study uses an explicitly averaged pulse-dose reduction; it does not simulate 300 µs electrical transients on a 5 ms body grid. The root electrical module separately characterizes pulses, compliance, imbalance and monitoring. When no caller adapter is supplied, the module declares a reference surrogate: actual fraction 0.95×request, measured fraction 0.94×request with 0.03×request uncertainty. This is a test convenience, not an electrical verification result. Published EES often varies amplitude; SCCI_RH's assumed dependence on admitted train fraction is a separate structural hypothesis.

## External observation and causal timing

The artificial cardiac waveform has a 1 Hz beat and chosen 40 mmHg pulse excursion. It is sampled at 200 Hz with default 0.35 mmHg independent sample noise. Each completed 1 s window supplies its maximum as SBP and preserves the physical peak time, full support start/end, sequence, validity, clock uncertainty, uncertainty allocation and arrival time. This simplistic maximum extractor has a positive noise bias; paired comparisons preserve it. It is not a calibrated Finometer model or a validated clinical SBP estimator.

Nominal transport is 150 ms. The local policy ticks at 4 Hz, reusing the latest completed and transported record. Its 2 s freshness gate uses **physical peak age plus 0.5 ms clock uncertainty**, not packet arrival or heartbeat. A sample must also have consistent support/peak/arrival ordering. Replayed records can have recent arrival and sequence while retaining an old physical peak; they correctly become stale. The trace distinguishes these times and includes explicit records of transported, lost and replayed packets.

No spinal value is used to infer SBP. The Stage 2 dense reference train fails the motor neural-coverage screen, and its causal filtered archive is 100% invalid while the full train runs. A 4 Hz illustrative forward-voltage witness in the pressure trace makes an active-block invalidity visible; it is **not** a 16-channel/4 kHz AFE, ADC, artifact, source or decoder implementation. Active blocks are conservatively marked unqualified even under fractional trains. Off blocks are marked synthetic/unused; no benefit is inferred from them. The complete recording/decoder chain belongs to the motor mechanism, and any future physiological neural observation requires a separately supported hypothesis and equal-external-sensor comparison.

## Response calibration and controller permissions

Every feedback, off and oracle condition has the same finite calibration exposure: fraction 0.20 over 20–50 s, fraction 0.40 over 64–98 s, and zero otherwise until 144 s. Fresh external sensing and qualified delivery monitoring gate calibration requests. No hidden gain, delay, activation state or response state is supplied to the identification routine.

The identification data are arrived, fresh beat observations and past measured delivery. It subtracts a baseline estimated from pre-intervention beat records, then fits a first-order discrete ARX surrogate:

\[
\widehat y_{k+1}=a y_k+b \widehat d_{k-\ell},\qquad
\widehat G=b/(1-a).
\]

The lag grid is 0–10 s. Least squares selects a fit on records ending at 20–104 s; an independent chronological 105–144 s segment receives recursive predictions from that fit, without resetting each prediction to observed truth. Past monitored dose is held with earlier timestamps; future values are not interpolated backward. The identified surrogate is deliberately simpler than the two-state plant, so model mismatch can cause rejection or later poor regulation.

Qualification requires at least 100 fresh contiguous beat records and monitored doses, identifiable excitation, stable \(0\le a<0.9995\), a positive gain lower bound exceeding the chosen 3 mmHg/fraction floor and held-out recursive RMSE ≤4 mmHg. The gain interval conservatively includes a chosen 25% structural allowance, the measured-dose relative uncertainty, fitting residuals and held-out error. It is an engineering uncertainty interval, **not** a formal frequentist confidence interval. Unknown or zero-inclusive measured-dose intervals cannot qualify excitation. Rejected response models cause abstention; they are preserved as study results.

The bounded controller is a chosen nonnegative PI policy with anti-windup. Proportional weight is 0.55; the integral adds 0.025×normalized error once per newly observed beat, rather than treating repeated 4 Hz decisions as four new observations. Requests rise no faster than 0.12 fraction/s. Requests are bounded [0,1]. Above target+5 mmHg, output and integral are set to zero, and the trace records the lack of independent pressure-lowering authority. This withdrawal can leave a long response tail and recovery overshoot.

Only task target, allowed observations, estimated calibration and measured output reach operational decisions. Internal activation, actual delivery, disturbance and true SBP appear only in simulator/evaluator traces. The diagnostic oracle is a separately tagged privileged feedforward branch using true ambient pressure and gain. It is neither an operational controller nor a guaranteed optimal upper bound under saturation, threshold, delay and release dynamics; it is excluded from benefit claims.

## Faults, comparisons and interpretation

The predefined structural scenarios include nominal positive response, weak authority, no response, adverse response, inaccessible high recruitment threshold, slow onset/release, delayed sensing, missing sensing, invalid sensing, stale packet replay, sensor bias, high baseline beyond pressor-only authority, and a hidden gain reversal after calibration. They are not tuned to produce successful regulation. Response calibration valid in one context does not guarantee validity after a hidden context change.

For stale or invalid sensing, three declared variants can be compared: immediate stop; hold the last request for at most 2 s and then stop; or ramp down at 0.20 fraction/s. These suspend integration/adaptation. Unqualified electrical monitoring immediately inhibits further requests. None of these decisions is called universally safe. The model continues activation, pressure and disturbance after request withdrawal, so loss of support and remaining response are visible. A physical monitoring, power or route fault can require more detailed electrical interruption behavior; this physiological model does not invent a corrective balancing pulse.

Each seed preserves the same sensor noise, calibration, target, disturbance and hidden scenario across feedback/off/oracle. Primary operational contrasts are feedback versus off after equal calibration, disturbance SBP RMSE, dip, recovery overshoot, fraction of evaluation within the chosen ±5 mmHg band, delivered reference-train equivalent duration, and unqualified/fallback duration. Oracle is only a diagnostic. Outcomes are in Pa in the JSON; comparison scripts convert for display.

Nominal simulations can improve low-pressure error while creating a substantial recovery overshoot. Weak/no/adverse cases can reject calibration. Delayed sensing can block the calibration protocol altogether. Bias can produce incorrect support despite fresh packets. A high baseline remains unreachable with a pressor-only actuator. These are meaningful negative findings under the chosen model, rather than defects to conceal by altering biology or targets. More seeds quantify Monte Carlo variability of this simulation; they do not establish the biological response law, clinical robustness, healthy-consumer use, chronic implantation or safety.

## Checks and remaining boundary

The mechanism tests verify physical freshness versus arrival, paired calibration/noise, absent/adverse response abstention, delivered-dose versus command effects, unknown-monitor handling, finite fallback distinctions, nonnegative control, retained recovery overshoot, 200 Hz→1 Hz→4 Hz rate separation, conservative neural invalidity, step convergence, JSON finiteness and the oracle/information boundary. The integrated electrical adapter must also be tested with monitor overshoot and interval uncertainty.

Remaining studies should vary response parameters and context jointly, test support-loss nadirs under each fallback, evaluate bias and unreachable conditions, and report structural families separately from paired-seed uncertainty. A Stage 3 paper may report these mathematical results. A real device, retained learning, clinical pressure regulation or universal autonomous body control is not established by them.
