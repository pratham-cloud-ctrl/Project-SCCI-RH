# Known task cues: observed forecasting and cancellable frame planning

**Status: implemented and reproduced digital component study. The complete assisted cue controller remains unqualified.**

Project SCCI RH's motor concept combines observed spinal/external information, an expert-informed task reference, an observed learner response map and selective stimulation. The original reactive controller has a chosen 100 ms prediction cap. Its nominal observed support age, processing and response delay exceed that cap. This study investigates a different mechanism: a participant follows a declared periodic instruction, so the computer knows the future **instruction** while forecasting achieved movement from finite measured history. It never knows the participant's future achieved position or true neural phase.

The implementation is [cue_policy.py](../../src/scci_rh/stage3/cue_policy.py). Its separate 150 ms allocation was fixed before evaluating results. The original reactive policy, biological delay and electrical precision are unchanged. This is an additional forecast family with its own heldout measurements and limits; a longer number alone cannot qualify the existing reactive model.

## Forecast fit and information boundary

One synthetic subject's 12 s nominal-cadence calibration supplies finite external measurements at 200 Hz. Each input has 40 components: the latest 16 measured two-position samples (32 components, 75 ms history), four components of the known current instruction, and four of the known target instruction. A separate ridge model predicts measured target position at each 5 ms horizon from 0 through 150 ms. Each model has 82 coefficients; this is not the 32-input capacity-matched spinal-information comparator and does not establish additional information from spinal recordings.

Training uses the first chronological portion and a 100 ms purge before the split. Every training target, including the furthest future label, ends before that purge. Heldout rows begin only after their complete past history clears a second 100 ms purge. The saved fit has 1,725 training and 534 heldout rows per horizon. Offline future **measured** labels are legal fitting targets; they never become online inputs.

The forecast error allocation is the largest absolute component error in heldout measured labels plus a chosen 3 mm label allocation. A 15 mm maximum forecast allocation was specified before results. This is an empirical diagnostic in the chosen model, not a confidence interval, a universal error bound or physiological tolerance. Standardized inputs must also remain within the chosen five-standard-deviation feature domain.

The record's synthetic spinal packets and a separately calibrated decoder still supply `StateEstimate` qualification. The interface accepts a frozen `ExpertRepresentation`, but this study uses the **known instructed learner goal**. Existing recorded expert resources are not treated as task-competence qualified. The forecaster itself uses measured external history and known instructions. No claim is made that this particular planner requires learner spinal information or transfers an expert's skill.

## Physical timeline and command guards

For a decision available at time `now`, the earliest candidate launch is the first 40 Hz frame at or after `now + 11.85 ms`. The forecast horizon runs from the actual measurement support to that frame plus the **observed** response onset and twice its observed onset uncertainty. It is rounded upward to the 5 ms forecast grid; the extra rounding is retained in the target time. The entire horizon must remain within 150 ms and within a qualified context/horizon domain.

The policy solves a regularized correction using the observed 2×2 response matrix. Qualification requires the smallest observed singular value to exceed the uncertainty-matrix norm. A future command is not an independently measured future dose. This prototype explicitly assumes a prospective full-profile measured dose of 1.012 nominal with 0.074 nominal uncertainty, inherited from the unqualified nominal-delivery surrogate. It converts the solved measured fraction into a command fraction and retains both separately. With gain uncertainty `U_G` and prospective dose uncertainty `U_u`, its correction allocation contains all three terms: `U_G|u| + |G|U_u + U_GU_u`, plus empirical forecast error. These must fit the separate 25 mm allocation. The joint term cannot be discarded. Every emitted command retains `UNQUALIFIED_NOMINAL_ASSUMPTION`; this arithmetic does not qualify future hardware. Invalid state or reference representations, unsupported forecast inputs and unqualified authority cause abstention.

The scheduler keeps the latest command **for each frame**. A later frame's new plan must not erase an earlier eligible frame. Every newly arrived observer packet can cancel all pending commands. Invalid/stale/repeated/nonmonotonic support, changed context, replayed command IDs, excessive horizons or malformed commands cancel or reject admission. At launch it checks support freshness again and prohibits an observer packet whose arrival lies in the future. A missed frame is cancelled; it is never replayed late. Commands expire 1 ms after their frame. Reversed or invalid clocks cancel pending work.

Previously predicted targets are checked only when the corresponding measured support actually arrives. A component error above 15 mm latches forecast rejection for that policy session; no automatic reset makes a changed context qualified again. This delayed monitor cannot erase already authorized commands or guarantee detection before every possible disturbance.

## Observed results and their limits

The [readable summary](../../results/stage3/cue-policy/summary.json) and [compressed raw witness](../../results/stage3/cue-policy/raw.json.gz) preserve eight scheduling replays, all 31 fitted horizon models, chronological support identities, decisions, commands and cancellations.

| Test context | Largest measured-error allocation | Outcome |
|---|---:|---|
| Chronologically withheld nominal unassisted calibration | 8.744 mm | Passes the chosen 15 mm allocation across the fitted grid |
| Independent nominal unassisted four-second capture | 8.763 mm | Passes the separately tested 50/100/150 ms horizons |
| Independent four-second capture with 160 assumed fixed-profile pulses | 54.528 mm | Fails; assisted context remains unqualified |
| Independent capture with a 40 mm sensor-offset step | 47.264 mm | Fails; changed sensor context remains unqualified |

Sparse independent context probes qualify only their listed 50/100/150 ms horizons. They do not silently qualify intermediate horizons or a new cue-controlled context.

The actual electrical calibration has a negative observed authority margin (−31.119 mm) and emits **zero** cue commands. The nominal-assumption calibration has a positive observed margin (+24.572 mm), but its electrical delivery remains explicitly unqualified.

The nominal-assumption **scheduling replay** launches 34 signed-fraction commands over four seconds. Selected commands use 120 ms forecasts and a 15 ms decision-to-frame interval. This demonstrates a timing/planning component against an observed unassisted recording. It delivers **zero physical pulses**, does not feed commands back into that recording, and supplies no assisted-performance or retained-learning result.

When the first scheduled command changes the required domain to an unvalidated cue-assisted context, exactly one command is launched and the continuation abstains. Invalid, stale, repeated and explicitly changed-context negative controls launch 17 commands before their halfway fault and cancel continuation. An unannounced 40 mm sensor-offset step is detected by the previously forecast target's newly arrived measurement at 2.055 s; a 44.293 mm maximum observed residual is retained, and the latch cancels continuation. That detection time is a witness for this selected step, not a general latency guarantee.

The main mechanistic finding is therefore conditional. Known cues can support an empirically tested unassisted forecast and a correctly timed cancellable command queue. The same forecast does **not** survive the tested assisted response. A complete cue controller needs an input-aware model, withheld assisted validation across the proposed profiles/densities/postures and a qualified delivery monitor. The pipeline must then be coupled to acquisition, routing, delivered-dose evidence and a modeled body before any learning comparison is justified. This failed assisted-domain check remains part of the result.

## Reproduction and checks

Run `python scripts/stage3_cue_policy_study.py --check results/stage3/cue-policy/raw.json.gz` to reproduce the saved study without overwriting it. `--output` explicitly creates a new deterministic compressed witness and readable summary. The receipt hashes the policy, runner, motor and acquisition source.

Thirteen contract tests cover purged future-label support, the separate forecast family, actual negative authority, bounded horizons, gain/dose joint uncertainty, queue starvation prevention, exact frame/pipeline boundaries, expiry/missed frames, replay/context/invalid support, future observer arrivals, reversed clocks and the causal residual latch. They verify this digital mechanism, not an implanted human SCCI.
