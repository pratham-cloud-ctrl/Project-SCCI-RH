# Contact router: mechanism and integration boundary

This checkpoint gives the two existing stimulation sources explicit contact
selection and hardware route admission. It serves SCCI_RH's proposed spinal
recording, interpretation, learner-specific stimulation and observed feedback
architecture. The motor-learning and selected physiological-control applications
retain their conditional biological assumptions. Routing is electrical access;
it does not establish the information or selectivity needed by either application.

## Native circuit and ports

The [editable KiCad package](../../electronics/stage4/contact-router/README.md)
contains six sheets, 155 components and 650 pin assignments. Four **TMUX6208PWR**
8:1 devices provide two sixteen-way selectors: either source can select any one
of sixteen shared stimulation contacts. Each source retains its own dedicated
return. The single canonical output connector therefore represents eighteen
functional stimulation ports, complementing the recording package's eighteen
recording/reference/bias ports. Fixture headers are not proposed implant feedthroughs.

The new path is `driver A_BR -> future terminal guard -> source A_ROUTER ->
one of two 8:1 banks -> selected STIM contact`. The return path is
`dedicated RETURN contact -> existing monitor RETURN_LOAD -> existing 2 ohm
Kelvin shunt -> monitor RETURN_DRIVER -> driver B_BR`. The shunt is not duplicated
or moved to the servo ground leg. The terminal guard and physical monitored
interconnection remain integration tasks; this is not one assembled board.

The selected 24 V/approximately 3 mA/200 microsecond driver boundary is preserved.
Current polarity reverses through the existing bridge; the mux's absolute pin
voltages must still remain between its supplies. This fixed-return implementation
does not yet implement arbitrary pairs among the sixteen stimulation contacts.
It also does not implement the wider concept's 48 V/20 mA operating envelope.

TMUX6208 is selected over the earlier TMUX8108 comparison for this restricted
slice. The 8108 has substantially higher resistance near its positive rail;
the lower-voltage 6208 better fits the 24 V range and saves quiescent power at
the cost of larger capacitance. Manufacturer test conditions and exact production
packages are recorded in the [primary component review](contact-router-component-review.md).

## Actual route-holding and admission logic

A 595 shift/storage register holds a candidate eight-bit payload. Two quad
D-input selectors choose candidate or held active Q for eight physical address
flip-flops. The active flip-flops always receive the **raw COMMIT clock**;
permission changes D, never gates the clock. A forbidden commit therefore holds
the old route and consumes admission instead of creating a route change when
health later returns.

Commit requires both route intents, both phase requests and both driver RUN
signals low, plus external observed quiescence and health. Keeping route intent
high through both phases, the gap and recovery prevents reconfiguration during
a superficially quiet interphase interval. A separate acknowledgement flip-flop
requires a new edge after commit, followed by a separate valid REARM edge.
An acknowledgement stuck high from an earlier route cannot reauthorize it.
The actual eight active Q bits have a readback connector; the 595 serial output
is only candidate-state data.

If both sources request the same contact, four-bit equality logic inhibits
**both** banks and clears sticky route validity. Removing the conflict cannot
automatically restart delivery. Different selected contacts retain distinct
dedicated returns, without asserting independent tissue recruitment.

The [control contract](contact-router-control-contract.md) gives exact equations,
ports and the provisional 25 microsecond off/on allocations. These are stable
logic and future controller requirements. Setup/hold, analogue interruption,
true quiescence and switch position are not inferred from command pins. A new
but false acknowledgement can still authorize incorrectly checked data; that
counterexample remains visible. External rail/monitor/AFE-isolation/watchdog
inputs have not become implemented measurements merely by being named.

## Finite electrical and protocol evidence

The [routing study](../../electronics/stage4/routing-study/README.md) independently
checks 8,192 ownership states, 131,072 address capture/hold cases and 16,384
quiet-admission combinations. Fifteen scenario groups contain 36 histories,
86 assertions and 396 snapshots. Manufacturer pin roles are used to evaluate
the exported native gate/flip-flop connections separately from the producer.

A separate 36-case passive study investigates unselected-contact coupling.
Interterminal capacitances are declared assumptions, distinct from a datasheet's
terminal-to-ground capacitance. An independent scalar/charge/RC auditor checks
10,917 conditions, including every saved trajectory point through closed-form
impulse superposition. Small assumed contact capacitance produces appreciable
off-contact voltage; exactly opposed/matched coupling cancels only in that ideal
case. No peak-current, universal isolation or tissue-safety result is invented.

Four-device router power is illustrated at 5.28/10.08 mW using 55/105 microampere
test currents at 24 V. The original test is at 39.6 V; this projection is not a
guaranteed 24 V corner or complete system budget. Switch capacitance, injection,
leakage, voltage drop and return/monitor bias require integrated accounting.
EN low is not powered-off analogue protection. All connected contacts must be
qualified before reducing the router rail.

## MCP evidence and next package

The new KiCad MCP checks saved native component identities, actual pin nets,
schematic bounds and ERC. These saved-file operations do not inspect unsaved
PCB edits. FreeCAD's live bridge separately opened the unchanged Stage 2 model
and found 80 valid solids; that confirms access to existing allocation geometry,
not completion of populated CAD. The bridge provenance is recorded in
[MCP readiness](../../provenance/stage4-mcp-readiness.json).

The next bounded package is independent terminal shutdown, duration/watchdog,
rail and voltage/compliance supervision connected to the existing circuit ports.
The [remaining-work record](remaining-work.md) fixes the wider Stage 4 exit scope.
Biological demonstration, hardware fabrication and clinical qualification are
not prerequisites to finishing this entirely digital concept.
