# SCCI_RH controller carrier

This native circuit gives the compiled nRF5340 backend a dedicated physical
carrier. It contains a Fanstel **BT40F** module, all **46 firmware GPIO**, a
four-device SN74LVC165A observation chain, matched peripheral connectors,
explicit common endpoint-CNV and driver-rearm joins, reset biases and SWD.
The complete circuit has **68 components, 328 physical pins and ten sheets**.

Open `controller_carrier.kicad_pro` in KiCad 10, or use
`OPEN_CONTROLLER_KICAD.cmd`. The PDF and SVG exports are inspectable without
KiCad. The board set imports this circuit with unique reference numbers;
the seven historical packages and their receipts remain unchanged.

- [Primary component review](../../../docs/stage4/controller-carrier-component-review.md).
- [Exact native connectivity](connectivity.json), [exported XML](controller_carrier.xml),
  [BOM](bom.csv) and [physical module pad geometry](module-pad-geometry.csv).
- [Native verification](verification.json), [actual saved-file MCP inspection](mcp-inspection.json)
  and [final PDF visual review](visual-review.json).
- [Complete board-set integration](../integrated-pcb/README.md).

Run the independent, read-only package check from the repository root:

```text
python electronics/stage4/controller-carrier/verify_controller_carrier.py
```

The module includes both crystals and internal regulator networks. Normal
voltage mode ties its VDD and VDDH pads to the same 3.3 V module rail. The
integrated carrier firmware derivative must select the manufacturer's 11 pF
internal HFXO load, while retaining the original backend pin map. USB and radio
are unused. The module's antenna exists physically, but no radio implementation,
range or through-body communication is claimed.

The parallel observation chain loads active route and native health together.
It carries 26 observations plus six fixed sentinel bits. These observations
do not replace the independently wired guards. Three independent rearm outputs
remain distinct: common driver rearm, phase-supervisor rearm 0 and rearm 1.

This is a digital bench design. Native ERC and pin/pad checks establish saved
connectivity; actual assembly, power ordering, oscillator accuracy, SPI edges,
analog behavior and biological benefit remain unmeasured.
