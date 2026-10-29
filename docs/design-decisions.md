# Design decisions

The decisions below define the completed digital proof of concept. They are engineering choices made for this release, not statements that a clinical implant has been validated.

| ID | Decision | Reason | Consequence and reconsideration trigger |
|---|---|---|---|
| D01 | Entirely digital | User's explicit scope | No fabricated hardware, patient testing or measured biological result is claimed |
| D02 | Two applications on one conceptual platform | Preserve both original research interests | Motor practice and blood pressure use distinct models, targets and success criteria |
| D03 | Spinal-only neural access | SCCI_RH's central identity | No cortical signal can be silently introduced; adding it creates a hybrid architecture |
| D04 | Proposed intradural surface recording and separate epidural stimulation | Avoid equating a read interface with a write interface | Chronic compatibility and human signal quality remain open; anatomy must be assessed independently |
| D05 | Illustrative 8-recording/8-stimulation contacts in future concept | Make scaling visible without claiming neuron resolution | Contact count is a design hypothesis; digital electronics exercises one representative channel of each function |
| D06 | External kinematics/calibration permitted | Neural correlation does not identify causal influence | Synthetic learner response is explicitly calibrated; claims of superior neural sensing would need an external-sensor-only comparator |
| D07 | External pressure feedback | Directly specify the physiological observation | SCCI_RH does not claim to decode arterial pressure from spinal potentials |
| D08 | Rhythmic phase as first motor state | A small state permits interpretable delay/noise studies | This task is a surrogate for a component of skill, not a model of every sport or instrument |
| D09 | Retention separate from assistance | Performance during intervention can be misleading | Outcomes are sampled with assistance off; a zero-benefit learning control is mandatory |
| D10 | Reduced-order pressure plant with uncertainty | An inspectable model supports falsifiable control experiments | Gains and time constants are synthetic; successful control does not validate patient dynamics |
| D11 | Nominal 5 V reference circuit, 100 microampere / 200 microsecond phases | Make electrical charge/compliance calculations auditable on a test load | These are digital bench values, never a clinical waveform or safety claim |
| D12 | 100 x 70 x 32 mm enclosure, 80 x 50 mm board | Coherent desktop identity and shared mechanical interface | Display enclosure is deliberately labelled; no anatomical fit, hermeticity or sterilization qualification |
| D13 | Source plus exports | A professional engineering submission must be inspectable and reusable | Editable code/CAD/KiCad sources accompany renders and PDFs |
| D14 | Deterministic seeds, raw data and tests | Claims must be reconstructable | Numeric summaries refer to generated records rather than manually drawn curves |
| D15 | Private repository | User's preference | No public release or personal-data publication is implied |
| D16 | Explicit AI contribution | User intends to learn and defend the work | Repository creation does not establish that every derivation was independently authored or understood by the student |
| D17 | Add 12 kilohm resistance to each test-load output leg in Revision B | Initial generic SPICE model exposed a 1.361 mA switching peak | Revised nominal peak is 102.58 microamperes; compliance falls and stored polarization prevents a universal current-cap claim |

## Alternatives considered

**Direct voltage replay** was rejected as a causal model: extracellular recording combines many sources while stimulation excites structures according to field geometry and excitability. The relation must be learned or identified in the receiving system.

**A universal autonomic controller** was rejected as too underspecified to test. Mean arterial pressure is selected because it offers a clear observable output and bounded control question. This decision does not imply access to every involuntary function.

**A single fully implanted recording/stimulation arrangement** was not assumed. The surface recording evidence motivating SCCI_RH and the stimulation evidence used for its application cases involve different placements. The future platform presents these as separate modules.

**An electronics-only demonstration** would reproduce the visible build progression but leave SCCI_RH's central mechanisms unevaluated. The release therefore includes independent application models and electrical fault studies, with separate claims at each layer.

**A simulation-only submission** would leave the proposed device's interface, packaging and data flow hard to inspect. Native CAD, circuit files and a demonstration interface give the theory an engineering body while preserving the scope boundary.

## Revision discipline

The initial circuit and its transient finding are archived in `electronics/revisions/revA/`. The final Revision B preserves a traceable before/after example: model disagreement prompted a hardware-design change, then nominal and challenged cases were rerun. This is a digital design iteration; it does not establish real-component behaviour.

Every future revision should identify the changed assumption, affected claim IDs, relevant tests and observed consequence. Prefer a failed or negative test with a clear interpretation over tuning parameters until a headline appears. If a new model introduces favourable plasticity, extra sensor information or more actuator authority, name that change before comparing its results with this release.
