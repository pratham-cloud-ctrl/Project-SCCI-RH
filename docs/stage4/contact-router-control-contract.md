# Contact-router ownership, address capture and rearm contract

**13 October 2026. Restricted 24 V digital SCCI circuit slice; no implanted or biological validation.**

The contact router connects each of the two [current-driver sources](current-driver-control-contract.md)
to one of 16 shared stimulation contacts. Each source has its own fixed dedicated return. Four
`TMUX6208PWR` devices provide two 8:1 banks per source. This adds actual routing commands to the
driver's previously external `ROUTE_LOCKED` requirement. It does not turn a command signal into
measured confirmation of analogue switch position, terminal isolation or delivered phase charge.

The native router and the finite study implement a bounded part of Project SCCI RH's proposed
record–interpret–stimulate–observe loop. They do not require the conditional motor-learning or
selected physiological-response premises to be demonstrated before the digital concept can be designed.

## Ports and ownership

| Signal or connection | Required meaning |
|---|---|
| `ADDR0[3:0]`, `ADDR1[3:0]` | Two active four-bit contact addresses, retained in eight physical flip-flops. Address 0–15 selects contact 1–16 in the native connector naming. |
| Shifted payload | Eight bits in the `SN74LVC595A` output register. Shifting or latching this payload alone cannot alter an active contact address. |
| `COMMIT` | Raw positive-edge clock to the active-address flip-flops and `COMMIT_SEEN`. Its high level also inhibits every bank and clears acknowledgement/validity. Keep the admission inputs and data stable before and after this edge. |
| `WANT0`, `WANT1` | Route-enable intent for each source. Hold it high through both pulse phases, interphase gap and recovery. Release both before reconfiguration. It is distinct from raw phase request and observed driver RUN. |
| `REQ0/1`, `RUN0/1` | Both raw driver requests and observed driver RUN signals must be low for address commit and rearm. A low request is not itself proof that current has decayed. |
| `QUIESCENT0/1_OK` | Independently observed current quiescence and settled monitoring history for both sources. These are external qualified inputs in this package. |
| `RESET_READY`, `RAILS_QUALIFIED` | External startup/reset and rail supervision. Deassert while logic still operates validly; do not invent reliable logic state after supply brownout. |
| `MONITOR0/1_OK` | Independent delivered-current/charge monitoring permission. Router rearm does not clear monitor faults. |
| `AFE_ISOLATED_OK` | Qualified recording isolation/blanking state before stimulation. A commanded clamp state alone is insufficient; this router does not establish RHD input voltage or filtered neural recovery. The executable study calls this input `afe_blanked`. |
| `EXT_WATCHDOG_OK` | Independent supervisory permission. The actual watchdog circuit and its interruption deadline remain a subsequent integration item. |
| `ROUTE_ACTIVE_BITS_VERIFIED` | A raw external positive-edge acknowledgement after all eight active Q bits have been read and compared with the intended route. Native logic checks a fresh edge after COMMIT; correctness of the comparison remains external. |
| `REARM` | Separate raw positive-edge clock that can admit the already committed and freshly acknowledged route, only while both sources are quiescent and all route intents/requests/RUN signals are low. Release it and allow settling before asserting WANT or a phase request. |
| `ROUTE_LOCKED0/1` | Commands reporting that the corresponding route enable is admitted. These are not mux-position sensors. Connect them to the driver's route-permission input, retaining independent driver timer, monitor and supervision requirements. |
| Fixed return 0/1 | One dedicated driver-return connection per source. It is not the recording reference or body-bias contact. Disabling the contact bank does not disconnect this return wire from its driver output. |

Two sources can use different shared contacts simultaneously. If both WANT signals are high and the
active addresses are equal, **both sources are inhibited**. There is no winner, priority or implicit
permission to sum their currents. Dropping one WANT after a collision cannot automatically resume
the other source because collision clears the sticky route-validity flip-flop.

## Exact stable-state equations

`&`, `!` and `==` mean AND, NOT and equality. All controls below refer to qualified 3.3 V logic;
external input defaults and asynchronous reset remain necessary.

```text
BASE = RESET_READY & RAILS_QUALIFIED & MONITOR0_OK & MONITOR1_OK
       & AFE_ISOLATED_OK & EXT_WATCHDOG_OK

SAFE_LOAD = BASE & QUIESCENT0_OK & QUIESCENT1_OK
            & !WANT0 & !WANT1 & !REQ0 & !REQ1 & !RUN0 & !RUN1

Each active-address bit:
  D = SAFE_LOAD ? shifted_payload_bit : active_Q
  CLK = raw COMMIT
  N_CLR = RESET_READY
  N_PRE = 1

COMMIT_SEEN flip-flop:
  D = SAFE_LOAD
  CLK = raw COMMIT
  N_CLR = BASE
  N_PRE = 1

READBACK_SEEN flip-flop:
  D = COMMIT_SEEN
  CLK = raw ROUTE_ACTIVE_BITS_VERIFIED
  N_CLR = BASE & !COMMIT
  N_PRE = 1

COLLISION = WANT0 & WANT1 & (ADDR0 == ADDR1)

VALID flip-flop:
  D = COMMIT_SEEN & READBACK_SEEN & SAFE_LOAD
  CLK = raw REARM
  N_CLR = BASE & !COMMIT & !COLLISION
  N_PRE = 1

READY = VALID & BASE & !COMMIT & !COLLISION
ROUTE_LOCKED0 = READY & WANT0
ROUTE_LOCKED1 = READY & WANT1

BANK0_EN[source] = ROUTE_LOCKED[source] & !ADDR[source][3]
BANK1_EN[source] = ROUTE_LOCKED[source] &  ADDR[source][3]
MUX_A[2:0]      = ADDR[source][2:0]  (same for both banks)
```

Every flip-flop uses a raw externally generated clock. Combinational health logic selects the
address **D input** or asserts asynchronous clear; it does not gate COMMIT, acknowledgement or REARM
clocks. In particular, returning health while COMMIT or an acknowledgement is held high cannot
create a new clock edge. An inadmissible COMMIT retains the active address through its D-input hold
mux, clears `COMMIT_SEEN`, and consumes route permission. It is detected/inhibited in stable logic;
this is not a proof of hazard-free operation when signals violate physical setup/hold timing.

`SAFE_LOAD` deliberately requires both WANT signals low. Requiring only disabled bank outputs
would be circular: COMMIT itself forces those outputs off. WANT held high through an interphase gap
therefore continues to reject address updates even when request and RUN happen to be low.

COMMIT clears `READBACK_SEEN` even if an earlier acknowledgement is still high. Returning COMMIT
low does not create an acknowledgement edge. A new raw acknowledgement edge is necessary before
a separate REARM edge can set VALID. A REARM edge with invalid conditions samples D=0; health
recovery cannot later reinterpret that old edge as successful. Collision clears VALID but does not
invalidate an unchanged active address or its acknowledgement: after explicit release and observed
quiescence, a new REARM may re-admit that same verified configuration.

## Reconfiguration sequence and timing allocation

1. End the phase through the driver; preserve its timeout, interruption and monitor history. Hold
   the existing route throughout the planned opposite phase, gap and recovery.
2. Set both WANT signals low. Keep both raw requests and driver RUN signals low. Wait for bank
   turn-off and require both observed quiescence inputs. A request-low delay is not a substitute for
   measured quiescence.
3. Preload and latch the eight-bit shift-register payload. Drive acknowledgement and REARM low.
   Confirm startup, rails, monitors, recording isolation and external watchdog qualification.
4. Make one raw COMMIT pulse with data and SAFE_LOAD stable across the real setup/hold aperture.
   Return COMMIT low and wait for the active registers and readback wiring to settle.
5. Read all eight active Q bits and compare with the intended configuration. Missing, wrong or
   ambiguous data must not produce an acknowledgement. Generate one new acknowledgement pulse only
   after a successful comparison; return it low.
6. Generate a separate REARM pulse while SAFE_LOAD remains true. Return REARM low, allow logic
   settling, assert the selected WANT signals and allow bank turn-on/analogue settling.
7. Only then rearm and request a driver phase according to its independent control contract.

A **25 microsecond bank off/on settling allocation** and a **250 microsecond controller
reconfiguration allocation** are provisional integration targets. The finite event study assigns
no physical latency to its ordered events and does not qualify either number. Primary switching
limits must be applied at the selected supply, temperature and load; a parameter specified at a
different rail or a typical curve is not a guaranteed 24 V interruption bound. Readback GPIO
settling, logic propagation, monitor history and actual load-current decay need their own budget.
The controller allocation includes both 25 microsecond guards, shift/latch, commit, readback,
acknowledgement and rearm; future firmware must demonstrate that complete sequence within its
admitted operating conditions.

The selected TMUX6208 supports the restricted 24 V slice; it does not extend the package to the
broader earlier 48 V concept. Its powered signal terminals must remain within its supplied signal
range. Rail-off or overvoltage behavior is not inferred from its fail-safe **logic** feature.

## What the finite study checks

Run the portable, standard-library-only study with the repository Python or any supported Python 3:

```text
python electronics/stage4/routing-study/route_contract.py --check
```

Default and `--check` reproduce and compare saved data without writing. Only `--write-results`
refreshes `route-results.json`. The saved source digest normalizes CRLF to LF so a Windows checkout
does not falsely change the source identity.

The study compares gate-form bank decoding with an independent set-based contact-allocation oracle,
and bitwise D-input selection with a separate before/after register-state rule. It reports:

| Check | Finite scope |
|---|---:|
| All 16 × 16 address pairs, both WANT values, base permission, block and COMMIT states | 8,192 truth rows |
| Equal-address simultaneous demand, all other enumerated states | 128 rows; both sources inhibited |
| Every old/next pair of two four-bit addresses, both SAFE_LOAD states | 131,072 capture/hold rows |
| Every combination of the six base qualifiers, two quiescence flags and six activity flags | 16,384 qualification rows |
| Independently evaluated gates from the exported native KiCad XML, checked against ownership and quiet-admission oracles | 8,192 ownership and 16,384 qualification rows |
| Actual exported clock/D/asynchronous-control pin connections and D-input selectors | 11 flip-flops, two selectors; 631 wired pins compared with the connectivity table |
| Startup, two-source ownership, collision, phase/gap/recovery freeze, invalid commit, raw-clock recovery, missing/wrong/stale acknowledgement, false fresh ACK, fault interruption, host freeze, shift-only changes, brownout and ordered reconfiguration | 15 groups, 36 router histories |

The current saved study contains **86 successful assertions and 396 state snapshots**, with no
independent-oracle disagreement. Its exposed-fault witnesses are successful checks that the model
retains a limitation; they are not claims that the corresponding protection has been implemented.
The exported-XML check uses manufacturer pin roles independently of the local symbol's pin names;
it does not execute the schematic builder's Boolean implementation as its reference oracle.

## Explicit remaining boundaries

The fresh acknowledgement latch rejects an old high acknowledgement held through COMMIT. It cannot
prove that a **new** acknowledgement edge is truthful. The study retains a counterexample in which
the external checker asserts a fresh edge despite wrong stale bits; the router then admits that
incorrectly qualified command. Active-Q readback must therefore be implemented and validated in the
controller, and it still establishes digital command state rather than actual analogue mux position.
The 595 serial return is not active-address readback.

Loss of any base permission interrupts bank commands and clears the admission/acknowledgement state.
Restoring permission cannot restart a phase. A powered host that freezes while its external watchdog
permission remains high is not detected by the router alone; the separate driver timer and the future
independent watchdog remain essential. The Boolean study provides no analogue interruption deadline.

For the analogue handoff, budget off-bank leakage from both sources, drain/source capacitance,
transition charge injection, driver clamp and bias paths, fixed-return connections, adverse shared-load
coupling and a failed-on mux. Bank disable is not zero charge or complete terminal isolation. Retain
observed monitor current rather than replacing it with route commands. The recording reference and
bias remain separate from stimulation returns. None of these finite results earns neural decoding,
retained motor learning, selected physiological efficacy or implant safety.

Primary component references: [TI TMUX6208 Rev E](https://www.ti.com/lit/ds/symlink/tmux6208.pdf),
[TI SN74LVC595A](https://www.ti.com/lit/ds/symlink/sn74lvc595a.pdf),
[TI SN74LVC157A](https://www.ti.com/lit/ds/symlink/sn74lvc157a.pdf), and
[TI SN74LVC1G74](https://www.ti.com/lit/ds/symlink/sn74lvc1g74.pdf).
