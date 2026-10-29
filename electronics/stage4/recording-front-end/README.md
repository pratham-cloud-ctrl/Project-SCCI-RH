# SCCI_RH-S4-REC-01 - protected, isolated 16-stream recording slice

**13 October 2026 - editable digital research design - artificial signals only**

Open [recording_front_end.kicad_pro](recording_front_end.kicad_pro) in KiCad.
On this laptop, [OPEN_IN_KICAD.cmd](OPEN_IN_KICAD.cmd) launches the installed
application explicitly. The package contains **151 components, 594 pins and
seven sheets**, with local symbols and footprint snapshots, a
[seven-page schematic PDF](recording_front_end.pdf), [BOM](bom.csv),
[pin/net manifest](connectivity.json), [XML netlist](recording_front_end.xml),
[native netlist](recording_front_end.net), [SVG sheets](svg/) and reviewed
[page renders](review/). Interface and four input-bank sheets use A2; the
acquisition and reference sheets use A3 for readable printing and inspection.

This supplies the recording side of SCCI_RH's spinal
recording-interpretation-stimulation-feedback concept. It is a concrete
component-and-net design, with deliberately external power and supervision
contracts. It does not establish that the proposed electrode arrangement
records useful spinal information, or that downstream stimulation improves
retained learning or regulates a physiological function.

## What is physically represented

| Native circuit | Selected identity and purpose |
|---|---|
| Acquisition | One Intan RHD2216, QFN56 plus grounded center shield pad |
| Source-side fault disconnect | Five TMUX7412FRRPR quads; 17 of 20 paths used |
| RHD ground clamp / acquire selection | Seventeen bipolar TMUX6219DGKR SPDT switches |
| Host/AFE digital barrier | Two ISO6741FDWR devices, three forward and one reverse channel each |
| Default-aware chip select | SN74LVC1G04DBVR on the AFE island |
| Acquire interlock | SN74LVC1G08DBVR: CONNECT AND RECORD |
| Passive bias | Two series 499 kohm resistors from separate bias contact to AFE ground |

The montage has **16 positive recording contacts, one shared reference contact,
and one separate passive body-bias contact**: 18 recording functional ports.
The 16 RHD2216 negative input pins are tied to the same `AFE_REF` node. This
provides 16 sampled differential streams; it does not create 16 independent
bipolar electrode pairs. The RHD2216 ADC multiplexes these amplifiers.

The reference and bias contacts are separate from all stimulation returns.
No stimulation router or current driver is hidden in this package. J3 is an
ordinary research-fixture header, not an implant connector or electrode design.
The Stage 3 synthetic 16-feature model remains an abstraction; native channel
count is not evidence that those features are available from these contacts.

## One positive input path

```text
RECxx_CONTACT -> 4.99k -> TMUX7412F protected S
                                  |
                        commanded disconnect / fault switch
                                  |
                           unprotected internal D ---- 10M ---- AFEAGND
                                  |
                             TMUX6219 S2
AFEAGND -------------------- TMUX6219 S1
                                  |
                             TMUX6219 D -> RHD inxx+
                                              |
                                           470pF
                                              |
                                           AFEAGND
```

The reference uses the same topology once, with **2.2 nF** at the RHD-side
reference node feeding all 16 negative inputs. Its intrinsic RHD input
capacitance is consequently 16 x 12 pF = **192 pF typical**, before the switch,
board and selected capacitor contributions. That shared loading can convert
common-mode interference into differential error.

The 4.99 kohm series resistors, 10 Mohm bleeders, and added 470 pF / 2.2 nF
capacitors are SCCI_RH design choices. Capacitors are specified provisionally as
C0G, 50 V. Exact passive manufacturer part numbers and voltage/pulse/assembly
qualification remain open. The bleed defines a floating internal node but
does not guarantee low DC voltage: for example, 25 nA through 10 Mohm is 0.25 V.
Switch charge injection, leakage and parasitic-capacitance numbers used by
the associated study remain condition-specific or assumed sensitivity values.
**Quiet recording quality and worst-case input protection are unearned.**

TMUX7412F protection is on the **S** pins, which face the external contacts.
The internal **D** pins are not overvoltage protected. During a detected source
fault the selected drain becomes high impedance. Its fault threshold follows
the approximately +/-5 V analog supply rails; it does not enforce the RHD's
much narrower +/-0.4 V linear DC input range. The RHD's differential AC range,
DC input range, and absolute maximum ratings must remain distinct.

## Control and stimulation handoff

`CONNECT` and `RECORD` cross the digital barrier as active-high commands.
Default-low receiver behavior and explicit pulldowns request disconnect/clamp
when the host link is absent and the AFE receiving supply is valid.
The actual U4 gate creates `AFE_ACQUIRE = AFE_CONNECT & AFE_RECORD_CMD`.

| CONNECT | RECORD | Native commanded state |
|---:|---:|---|
| 0 | 0 | All 17 HV paths disconnected; RHD inputs and reference grounded |
| 1 | 0 | Contacts connected to protected nodes; RHD remains grounded for qualification |
| 1 | 1 | RHD connected to protected nodes, only after external qualification |
| 0 | 1 | Invalid acquisition request; the AND gate retains the ground clamp |

Before stimulation, first lower RECORD, allow the RHD clamp to settle, then
lower CONNECT. An **external independent supervisor** must establish observed
`ISOLATED_READY` before it admits a driver phase. No such measured readiness
output is fabricated by this circuit. Commands and ordinary FF status do not
prove isolation. The driver can consume this observed result through its
external supervisory permission contract; direct integration remains work.

After stimulation, require driver current to be observed quiescent, connect
the protected nodes while retaining the RHD clamp, and qualify their voltage
relative to AFEAGND before releasing that clamp. Then apply the separately
defined settling / fast-settle and data-validity policy. Sample timestamps and
blanking/recovery invalidity must survive into the decoder. An analog model
returning below a voltage threshold does not qualify digital-filter recovery
or biological signal usefulness.

The five TMUX7412F open-drain fault flags share exactly **one 1 kohm pull-up to
AFE_3V3**. Any flag can pull the aggregate low. A high FF flag does not establish
the low-voltage RHD input qualification, acceptable leakage, valid power,
working switches, or correct data. The unused three quad paths have selectors,
sources and drains grounded.

## Power domains, SPI and RHD support pins

`HOSTGND` and `AFEAGND` are distinct exported nets. Only the two digital
isolator symbols contain both domains; no passive ground bridge is present.
Host-side power is externally supplied 3.3 V. The recording island receives
externally generated, isolated +3.3 V and nominal +/-5 V rails through J1.
These supplies must meet the devices' valid operating ranges with actual
tolerance margin. Rail generation, isolation certification, supply monitoring
and startup sequencing are not implemented here. The isolators do not provide
isolated power, and valid-supply default behavior does not qualify power ramps.
The added bipolar rails, isolators and switches revise the original Stage 2
power and area budgets; that older estimate is not a qualification of this slice.

RHD2216 operates in CMOS SPI mode: LVDS_en is grounded; CS-, SCLK-, MOSI- and
MISO- are NC as shown in Intan's CMOS connection diagram. CS+ is inactive high.
Because the selected ISO6741F forward outputs default low, the host sends
**active-high CS_ASSERT**, and U3 inverts it locally to `AFE_CS_N`.
SCLK and MOSI use the other two forward channels; MISO uses the reverse one.
The second isolator carries CONNECT and RECORD forward, and the aggregate
fault flag backward; its spare forward output is NC.

All three RHD VDD pins share AFE_3V3; GND and VESD connect to AFEAGND. Two
100 nF X7R, 16 V supply bypasses represent the manufacturer's CMOS placement
recommendation near the bottom and right supply pins. ADC_ref has 10 nF,
16 V to AFEAGND, to be placed within 1 cm. Unused auxiliary inputs connect to
VDD, auxout is NC, and elec_test is grounded to disable impedance injection.
The center pad is internally NC, assigned pad 57 locally and grounded for
shielding and mechanical soldering. RHD configuration, calibration and readback
must occur through firmware before any data is admitted.

The revised isolated-link study baseline is **4 MHz, 5 microseconds per command,
19 commands per 250 microsecond frame**: a 95 microsecond SPI burst and
4 ksample/s per channel. It replaces the earlier direct-link 8 MHz timing
assumption for this slice. Pipeline response position and physical sample
apertures must be timestamped according to Intan's command semantics.
The associated timing contract supplies the explicit roundtrip, setup, hold,
guard and invalidity assumptions; none are measured laptop-to-chip results.

The passive bias chain totals 998 kohm. Applying 24 V across it would give
approximately **24.05 microamps** by Ohm's law, assuming both resistors intact
and rated. This is neither a patient-current safety limit nor evidence about
actual current through the body or alternate fault paths.

## Footprints, review and reproducibility

The local RHD2216 land pattern follows Intan's recommended 0.5 mm pitch,
0.25 x 0.90 mm peripheral lands, 9.0 mm outer span and 6.1 mm center shield.
The local TMUX7412F RRP pattern follows TI's 0.65 mm pitch, 0.30 x 0.60 mm
lands, **3.8 mm pad-center span** and 2.6 mm center pad. RRP is the actual
orderable WQFN package; the datasheet's TSSOP PW package remains marked preview.
Both custom footprints have nine reduced center-paste windows as an assembly
proposal. The verifier checks actual copper pad numbering and dimensions.
Other local footprints are snapshots of the installed KiCad libraries and
retain their original metadata and external standard 3D-model references.
PCB stackup/routing, assembly rules and the complete populated CAD model are
future work. Intan recommends at least four PCB layers for a future board.

The native symbol pin name `VSS_NEG` identifies the bipolar negative supply;
it is a power-input pin, not a ground alias. ERC rules remain enabled, with
no ignored checks. This avoids treating a manufacturer VSS negative rail as
a ground-only pin.

`build_recording_front_end.py` generates native source and connectivity/BOM.
Re-export through KiCad 10 and render all seven PDF pages after intentional
changes. `verify_recording_front_end.py` is **read-only by default** and checks
the actual exported pin nets, manufacturer functional contracts, all 17 input
paths, domain separation, real gate/inverter connections, passive values,
footprint pad geometry, and export integrity against the frozen receipt.
Use `--write-receipt` only after an intentional reviewed regeneration.
Text hashes normalize CRLF/CR to LF; PDF and PNG hashes are exact.

Primary source identities and pin/package rationale are recorded in
[the component review](../../../docs/stage4/recording-front-end-component-review.md).
The read-only audit proves saved design consistency. It does not prove analog
noise, worst-case switching behavior, single-fault protection, surgical
feasibility, or clinical/consumer efficacy.
