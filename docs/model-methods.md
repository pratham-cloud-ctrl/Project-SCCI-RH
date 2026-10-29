# Synthetic model methods and reproducibility

**Status:** digital engineering studies with generated data. No human or animal measurements, clinical validation, or demonstrated spinal decoding are reported. The models explore consequences of stated assumptions. The motor model does not establish that spinal signals contain sufficient information or that stimulation produces learning. The pressure model does not identify a human physiological plant or a stimulation-dose response.

## Reproduction and evidence files

From the repository root, with Python 3.10 or newer, NumPy and Matplotlib installed:

```sh
python scripts/run_studies.py
python -m unittest discover -s tests -v
python scripts/build_firmware.py  # GCC, Clang or Zig on PATH; --cc also supported
python scripts/run_adapter.py     # Calls the built C shared library through ctypes
```

`scripts/run_studies.py` deterministically generates all model CSV/JSON files and both PNG/SVG scientific figures. It uses 40 paired seeds, 24000–24039, for primary comparisons and the pressure robustness cases. Each motor sensitivity cell uses the first 12 seeds. Pairing means a given seed draws identical synthetic learner or plant parameters, disturbances and sensor noise across compared policies. The figures are generated from those arrays, not manually drawn numerical curves.

`results/study_metadata.json` records all default parameters, software versions, seeds and pressure case overrides. `results/summary.json` contains the aggregates. CSV files retain trial-level parameters and outcomes; `motor_sessions.csv` additionally retains each practice session. Three full example traces use seed 24000: `motor_example_trace.csv`, `pressure_example_trace.csv`, and `pressure_fault_trace.csv`.

Mean effects have percentile bootstrap 95% intervals, using 2,000 resamples and bootstrap seed 20261007. Paired effects resample paired learner/plant outcomes. These intervals describe variability across **the selected synthetic parameter distributions**. They exclude uncertainty about biology, electrode placement, causal learning mechanisms, sensor validity, and model structure. They are not confidence intervals on a real treatment effect.

## A. Expert-informed rhythmic practice

### Generated signals and causal phase estimator

The expert target is the analytic trajectory \(y^*(t)=\sin\phi(t)\), not a recorded expert neural waveform. The phase evolves at \(f(t)=1+0.03\sin(2\pi\,0.07t+\phi_0)\) Hz. Two artificial quadratures are

\[
z_c[n]=\cos\phi[n-d]+\epsilon_c[n],\qquad
z_s[n]=\sin\phi[n-d]+\epsilon_s[n],\quad
\epsilon_{c,s}\sim\mathcal N(0,\sigma_z^2).
\]

At a 10 ms timestep, the causal estimator averages the complex signal \(z_c+jz_s\) over five samples, unwraps its angle, estimates frequency using the angle difference over the previous one second, and clips that estimate to 0.5–1.5 Hz. It predicts current phase using the declared sensor latency plus the moving-average group delay:

\[
\hat\phi[n]=\theta[n]+\hat\omega[n]\bigl(\hat d+0.02\text{ s}\bigr).
\]

Nominal true and assumed latency are 80 ms; quadrature noise SD is 0.16. The first two seconds of each 12 s practice session are excluded from scoring to allow estimator warm-up. Sensitivity sweeps use noise SD 0.08/0.25/0.60 and **known** delays 20/150/400 ms. A separate negative control uses true latency 400 ms but assumed latency 80 ms. The latter is needed because an exactly known delay is an optimistic assumption.

These artificial channels demonstrate an estimator's behavior when usable rhythmic information is supplied. Their amplitudes are normalized; they are not electrode voltages. No equivalence to descending motor commands, intention, reflex state, or an identifiable spinal recording channel is assumed. Real signals may have correlated noise, drift, stimulation artifacts, competing rhythms, weak observability and dropouts that this model does not simulate.

### Learner calibration and assistance

Learner skill is a scalar surrogate \(s\). The unassisted movement template is

\[
y_0(\phi,s)=A(s)\sin\bigl(\phi-\ell(s)\bigr),\quad
A(s)=1-0.45e^{-s},\quad \ell(s)=0.35e^{-s}.
\]

The synthetic learner response gain \(\gamma\) is drawn uniformly from 0.45–1.65. Calibration applies four abstract command levels \(x=(-0.6,-0.3,0.3,0.6)\), receives \(\gamma x\) plus independent SD 0.025 measurement noise, and estimates a least-squares gain clipped to 0.25–2.0. This is an assumed accessible linear response, not a validated spinal recruitment model.

The calibrated policy uses

\[
u(t)=\operatorname{clip}\left[\frac{a}{\hat\gamma}
\{\sin\hat\phi(t)-y_0(\hat\phi(t),s)\},-0.8,0.8\right],\qquad
y_a=y_0+\gamma u,
\]

where \(a=0.65\). These commands are abstract signed trajectory corrections. They are **not currents**, and no feasible spinal stimulation map is derived. The learner template and its current skill are available to this model; inferring them reliably in practice would require independent identification. This information access makes the model optimistic.

Policy controls are:

| Policy | Phase | Response gain | Purpose |
|---|---|---|---|
| Unassisted | Unused | Unused | Same learner and practice without intervention |
| Calibrated | Causal latency prediction | Noisy learner calibration | Main conditional architecture |
| Uncalibrated | Delayed phase; no prediction | Fixed gain 1 | Joint calibration/latency ablation, **not** an isolated calibration test |
| Shuffled | Randomly permuted estimated phase | Learner calibration | Negative control for relevant timing |
| Oracle | True phase | True gain | Upper reference bound under the same assistance magnitude |

### Learning and retention assumptions

Each learner draws initial skill \(s_0\sim U(0.12,0.25)\) and baseline practice rate \(\lambda\sim U(0.07,0.10)\). Over each scored session, helpful alignment is

\[
q_k=\operatorname{clip}\left(\frac{E_{0,k}-E_{a,k}}{E_{0,k}},-1,1\right),
\quad E_{0,k}=\langle(y^*-y_0)^2\rangle,
\quad E_{a,k}=\langle(y^*-y_a)^2\rangle.
\]

The practice update is

\[
s_{k+1}=s_k+\lambda\left(1-\frac{s_k}{3.2}\right)(1+\beta q_k).
\]

**This equation explicitly assumes that helpful assistance changes intrinsic learning through \(\beta\). It is not a discovered learning mechanism.** The nominal value 0.8 is a hypothetical scenario; no data fit, literature-derived estimate, or optimized target-speed claim is made. Sweeping \(\beta=0,0.4,0.8,1.2\) reveals dependence on this assumption. Setting \(\beta=0\) makes intrinsic learning exactly identical under assistance and no assistance, even while online performance improves. Negative alignment slows intrinsic learning in the assumed model; a positive learning benefit is therefore not automatic.

Unassisted RMSE is evaluated analytically over phase, including a motor noise floor \(\sigma_m=0.025\):

\[
R(s)=\sqrt{\tfrac12\{A(s)^2+1-2A(s)\cos\ell(s)\}+\sigma_m^2}.
\]

The model simulates 45 practice sessions. An illustrative acquisition threshold is \(R\le0.075\). It has no clinical or university assessment meaning. Retention is a separate assistance-free test at \(s_{\mathrm{ret}}=0.97s_{45}\). The 0.97 factor is another assumed retention rule; no actual elapsed time, sleep consolidation or forgetting mechanism is predicted. Online assisted RMSE is scored before that session's skill update, while the saved unassisted curve is evaluated after the update.

Acquisition speed is the paired ratio of sessions to this threshold. It is computed only where both policies cross; the output explicitly records censoring. The nominal comparison has 40/40 pairs reaching the threshold. The shuffled policy has only 29/40 crossing within 45 sessions; its conditional crossing-time mean must not be compared without disclosing that censoring.

### Motor outcomes and interpretation

| Outcome | Synthetic result |
|---|---:|
| Baseline retained RMSE | 0.05060 normalized amplitude |
| Calibrated retained RMSE, assumed β=0.8 | 0.03651 |
| Paired retained-error reduction | 27.61%; bootstrap interval 26.73–28.50% |
| Baseline / calibrated threshold sessions | Mean 27.65 / 16.425 |
| Mean paired threshold-speed ratio | 1.685; bootstrap interval 1.674–1.696 |
| Maximum retained difference when β=0 | Exactly 0 |
| Shuffled retained RMSE | 0.07185 |
| Unmodeled-latency retained RMSE | 0.16293 |
| Nominal / unmodeled-latency phase RMSE | 0.07990 / 2.01218 rad |

The 1.685 value illustrates a model in which learning benefit is already inserted into the update law. It supplies neither evidence nor a prediction that an SCCI can accelerate human skill acquisition by that factor. The substantive digital result is the separation of immediate assistance, assumed retained learning, and timing failures, with a reproducible procedure for testing those distinctions.

## B. Mean arterial pressure feedback

### Reduced-order plant and external measurement

The second application is an explicitly selected physiological function: maintaining a synthetic MAP state under a modeled orthostatic disturbance. No brain recording is used. Feedback comes from an **external pressure sensor**; the model does not infer blood pressure from spinal recordings.

Pressure \(p\) and a dimensionless first-order actuator state \(r\) follow

\[
\dot r=\frac{u-r}{\tau_a},\qquad
\dot p=\frac{-(p-p_0+D(t))+g r}{\tau_p}.
\]

Explicit Euler integration uses \(\Delta t=0.05\) s for 160 s. The illustrative reference is \(p_0=90\) mmHg. At 20 s, \(D(t)\) ramps to a uniformly drawn 26–34 mmHg disturbance over two seconds, then stays there. Each seed draws \(g\sim U(28,42)\) mmHg per normalized actuator unit, \(\tau_p\sim U(6,10)\) s, and \(\tau_a\sim U(1,2.5)\) s. The ordinary feedback sensor has 0.30 s latency and independent Gaussian noise SD 0.60 mmHg.

This is a stable linear plant with uncertain gain, not a patient-specific model. It omits cardiovascular compartments, baroreflex nonlinearities, posture dynamics, sympathetic recruitment, arrhythmias, medication, sensory confounding and chronic adaptation. The favorable plant signs and available actuation are assumed. The mapping from stimulation site, amplitude, width and frequency to \(g\) is absent.

### PI control, output authority and faults

With measured error \(e=p_0-p_m\), the controller proposes

\[
u^*=K_p e+I,\qquad
\dot I=K_i e,\qquad
u=\operatorname{clip}(u^*,0,u_{\max}).
\]

Nominal \(K_p=0.045\) per mmHg and \(K_i=0.008\) per mmHg-second. Conditional integration freezes integral growth that would push further into a constraint. The command is limited to 0–1 and slew-limited to 0.40 units/s. The normalized command is not a stimulation dose. A fixed-input control ramps to 0.85 at disturbance onset; the unassisted control stays at zero. The fixed controller knows the disturbance onset, so this comparison already grants it information unavailable in many practical settings.

When sensor age exceeds 0.50 s, closed-loop output immediately goes to zero, overriding the slew limit, and integration freezes. In the fault case, sensor data disappear from 75–88 s. Invalid data from 105–108 s latch an inhibition until two seconds of valid data have returned; the integral is reset on recovery. Dropout recovery without an invalid-data latch resumes after a fresh sample. This model-level 0.50 s stale-data rule is distinct from the pulse reference's nominal 0.10 s freshness interlock; neither is validated for a medical system.

The fault strategy prioritizes inhibition over regulation: pressure can fall while output is off. Calling it "safe" for a person would be unsupported. Loss of pressure support may itself be dangerous, and a clinical fallback must be designed and evaluated separately.

### Pressure comparisons and results

Primary accuracy scores use 40–159 s, excluding initial adaptation. Minimum/maximum pressures use the full trace. Reporting both prevents the low steady-state error from concealing the initial dip. The fraction within an illustrative ±5 mmHg band and the saturation fraction accompany MAE.

| Case, 40 seeds each | Mean MAP MAE, mmHg | Mean fraction within ±5 mmHg | Saturation fraction |
|---|---:|---:|---:|
| Unassisted | 29.835 | 0.000 | 0.000 |
| Fixed input 0.85 | 2.978 | 0.755 | 0.000 |
| Nominal PI feedback | 0.309 | 0.999 | 0.107 |
| Gain multiplied by 0.60 | 9.337 | 0.133 | 0.986 |
| Gain multiplied by 1.40 | 0.071 | 1.000 | 0.000 |
| Latency 1.5 s, noise SD 2.0 mmHg | 0.696 | 0.998 | 0.058 |
| Output capped at 0.65 | 7.616 | 0.152 | 0.956 |
| Dropout and invalid-data episode | 4.540 | 0.698 | 0.169 |

The paired nominal MAE reduction versus no input is 99.02% (bootstrap interval 98.36–99.53%). This large value reflects an idealized, mostly controllable plant and the post-transient scoring window. Mean minimum pressure during the **full** nominal closed-loop trace is 79.40 mmHg, compared with 85.20 for the anticipatory fixed input: feedback has a deeper initial dip despite better sustained regulation. Neither number is a clinical target or a predicted patient response.

Low-gain and capped-actuator failures show the importance of control authority. Zero nonzero commands occur during model-defined stale/invalid states in all 40 fault trials, but pressure regulation deteriorates. The results validate software behavior against its own specified model; they do not demonstrate effectiveness of spinal stimulation or a universal ability to control the body.

## Digital pulse reference and separation of layers

`firmware/scci_rh_pulse.c` is a portable timed-command state machine. The nominal ideal test-load sequence has +100 µA for 200 µs, a 50 µs gap, −100 µA for 200 µs, and 19,550 µs recovery. That is 20 nC per phase and zero signed ideal net charge over a 20 ms period. A software sensor fault inhibits new pulses while allowing an already scheduled balancing phase to complete. Configuration, stale-data, overlapping-pulse and 32-bit timestamp-wrap conditions are host-tested.

The C host executable passed **23 assertions** with warnings treated as errors and assertions explicitly enabled. The model Python suite has **9 tests** exercising conditional learning, latency mismatch, phase shuffling, determinism, output bounds, insufficient actuator authority, stale/invalid-sensor inhibition and observation completeness at every saved sample. Five additional unit tests call the actual compiled C library, covering startup inhibition, balance, fault latching, stale/wrapped timestamps, non-overlapping pulses and invalid configurations. C binding tests are explicitly skipped until the library has been built. Generated C artifacts are `results/firmware_pulse_trace.csv` and `results/firmware_validation.json`.

`scripts/run_adapter.py` connects each application trace to the C shared library through `ctypes`. Pressure's normalized command requests an illustrative frequency of \(50u\) Hz, with application commands held between samples and integer-microsecond pulse scheduling. Motor timing requests one pulse per increasing estimated phase crossing after warm-up; its abstract signed trajectory correction is retained as a separate logged variable and is not mapped to electrical current. Each accepted pulse remains at the nominal 100 µA, 200 µs-per-phase setting. The adapter generates 5,704 pressure pulse requests accepted by the C gate and 10 motor pulses for the example traces. Seven checks verify initial off state, valid-data gating, ideal balance, spacing ≥20 ms, nominal segment bounds, PHASE/INHIBIT current-sign consistency, and a deliberately stale request's rejection. `results/application_pulse_events.csv` logs the segment commands; `application_pulse_requests.csv` logs accepted/rejected requests; `adapter_validation.json` records the outcomes.

The pin convention is PHASE=0 for positive, PHASE=1 for negative, and INHIBIT=1 for off. This is a declared digital interface to the illustrative switching circuit and must be verified in an actual timer/output backend. The adapter's fresh-data gate inhibits immediately when application data are unavailable; the plant controller's 0.50 s rule and C engine's 0.10 s interlock are distinct layers. The C engine is advanced at ideal segment boundaries without an MCU or analog switching transient. This integration proves that computed requests can drive the specified digital state machine, not that the emitted pulses produce either model's assumed actuator response.

These layers are connected architecturally but are not a biological end-to-end simulation. The motor command is an abstract correction; pressure control uses a normalized actuator; the pulse state machine emits nominal electrical commands; the circuit study uses an electrical load. No common experimentally calibrated conversion between them is claimed. Real MCU timing, current accuracy, charge density, electrode impedance, compliance, tissue response, chronic recording and closed-loop stability would need separate validation.
