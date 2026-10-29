# Populated board index

Open the [master schematic project](integration/master/SCCI_RH_integrated.kicad_pro) with
`OPEN_MASTER_KICAD.cmd`. Each board has an explicit PCB Editor launcher below.
These use the installed KiCad executable and do not depend on Windows file associations.
On another installation set `SCCI_RH_KICAD_BIN` to its KiCad 10 `bin` directory.

The board set has 1,298 electrical positions, 1,296 fitted components and 32
mechanical mounting holes. Two optional driver capacitors remain DNP.
Native previews may show optional package placements; fitted STEP and placement
exports explicitly honor the original population flags. All geometry is nominal.

| Board | Native PCB / launcher | Fitted / positions | Size, mm | 3D / copper / fabrication |
|---|---|---:|---|---|
| Monitoring Cell | [PCB](boards/monitoring-cell/monitoring_cell.kicad_pcb) · [launcher](OPEN_MONITORING_CELL.cmd) | 71 / 71 | 120 × 145 | [STEP](exports/monitoring-cell/populated.step) · [top](exports/monitoring-cell/top.png) · [3D](exports/monitoring-cell/isometric.png) · [copper](exports/monitoring-cell/top-copper.svg) · [fabrication reference](exports/monitoring-cell/fabrication-reference/README.md) |
| Current Driver | [PCB](boards/current-driver/current_driver.kicad_pcb) · [launcher](OPEN_CURRENT_DRIVER.cmd) | 154 / 156 | 175 × 155 | [STEP](exports/current-driver/populated.step) · [top](exports/current-driver/top.png) · [3D](exports/current-driver/isometric.png) · [copper](exports/current-driver/top-copper.svg) · [fabrication reference](exports/current-driver/fabrication-reference/README.md) |
| Recording Front End | [PCB](boards/recording-front-end/recording_front_end.kicad_pcb) · [launcher](OPEN_RECORDING_FRONT_END.cmd) | 153 / 153 | 155 × 190 | [STEP](exports/recording-front-end/populated.step) · [top](exports/recording-front-end/top.png) · [3D](exports/recording-front-end/isometric.png) · [copper](exports/recording-front-end/top-copper.svg) · [fabrication reference](exports/recording-front-end/fabrication-reference/README.md) |
| Contact Router | [PCB](boards/contact-router/contact_router.kicad_pcb) · [launcher](OPEN_CONTACT_ROUTER.cmd) | 155 / 155 | 175 × 155 | [STEP](exports/contact-router/populated.step) · [top](exports/contact-router/top.png) · [3D](exports/contact-router/isometric.png) · [copper](exports/contact-router/top-copper.svg) · [fabrication reference](exports/contact-router/fabrication-reference/README.md) |
| Supervision | [PCB](boards/supervision/supervision.kicad_pcb) · [launcher](OPEN_SUPERVISION.cmd) | 479 / 479 | 300 × 250 | [STEP](exports/supervision/populated.step) · [top](exports/supervision/top.png) · [3D](exports/supervision/isometric.png) · [copper](exports/supervision/top-copper.svg) · [fabrication reference](exports/supervision/fabrication-reference/README.md) |
| Power | [PCB](boards/power/power.kicad_pcb) · [launcher](OPEN_POWER.cmd) | 156 / 156 | 175 × 185 | [STEP](exports/power/populated.step) · [top](exports/power/top.png) · [3D](exports/power/isometric.png) · [copper](exports/power/top-copper.svg) · [fabrication reference](exports/power/fabrication-reference/README.md) |
| Monitoring Transport | [PCB](boards/monitoring-transport/monitoring_transport.kicad_pcb) · [launcher](OPEN_MONITORING_TRANSPORT.cmd) | 60 / 60 | 125 × 140 | [STEP](exports/monitoring-transport/populated.step) · [top](exports/monitoring-transport/top.png) · [3D](exports/monitoring-transport/isometric.png) · [copper](exports/monitoring-transport/top-copper.svg) · [fabrication reference](exports/monitoring-transport/fabrication-reference/README.md) |
| Controller Carrier | [PCB](boards/controller-carrier/controller_carrier.kicad_pcb) · [launcher](OPEN_CONTROLLER_CARRIER.cmd) | 68 / 68 | 155 × 150 | [STEP](exports/controller-carrier/populated.step) · [top](exports/controller-carrier/top.png) · [3D](exports/controller-carrier/isometric.png) · [copper](exports/controller-carrier/top-copper.svg) · [fabrication reference](exports/controller-carrier/fabrication-reference/README.md) |

The [80-sheet PDF](integration/master/SCCI_RH_integrated.pdf),
[BOM](integration/populated-bom.csv), [harness](integration/harness.json),
[power](power-overlay.json) and [carrier firmware](firmware-profile/README.md)
connect the physical reference to its mechanism and operating assumptions.
Fabrication files are inspectable digital references; assembly and physical
performance have not been measured. Final mechanical packaging is Stage 5.
