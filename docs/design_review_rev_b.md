# Design review – latest built revision (Nov 2024)

**What was reviewed** (identified as the latest build from the Altium output-job timestamps):

| Board | Altium project | Outputs dated |
|---|---|---|
| Control board ("Redemption Edition") | `../archive/rev_b_2024-11_control_board_altium/` | 16 Nov 2024 |
| Power board | `../archive/rev_b_2024-11_power_board_altium/` | 26 Nov 2024 |
| UI board (encoder + 2 × 16-pin headers) | `../archive/rev_b_2024-11_ui_board_altium/` | – |

Older revisions (`../archive/rev_a_2024-05_altium/` V1, May 2024, and `../archive/rev_a2_2024-07_cheaper_altium`, Jul 2024) were not reviewed in depth.

**Method**: the `.SchDoc` files were parsed directly (`../archive/rev_b_netlists/altium_schdoc_netlister.py`), and a netlist was
rebuilt from pin, wire, label and port geometry (`../archive/rev_b_netlists/netlist_*.txt`). The two power-board errors
were then reproduced in LTspice (`../simulation/00_baseline_rev_b/00_baseline_rev_b.asc`).
Findings are from the **schematics**. If a board was bodged after assembly, check the item against the board.

In this document "Rev B" means the Nov 2024 boards and "Rev C" the proposed new power board.

## Verdict
- **Control board: keep it.** Its core (STM32F103RET6, MCP4725 + REF5040 4.096 V, TPS5430 / AMS1117 power tree,
  USB-UART, the 16-pin power-board interface) is sound. It has one functional bug (the fan driver can never turn on)
  and some limitations, but nothing that stops a 150 W load. The Rev C power board was designed to plug
  into it unchanged.
- **Power board: replace it (Rev C).** It has two critical errors (gate drive, VSEN amplifier) and is
  thermally sized for well under 150 W. Its good ideas are carried forward: one op-amp loop per MOSFET,
  2 × 0.2 Ω 2512 source resistors per FET, the RC drain snubber, the fuse, and the 16-pin pinout.

## Power board (`DC Electronic Load Power MOSFETS`)

| # | Severity | Finding | Evidence | Rev C fix |
|---|---|---|---|---|
| P1 | **Critical** | The gate-drive op-amp U3 (LMV358) is powered from **+4.096 V** (REF5040 output). Its output can't exceed ~4.1 V, but IRF530 VGS(th) is 2–4 V (datasheet), plus 0.3–0.6 V across the source resistor. Full scale is only reachable with a lucky low-Vth part. | MOSFETs.SchDoc: U3.8 = +4.096V. Deck 00: 5.7 / 2.0 / **0.04 A** per channel for Vth 2 / 3 / 4 V against a 6.1 A target. | LT1014 on +12 V: ≥ 10 V of gate drive available. |
| P2 | **Critical** | **VSEN difference amp has positive feedback.** R1 (2 k feedback) goes from OUT B (pin 7) to **+IN B** (pin 5), together with R2 from DUT+. R4 (2 k to GND) goes to −IN B with R3 from DUT−. The output latches to a rail. | Power Monitor.SchDoc nets: `R1.1 R2.2 U1.5(+IN B)`, `R1.2 U1.7(OUT B)`, `R3.2 R4.1 U1.6(−IN B)`. Deck 00: output 4.10 V at DUT = 12 V (should be 1.20 V). | Swap R1/R4 (the correct topology), now with 200 k/10 k on an LT1013 at 12 V. |
| P3 | Major | **Thermal capacity well below 150 W.** 2 × IRF530 (TO-220, RθJC ≈ 1.7 K/W, 88 W at Tc = 25 °C). At 75 W per FET, even a perfect heatsink gives Tj ≈ Tsink + 200 °C. | Deck 05 (2 FETs) and the hand calculation in `mosfet_selection.md`. | 4 × TO-247 (IRFP250N), fan, measured heatsink. |
| P4 | Major | Gate-drive op-amps and the INA240 run from the **precision reference rail** (REF5040, 10 mA maximum), which also sets the DAC full scale. Gate-charge transients and load changes couple into the setpoint. The design notes chose this because the 5 V/USB rail is noisy, which is a valid concern, but 12 V is available on pin 16. | MOSFETs / Power Monitor sheets: U1, U2, U3 VS = +4.096V. | All op-amps on +12 V. The reference only feeds high-impedance offset and NTC networks (< 1 mA). |
| P5 | Major | The common 5 mΩ shunt R5 sits between the source resistors and GND, but the loop references GND. Each channel then regulates `I_ch·0.1 + I_total·0.005`, which couples the two loops and costs ~10 % of gain. | Nets `Rshunt` / R5 / GND. | Shunt removed. ISEN = mean of the four source-resistor voltages (4 × 10 k into a ×12 amplifier): the same resistors, no coupling. |
| P6 | Major | ISEN (INA240A2 on 4.096 V) and VSEN can drive up to ~4.05 V into STM32 PA1/PA2. Those are **not 5 V-tolerant** (analog pins, abs max VDDA + 0.3 V). There is no series resistor or clamp. | INA240 OUT → P1.5 → PA1 directly. | 1 k + 10 n + BAT54S clamp to 3V3 on both outputs. Scaling keeps ≤ 3.3 V at full scale. |
| P7 | Major | **No hardware protection** on the power board: no over-temperature cut-off, no dropout/anti-wind-up (the D1 "OCP trip" and D2 "thermal runaway" lines from the design notes were dropped). Deck 04 shows the generic consequence: 115–170 A spikes on DUT hot-plug or recovery. | IO.SchDoc: no fault lines; no comparator on the board. | LM339: OTP pull-down on V_SET, dropout → KILL line into every In−, fan thermostat. Deck 04: peak = setpoint. |
| P8 | Minor | Compensation (3.3 k / 220 p / 100 Ω) is fine for IRF530 but gives **−13° to 25° phase margin** with a large-die or linear-rated MOSFET at 2.5 A. A part swap could make it oscillate. | Tuning sweep; deck 03 history. | 3.3 k / 1 nF / 47 Ω: ≥ 80° for every candidate. |
| P9 | Minor | TEMP_IN+ goes off-board to a "10K_NTC" net label that has no part. On the control board it is pulled up by 470 Ω from 12 V (≈ 60 mW of NTC self-heating when hot). | Top.SchDoc label `10K_NTC`. | NTC handled locally on the power board. TEMP_IN+ left NC (DNP option). |
| P10 | Info | Good: per-FET loops (true current sharing), 0.2 Ω ∥ 0.2 Ω 2512 sources, 2.2 Ω + 2.2 µF snubber, 20 A fuse holder, test points on gates and sources. | – | All kept. |

## Control board (`DC Electronic Load Redemption Edition`)

| # | Severity | Finding | Evidence | Action |
|---|---|---|---|---|
| C1 | **Functional bug** | **The fan can never turn on.** LM311 U7 is open-collector (pin 1 EMIT OUT to GND). Its pin 7 goes through R21 (470 Ω) to Q2's base, but **nothing pulls the base up**, so Q2 never gets base current. | Thermal.SchDoc nets: `R21.1 U7.7`, `C25.1 Q2.1(B) R21.2`. No other connection. | Not needed with Rev C, which drives the fan from the power board. To fix Rev B: 2.2 k from +12 V to U7 pin 7. Fix properly in the KiCad redo. |
| C2 | Limitation | The MCU cannot read temperature. TEMP_IN+ only reaches the LM311 thermostat, and that comparator has no hysteresis (fan chatter). | Thermal.SchDoc. | KiCad Rev D: NTC to a free ADC pin (PA0 / PA3 are unused). |
| C3 | Limitation | The 16-pin interface has **7 GND pins and no fault or enable line**. The MCU can't hard-disable the power stage or see a trip. | Top.SchDoc P3 pinout. | Rev C works around it (local protection; firmware sees a trip as ISEN ≈ 0 with a non-zero setpoint). Rev D: re-assign 2 GND pins to /FAULT and /ENABLE. |
| C4 | Accuracy | The ADC reference is VDDA = AMS1117 3.3 V (±1–2 %, drifts). The F103 has no factory-calibrated VREFINT, so absolute readback is ±2 % until calibrated. | Microcontroller.SchDoc. | Two-point calibration against a DMM (firmware). Rev D option: ADS1115 (its datasheet is already in `../datasheets/`) referenced to the 4.096 V reference. |
| C5 | Safety | The MCP4725 powers up at its **EEPROM value**. If the EEPROM is not 0x000, the load turns on at power-up. | DAC.SchDoc. | Firmware writes 0x000 to EEPROM once. Rev C's KILL/OTP do not cover this case. |
| C6 | Minor | R14 (10 k) on LOAD_CTRL plus the Rev C divider (16 k) load the DAC with 6.2 k. That's fine for the MCP4725, but it may lose a few LSBs at the top of the range. | DAC.SchDoc. | Fit R14 = 100 k or DNP on the next spin. |
| C7 | Cosmetic | Firmware comment says "MCP4725 A0 grounded", but the schematic pulls A0 high (R15 4K7 to 4.096 V). The address 0x61 in the code is correct. | `main.c` line 35. | Fix the comment. |
| C8 | Info | `Digital IO.SchDoc` is referenced by `Top.SchDoc` but is not in the folder (keypad / LCD sheet). | Folder listing. | Recover it before the KiCad port, or re-draw it. |
| C9 | Info | Firmware is bring-up only (DAC triangle sweep, one ADC channel at 1.5 cycles). No control logic exists yet, so nothing has to be ported. | `main.c`. | See `firmware_requirements.md`. |

## UI board
Two 16-pin 2 mm headers and a PEC11L encoder. Designators are unannotated (`J?`, `ENC?`). The encoder's switch pins 1/2 are not
connected. Annotate and finish it in KiCad.
