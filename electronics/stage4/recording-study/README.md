# Recording-front-end studies

This package connects the new native recording slice to explicit electrical and
protocol assumptions. It does not repeat or supersede the closed Stage 3
biological/control investigation. Native sources are in
[recording-front-end](../recording-front-end/README.md).

## Passive input-network model

`input_network_study.py` solves a two-node passive network with exact matrix
exponentials and charge conservation. Eight quiet rows compare four source/reference
conditions, with and without the newly selected shunt capacitors. Nine transient
cases preserve source-edge coupling, positive/negative stimulation transients,
reconnection while grounded, switch charge injection, high source impedance and
an intentionally unblanked subrail fault. Raw trajectories are saved in `traces/`.

The native network uses 4.99 kohm series impedance, a 10 Mohm protected-node
bleeder, 470 pF at each positive RHD input and 2.2 nF at the shared reference.
The reference feeds sixteen negative amplifier pins: 192 pF typical input
capacitance before the external network. The added capacitors reduce charge-step
amplitude; their different values approximately match nominal input time constants.
They do not compensate arbitrary or changing electrode impedances.

The model deliberately declares 10 ohm HV-switch resistance, 2.1 ohm clamp
resistance, 94 pF protected-node and 84 pF drain/board capacitance. The capacitance
split is an engineering lump, informed by typical manufacturer capacitance figures,
not an extracted device model. Source-to-protected-node and off-path mutual
capacitances are swept from 1 to 10 pF. Injected charge is swept from 30 to 300 pC.
These are sensitivity assumptions, not guaranteed limits at the proposed rails.
TMUX7412F has no dedicated +/-5 V electrical-characteristics table; its higher-rail
Ron/leakage figures cannot silently become worst-case +/-5 V guarantees.

An uncorrelated RSS illustration barely exceeds the 10 dB allocation for a
10 microvolt RMS source at 50 Hz, including the network's source attenuation.
However, intrinsic CMRR leakage and source-impedance conversion share the same
common-mode sinusoid. Their phases are not established; a constructive coherent
bound must add those amplitudes before combining unrelated noise. With that
bound, even the nominal native network falls just below 10 dB. All four native
10 microvolt cases fail; the nominal 50 microvolt case passes conditionally.
This is an explicit unresolved weak-signal allocation, not a reason to retune
the gate or reopen biological qualification. The 10 Mohm
bleeder itself introduces unequal common-mode attenuation at unequal source
impedances. Intrinsic typical CMRR does not repair this effect. Noise includes the
typical 2.4 microvolt RHD contribution, a conservative series-resistance thermal
allocation, nominal quantization and an assumed alias allowance. Both RSS and
coherent common-mode results are saved; the latter controls the quiet gate.
The signal family
and impedances are SCCI_RH hypotheses, not measurements from implanted human spines.

Seven transient cases remain inside the sampled +/-0.4 V pin envelope; the
300 pC injection and unblanked 600 mV fault fail and remain in the results. These
sampled voltage classifications neither certify continuous maxima nor establish
the +/-5 mV **AC** linear range. In particular, a 200 mV step through an ideal
0.1 Hz high-pass remains approximately 188 mV after 100 ms, and takes about
5.87 seconds to fall below 5 mV without a reset. Intan's recommended fast-settle
duration is 2.5/fH, approximately 8.33 ms at 300 Hz; restored acquisition must
still qualify actual amplifier and downstream filter recovery. No fixed wait
in this package grants neural validity or a 20 ms feature latency.

The model does not implement the HV-switch nonlinear fault detector, body/tissue
common-mode motion, rail collapse, package parasitics, switch failures, assembled
isolation, ADC nonlinear saturation, or a full amplifier macromodel. A voltage
within +/-5 V switch rails can still violate the RHD +/-0.4 V input envelope.
External voltage qualification and phase sequencing remain necessary.

Two 499 kohm body-bias resistors imply 24.05 microamp at an assumed 24 V potential;
one short implies 48.10 microamp. Those are circuit arithmetic, not a clinical
current limit or proof of an acceptable tissue path. The reference/bias contacts
are never stimulation returns. A 25 nA leakage through 10 Mohm alone gives
250 mV, so open-input voltage must be qualified rather than assumed near zero.

Primary sources and exact component conditions are recorded in
[component review](../../../docs/stage4/recording-front-end-component-review.md).

## Reproduction and independent checks

From the repository root, use the project Python environment:

```text
python electronics/stage4/recording-study/input_network_study.py
python electronics/stage4/recording-study/verify_input_network.py
python electronics/stage4/recording-study/timing_contract.py --check
```

The first command is a read-only same-model replay. The second independently
expands the AC admittance determinant, recomputes DC limits and integrates
whole-network KCL on the saved logarithmic grids with a declared 1% quadrature
allowance. It also checks artifact hashes. This distinguishes reproduction from
an independent conservation check. Timing/protocol scope is documented in the
[control contract](../../../docs/stage4/recording-front-end-control-contract.md).

`--write-results` on the generator and `--write-receipt` on the verifier explicitly
refresh their respective evidence. `build_input_figures.py` renders only saved
results. Text hashes normalize line endings; binary hashes remain exact.
