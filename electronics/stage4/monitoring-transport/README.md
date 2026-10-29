# SCCI_RH-S4-TRANSPORT-01 - monitoring and companion interfaces

**14 October 2026 - native digital design for artificial signals and loads**

Open [monitoring_transport.kicad_pro](monitoring_transport.kicad_pro) in KiCad,
or use [OPEN_IN_KICAD.cmd](OPEN_IN_KICAD.cmd). The package contains **60 components,
217 physical pins and eight editable schematic sheets**. A vector
[schematic PDF](monitoring_transport.pdf), individual [SVG sheets](svg/),
[BOM](bom.csv), local symbols, local footprint snapshots and explicit
[connectivity manifest](connectivity.json) accompany the native sources.

This is the observation and companion handoff in the proposed spinal
recording-interpretation-stimulation-feedback system. It adds actual ADC and
isolated UART circuitry without altering the earlier monitor, driver, recording,
router, supervision or power packages. It does not implement the host processor,
target firmware, physical PCB or a through-body radio.

## What the circuitry does

U1 is an **ADS8688IDBTR**, an eight-channel 16-bit ADC with a maximum aggregate
rate of 500 ksps. Its analog supply is HOST_5 and digital supply is HOST_3V3.
REFSEL is grounded to select its independent internal 4.096 V reference;
REFIO has 22 uF bypass and REFCAP has 22 uF plus 1 uF. These are nominal capacitor
allocations: actual effective capacitance and placement require PCB selection.
The source monitor's REF3440 remains separate, so reference mismatch belongs in
measurement uncertainty.

All eight channels are configured to unipolar 0 to 5.12 V in the companion
transport contract. This range gives an ideal 78.125 uV step, corresponding to
1.953125 uA in the existing nominal current transfer. These numbers describe
quantization, not measurement accuracy.

| ADC channel | Source and meaning |
|---|---|
| 0 | CH0_I_MON from the existing monitor; nominal 2.048 V + 40 V/A times current |
| 1 | CH1_I_MON with the same nominal transfer |
| 2 | CH0_VPAIR from supervision U502 pin 1; nominal 2.048 V + 0.0499 times driver A minus B |
| 3 | CH1_VPAIR from supervision U502 pin 7 with the same transfer |
| 4 | MON_VREF, the existing monitor's nominal 4.096 V reference |
| 5 | MON_VMID, its nominal 2.048 V midpoint |
| 6 | PACK_BUS through 4.99 kohm / 2.49 kohm |
| 7 | HOST_5 through 2.4 kohm / 2 kohm |

Each channel has a 100 ohm / 1 nF input network. The ADS8688 input resistance is
specified as 0.85 to 1.15 Mohm at 25 C, with maximum 25 ppm/C drift, and its
unipolar input network refers to an internal 2.5 V bias. That loading affects
both direct taps and dividers. The health divider Thevenin resistances are below
2 kohm. Neither the dividers nor the ADC replace the existing independent
hardware rail/current/voltage windows.

The ADC also has a typical internal low-pass bandwidth near 15 kHz. The high
sample allocation therefore oversamples a filtered observation. It does not
establish 200 kHz waveform bandwidth, precise edge timing or anti-alias rejection
under every possible input. The new finite study records this limitation and
nonuniform sampling. It does not earn the historical 4% phase-charge target.

## Separate buses and identities

J3 carries the dedicated raw ADC SPI bus. SDI and SCLK have 33 ohm damping,
CS has a default-high pullup, and RST_PD has a default-low pulldown. The proposed
clock is **16 MHz**, below the ADS8688 17 MHz maximum. Each default-format
32-clock transfer receives a 2.125 us allocation, including chip-select margins.
The schedule must retain the channel identity that existed before its command,
configuration/readback history and recovery after a lost frame. These are
transport-contract requirements; target DMA and interrupt timing are a later
implementation.

J4 and J5 connect through native nets to host handoff J20. They retain the
**two existing ADS8866 endpoint ADCs**, individual CNV/CS/DOUT lines, the shared
separate MON_SCLK bus and integrator/rearm controls. No duplicate charge ADC is
added. Endpoint aperture, readout availability and source identity remain
distinct. An endpoint-bus schedule cannot silently substitute raw ADC apertures.

J22 exposes the actual shared 8 MHz endpoint bus: pins 1/2 are MON_SCLK/MON_MISO,
pins 3/4 are source 0 CNV/CS, pins 5/6 are source 1 CNV/CS and pin 7 is GND.
R30 and R31 each join one ADC's tri-state DOUT to MON_MISO through 330 ohms.
The contract selects only one source during readout. J20 retains separate-DOUT
diagnostic taps; the series resistors do not validate simultaneous selection,
an unpowered endpoint or arbitrary cable capacitance. Physical bus loading and
target CS timing remain qualification requirements.

J6 and J21 similarly provide a passive handoff of existing health observations.
They add no permission logic. The native guard, timer, watchdog and deliberate
rearming circuits retain shutdown authority if the ADC or companion stops.

## Concrete wired companion interface

U20 is **ISO6721BDR**, the standard bidirectional 50 Mbps isolator with default
HIGH outputs, suitable for UART idle. Pins 1/4 use HOST_3V3/GND; pins 8/5 use an
externally supplied COMP_3V3/COMP_GND. Those grounds are not shorted. Host TX
crosses INB to OUTB at the companion; companion TX crosses INA to OUTA at the
host. The two inputs use 10 kohm idle pullups, limiting the specified 10 uA input
leakage drop to 0.1 V. Each side has 100 nF and 1 uF local bypass and 33 ohm line
damping.

J7/J8 expose a **1 Mbaud, 8N1 UART**. Its payload ceiling is 800 kbit/s before
packet overhead and reserved service. The normal processed-feature/pressure
contract can fit; simultaneous continuous export of every raw ADC and recording
sample cannot. Packet sequence, age, CRC, validity and configuration identity
must reject stale or ambiguous observations. A pressure value is an externally
estimated, timestamped quantity, not proof that a cuff directly measures the
selected spinal control state.

This circuit represents a short wired digital fixture and an external companion
endpoint. A manufacturer's functional isolation rating does not prove body
leakage, implanted isolation, cable ESD immunity or an RF link. Peer power is
external; the battery budget covers the host side separately from the companion.

## Checks and scope limits

[verify_monitoring_transport.py](verify_monitoring_transport.py) independently
compares every exported component value, footprint pad and pin net, checks the
manufacturer-specific ADC and isolator maps, input filters, dividers, default
pulls and passive handoffs, and checks the final exports/MCP/visual records.
Full-severity KiCad ERC has **zero violations and no ignored checks**. Actual
Konnect MCP inspected the saved sheets, component pins and geometry; this is not
unsaved PCB-editor evidence. All eight final PDF pages were visually reviewed.

Physical settling, reference accuracy, input clipping under faults, converter
noise coupling, ADC alias behavior, cable immunity and measured timing remain
unqualified. The existing ADS8866 integrator protection, INA bias bypass and
endpoint-dose uncertainty remain historical limitations. No biological outcome
or implanted safety follows from the circuit checks.

Run the read-only package verification from the repository root:

```text
python electronics/stage4/monitoring-transport/verify_monitoring_transport.py
```

Intentional regeneration uses build_monitoring_transport.py and native_render.py,
followed by KiCad netlist/PDF/SVG export, full ERC, MCP inspection, final rendered
page review and explicit receipt refresh. Routine verification writes nothing.

Primary component references: [TI ADS8688](https://www.ti.com/lit/ds/symlink/ads8688.pdf)
and [TI ISO6721](https://www.ti.com/lit/ds/symlink/iso6721.pdf).
