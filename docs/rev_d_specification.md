# DC Electronic Load Rev D: specification

One board, galvanically isolated, powered from a single USB-C port, with a local 7-segment front panel.
150 W, 0.6 to 58 V, 0 to 10.2 A. Hardware CC and CV; CR, CP and battery discharge in firmware on top of the CC loop.

The analog stage (per-MOSFET LT1014 loops, sense amplifiers, LM339 protection, hardware CV) is the Rev C design that was
verified in LTspice (`../simulation`, decks 01 to 06). `hardware/tools/check_netlist_revd.py` proves, node by node, that the
Rev D KiCad netlist is that simulated circuit. Everything digital is new in Rev D.

Drawing conventions (A3, JetBrains Mono, block frames, no overlaps, 3-wire junctions, hop-overs, power tree) are listed in `../hardware/README.md`
and enforced by the generator's lint pass.

## 1. Why Rev D (what was wrong with the Rev B control board + Rev C power board)

| Problem | Rev D answer |
|---|---|
| No isolation: DUT minus was USB ground, so an earth-referenced DUT or a floating battery stack could push load current through the PC | ISO7761 digital isolator + 1 W isolated DC-DC. The whole analog stage floats on the DUT minus terminal |
| Two USB-C ports (CH340 UART + a second one for DFU) and a 12 V barrel jack | One USB-C: power, USB CDC (SCPI), USB DFU in ROM. Fan 12 V is made on board by a boost converter |
| STM32F103RET6 in LQFP64 | STM32G0B1CBT6 in LQFP48: USB DFU in ROM, crystal-less USB, cheaper and smaller. The F103 has no USB bootloader and needs a crystal, so it would have kept the second port |
| REF5040 reference + trimmer + MCP4725 (DAC uses VDD as reference, EEPROM power-up value) | MCP4822 (internal reference, 0 V at power-up) and ADS1118 (internal 0.01 % reference). No precision reference, no trimmer |
| STM32F103 12-bit ADC on an AMS1117 reference: ±2 % readback until calibrated | ADS1118, 16 bit, 7 ppm/K, 860 SPS, reads ISEN, VSEN, heatsink NTC and the live V_SET node |
| Fan driver could never turn on (LM311 output had no pull-up); MCU could not read temperature; no /FAULT or /ENABLE line | MCU runs the fan from the ADC temperature; LOAD_OFF line through the isolator; hardware OTP/OVP/NTC-open stay independent of firmware |
| Two boards, a 16-pin cable, an unannotated UI board | One PCB, 7-segment readouts for V, A and the set value, 8 status LEDs, encoder and 3 buttons |
| Schematic text unreadable (1.27 mm text on sparse A3 sheets) | A4 sheets where the circuit fits, 1.5 mm outline-font text, 2 mm block titles, colour-coded nets, legend, barrier drawn |

## 2. Ratings

| Parameter | Value | Basis |
|---|---|---|
| Current | 0 to 10.2 A, four equal channels of 2.56 A | 2.50 A/V × 0 to 4.095 V LOAD_CTRL (deck 01) |
| Set resolution | 2.44 mA per DAC LSB (12 bit) | MCP4822 channel A |
| Zero offset | about −72 mA: the first 29 codes give 0 A | deliberate +1.8 mV op-amp offset so code 0 is truly 0 A |
| DUT voltage | 0.6 to **58 V** operating; OVP trips at 62 V; MOSFETs 200 V | 58 V is the DC rating of the fuse (0997015.WXN); dropout detector disables the load below 0.45 V |
| Modes in hardware | CC; CV 0.1 to 10 A with LOAD_CTRL as the current ceiling | deck 06. Below 0.1 A CV hunts |
| Full current from | about 1 V at the terminals | deck 01 |
| Power | **150 W continuous with a fan**, about 55 W without | deck 05; heatsink Rsa still to be measured (`heatsink_and_thermal.md`) |
| Step response | 21 to 31 µs (10 to 90 %), 0 % overshoot | deck 02 |
| Stability | PM ≥ 80°, GM ≥ 13 dB, all MOSFET candidates, 1 to 10 µH leads | deck 03 |
| Readback | ISEN 0.300 V/A + 0.15 V (0.4 mA/LSB); VSEN 0.049 V/V + 0.10 V (2.5 mV/LSB), true 4-wire | ADS1118 at ±4.096 V FSR |
| Protection | 15 A 58 V fuse, TVS, OTP 85 °C, OVP 62 V, NTC-open, dropout/KILL anti-wind-up, hardware OFF, gate zeners, ADC clamps | decks 04, 06; spec table below |
| **Not protected in hardware** | **Power.** 58 V × 10 A is reachable if firmware misbehaves. The heatsink OTP is far too slow to save the die | firmware power limit is safety-critical (`firmware_requirements.md`, item 2) |
| Isolation | USB side to analog side: 150 V DC working voltage, barrier 4 mm | section 5 |
| Supply | USB-C 5 V, 0.8 A with the fan running, 0.35 A without | section 4 |

## 3. Architecture

```
USB-C ──┬── VBUS 5 V ──┬── AP2112K ── +3V3 ── STM32G0B1CBT6 ── SPI2 ── 74AHCT125 ── MAX7219 ×2 ── 3 × 4-digit 7-seg, 8 LEDs
        │              │                          │   │  └── TIM3 encoder, 3 buttons, fan PWM/tach/enable, CC1/CC2 ADC
        │              ├── MT3608 boost ── +12V_FAN ── AO3401 switch ── 4-pin PWM fan
        │              └── B0512S-1WR3 ═══ barrier ═══ +12V_RAW ─┬─ 4.7 Ω / 22 µF ── +12V_ISO (op-amps, LM339, pull-ups)
        └── D+ / D− ── USBLC6 ── USB FS               │          └─ MCP1703 ── +5V_ISO (DAC, ADC, isolator side 2, thresholds)
                                                      │
   SPI1 + /CS_DAC + /CS_ADC + LOAD_OFF ── ISO7761 ═══ barrier ═══ MCP4822 ── A: LOAD_CTRL ── /16 ── V_SET ── 4 × (LT1014 + IRFP250N + 2 × 0.2 Ω)
                                                      │                  └─ B: CV_SET ── LT1013 error amp ── Q13 pulls V_SET down
                                                      └── ADS1118 ◄── ISEN (mean of 4 Rs), VSEN (4-wire diff amp), V_NTC, V_SET
   LM339: OTP (85/70 °C) ── Q11 ─┐
          NTC-open, OVP (62 V), LOAD_OFF ── diode-OR ── Q12 ─┴── short V_SET to AGND
          dropout (DRAIN < 0.45 V) ── KILL ── 4.7k + 1N4148 into every channel's inverting input
   DUT+ ── 15 A / 58 V fuse ── DRAIN bus ── 4 drains; sources ── 2 × 0.2 Ω ── PGND ── NT1 (star) ── AGND
```

Grounds: **DGND** (USB side), **AGND** (isolated analog reference), **PGND** (DUT minus and the source resistors). AGND and PGND
meet only at net tie NT1, placed at the centroid of the four Rs bottom pads.

## 4. Power budget (USB-C, 5 V)

| Consumer | Current at 5 V |
|---|---|
| Isolated DC-DC (12 V × 30 mA / 0.75 efficiency + 5 V rail) | 0.12 A |
| STM32 + isolator side 1 + LEDs | 0.06 A |
| MAX7219 displays (ISET 33 k, intensity mid) | 0.10 to 0.15 A |
| Fan 12 V × 0.15 to 0.25 A through the boost (0.85 efficiency) | 0.25 to 0.45 A |
| **Total** | **0.55 to 0.8 A** |

The CC1/CC2 pull-downs (5.1 k) make the board a USB-C sink; the MCU reads the CC voltage to learn the source limit (0.4 V = 500 mA default,
0.9 V = 1.5 A, 1.7 V = 3 A). On a 500 mA source the firmware keeps the fan at minimum and caps power at 55 W.

## 5. Isolation design

Voltage blocks: **A** = USB side (DGND, earth-referenced through the PC), **B** = analog side (AGND/PGND = DUT minus, up to 58 V above
it on DRAIN). B floats with the DUT, so the A-to-B working voltage is whatever the DUT minus terminal sits at relative to earth.

| Pair | Grade | Working voltage (design limit) | IEC 60664-1 (PD2, material group IIIb, internal transient = V + 1200 V) | IPC-2221B B2 × 1.2 | Board rule |
|---|---|---|---|---|---|
| A to B | functional (bench instrument, no user-touchable live part) | 150 V DC | clearance 0.5 mm, creepage 1.6 mm | 0.72 mm | **4.0 mm** on every layer, no copper crosses |
| DRAIN to AGND (inside B) | functional | 60 V (77 V TVS clamp) | 0.5 / 1.24 mm | 0.72 mm | 1.5 mm |

Parts on the barrier: ISO7761DW (5 kVrms, 8 mm creepage), B0512S-1WR3 (3 kVDC). Hipot for the assembled board: 1 kV DC for 1 s A to B.
Not for mains-referenced work: the rating is set by the 4 mm PCB gap, not by the parts. Enclosure, USB shield, encoder shaft and buttons are
on side A; binding posts, heatsink hardware and NTC lug are on side B (insulated TO-247 mounting, plastic NTC lug).

## 6. Connectors

| Ref | Function | Pinout |
|---|---|---|
| J1 | USB-C 2.0 receptacle (HRO TYPE-C-31-M-12) | power, D+/D−, CC1/CC2 to the MCU ADC |
| J2 | Fan, JST-XH 4 | 1 GND, 2 +12 V (switched), 3 tach, 4 PWM 25 kHz open-drain. 2/3-wire fans: pins 1 to 3, on/off only |
| J3 | SWD | 1 +3V3, 2 SWDIO, 3 SWCLK/BOOT0, 4 NRST, 5 GND |
| J4 | Debug UART 3.3 V | 1 GND, 2 TX, 3 RX |
| J5 | I2C expansion (0.96" SSD1306 OLED module) | 1 GND, 2 +3V3, 3 SCL, 4 SDA |
| J6 | Heatsink NTC 10 k B3950, JST-XH 2 | isolated side |
| J7, J8 | DUT+, DUT− solder lugs to ≥ 15 A binding posts | isolated side |
| J9 | 4-wire sense pair, JST-XH 2 | 100 Ω local fallback when open |

## 7. Thresholds (all ratios of +5V_ISO, so independent of its absolute value)

NTC: 10 k B3950 on the heatsink next to FET 2, fed from +5V_ISO through 10.0 k 0.1 %. V_NTC = 2.50 V at 25 °C, 1.52 V at 45 °C, 0.75 V at 70 °C, 0.49 V at 85 °C.

| Comparator (LM339, open collector, 10 k pull-ups to +12V_ISO) | Threshold network | Trip / release | Acts on |
|---|---|---|---|
| U14A over-temperature | In+ 90.9 k / 10.0 k = 0.099 × rail, 402 k hysteresis; In− = V_NTC | 85 °C / 70 °C | Q11 shorts V_SET |
| U14B dropout / KILL | In+ 100 k / 10.0 k = 0.045 × rail, 165 k hysteresis; In− = DRAIN via 47 k + 12 V zener | DRAIN < 0.45 V / > 0.54 V | KILL into every channel (anti-wind-up) |
| U14C NTC open | In+ = V_NTC; In− 10.0 k / 27.4 k = 0.73 × rail (3.66 V) | NTC > 27 k (open, or below 3 °C) | OFF_GATE through BAT54C |
| U14D over-voltage | In+ = VSEN_OA via 10 k, 1 M hysteresis; In− 5.90 k / 10.0 k = 0.629 × rail (3.15 V) | 62 V / about 60 V | OFF_GATE through 1N4148 |
| LOAD_OFF_ISO (from the MCU through the isolator) | 5 V logic into the same BAT54C | high = OFF; default high when the USB side is dead | OFF_GATE → Q12 |

## 8. Transfer functions and calibration

| Quantity | Nominal | Calibrate |
|---|---|---|
| Set current | I = 2.50 A/V × (V_DAC − 0.0288 V), clamp ≥ 0 | 2 points (0.5 A, 8 A) against a DMM in series |
| CV set-point | V_CVSET = 0.049 × V_DUT + 0.10 V | same scale as VSEN |
| ISEN (ADC AIN0) | 0.300 V/A × I + 0.15 V | zero with the load off; gain at 8 A |
| VSEN (ADC AIN1) | 0.0490 × V_DUT + 0.10 V | zero with the DUT shorted (load off); gain at a known 24 V |
| V_NTC (ADC AIN2) | B3950 equation, rail-ratiometric | one point at room temperature |
| V_SET (ADC AIN3, PGA ±256 mV) | 25.6 mV/A; read-back of the node the loops follow | none; it is a diagnostic |

ADS1118: internal reference, single-ended against AGND, 128 to 860 SPS. The MCP4822 internal reference is ±2 %; the two-point calibration absorbs it.

## 9. Digital interface over the barrier

SPI mode 0 (CPOL 0, CPHA 0 for the MCP4822; ADS1118 mode 1), ≤ 2 MHz because of the 11 ns isolator delay on each direction. Channels:
SCK, MOSI, /CS_DAC, /CS_ADC, LOAD_OFF forward; MISO back. ISO7761 (no F suffix) outputs default **high**: with the MCU in reset,
unpowered or the firmware crashed, both chip selects are de-asserted and LOAD_OFF is asserted. 10 k pull-ups on the MCU side give the same
guarantee while the MCU pins are high-impedance.

## 10. Front panel

Three 0.56" 4-digit common-cathode displays (VOLTS 0.000 to 58.00, AMPS 0.000 to 10.00, SET), driven by two MAX7219 in a chain behind a
74AHCT125 (MAX7219 VIH is 3.5 V). Eight status LEDs (CC, CV, CR, CP, BATT, ON, FAULT, REMOTE) on digit 4 of the second MAX7219.
PEC11L encoder on TIM3 with 10 k / 10 nF filters, push = digit select. Buttons: ON/OFF, MODE, MENU. J5 takes an OLED module for menus.

## 11. Layout rules

1. **Barrier**: 4 mm gap under the ISO7761 and the DC-DC, no copper on any layer, no plane. Keep the two sides' decoupling on their own side.
2. **Kelvin everything around Rs** (unchanged from Rev C): each channel's Rf and ISEN averaging resistor connect at the top pad of that channel's Rs pair on their own trace; op-amp ground at the bottom pads.
3. **Star ground**: NT1 at the centroid of the four Rs bottom pads; take DUT− from the same point. 1 mΩ between an Rs and NT1 is 10 mV at 10 A (4 % of full scale).
4. **Gate**: 47 Ω within 10 mm of the gate pin; 100 k and 15 V zener at the FET pins.
5. **High-current path**: DUT+ → fuse → DRAIN bus → drains; sources → Rs → PGND. ≥ 5 mm of 2 oz copper, or a soldered wire. TVS and snubber across DRAIN/PGND at the terminals.
6. **R45, R48 (200 k) and R60 (47 k) see 60 V**: 1206. ≥ 1.5 mm from DRAIN copper to anything else on the analog side.
7. **Boost converter** (MT3608): tight loop L1-D3-C4, away from the barrier and from the USB data pair.
8. **ADC and DAC** next to the isolator on the analog side; the 1 k / 10 nF RC on AIN3 at the ADC pin.
9. **MAX7219 and displays** on the front edge; 74AHCT125 next to the MCU. Nothing from the USB side under the analog section.
10. **Thermal**: LT1014 close to the FETs but not on the heatsink edge; the four TO-247 along the heatsink at ≥ 25 mm pitch (`heatsink_and_thermal.md`).

## 12. Bring-up (summary; write the full plan before first power)

1. Unpowered: DUT+ to DUT− > 100 kΩ; each gate to source about 100 kΩ; DGND to AGND open (> 10 MΩ); DGND to PGND open.
2. USB from a current-limited supply or a USB power meter, no DUT: +3V3, VBUS, +12V_ISO (12 to 14 V), +5V_ISO (5.00 V ± 2 %). Current < 150 mA. All gates < 0.1 V. KILL about 2 V (dropout active with no DUT). LOAD_OFF_ISO high.
3. Enumerate: USB DFU with BOOT held at reset; then CDC with firmware. Displays show a test pattern, encoder and buttons register.
4. Firmware releases LOAD_OFF; DAC A = 0.1 V with a 5 V / 1 A-limited bench supply as DUT: 0.25 A − 72 mA ≈ 0.18 A, equal on all four sources (S1 to S4 about 4.4 mV). V_SET read-back on AIN3 matches.
5. Sweep to 1 A then 5 A at 5 V (25 W). ISEN/VSEN against a DMM; record calibration points.
6. Heat-gun the NTC: fan from the firmware at 45 °C, OTP trip at about 85 °C (current 0, AIN3 shows V_SET pulled down), release at 70 °C.
7. OVP: 62 V from a supply through a 1 k resistor onto VSEN only (not the DRAIN bus), or raise CV_SET and the DUT voltage; current must go to 0.
8. Step test: 1 A ↔ 9 A at 12 V, 100 Hz; scope a source node against deck 02 (21 to 31 µs, no ringing); add 1 m of loose lead.
9. Hipot 1 kV DC between DGND and AGND for 1 s, leakage < 10 µA.
10. Heatsink characterisation, then a 150 W soak with the fan for 30 min while logging the temperature.

## 13. Items to verify before ordering the PCB

- [ ] **PS1 pin numbering.** The SIP-4 footprint and symbol assume 1 VIN+, 2 VIN−, 3 VOUT−, 4 VOUT+. Check the datasheet of the exact part (Mornsun B0512S-1WR3 vs Murata NXE1S0512MC differ) and fix the footprint in `hardware/libraries/footprints/dcload.pretty`.
- [ ] CC56-12 / 5641AS display pinout against the part bought.
- [ ] MAX7219: genuine MAX7219CWG or a clone; clones work but check VIH behaviour.
- [ ] STM32G0B1: set option bit nBOOT_SEL = 0 once so the BOOT button works (factory default ignores the pin).
- [ ] Fan: 4-pin PWM fan preferred; measure its current for the USB budget.
- [ ] Heatsink Rsa with and without the fan, then the firmware power limits.
- [ ] Hysteresis values on the bench (bring-up step 6): they assume the LM339 output high level of 12 V through 10 k and about 2 V on the clamped KILL line.

## 14. Cost estimate (single unit, distributor prices, excluding PCB, heatsink, fan, enclosure)

LT1014 $9, 2 × LT1013 $7, 4 × IRFP250N $8, STM32G0B1CBT6 $3.5, ISO7761 $4, ADS1118 $5, MCP4822 $3, DC-DC $2.5, 2 × MAX7219 $3 (clones) to $16 (genuine),
3 displays $3, USB-C and connectors $3, passives and the rest $12. **About $70 to $85.** Removed from Rev B/C: REF5040, trimmer, CH340, TPS5430, second USB-C, 16-pin cable.
