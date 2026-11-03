# DC Electronic Load Rev E: specification

Rev E is the Rev D architecture built as cheaply as the JLCPCB / LCSC catalogue allows, without giving up the isolation, the per-channel loops or
the hardware CV. Two boards on one **2-layer** fabrication panel: a **control board** (USB side: USB-C, MCU, OLED header, encoder, buttons, blower
driver; the vertical front panel, 170 × 40 mm) and a **power board** (isolator, isolated supply, DAC/ADC, the four loops, protection, FETs; 170 × 60 mm,
exactly the heatsink base, lies flat on it), joined by a 12-way IDC ribbon cable that carries only USB-side digital and 5 V / 3.3 V. Galvanically
isolated, powered from a single USB-C port, local OLED + encoder UI. 150 W, 0.6 to 58 V, 0 to 10.1 A. Hardware CC and CV; CR, CP and battery
discharge in firmware on top of the CC loop.

The analog stage is the Rev C design (per-MOSFET loops, sense amplifiers, LM339 protection, hardware CV) with the LT1014 / LT1013 replaced by two
TLV9154 quads and the zero-offset resistor changed to suit. It was re-simulated with TI's TLV915x model in `../simulation/rev_e` (decks 01 to 04 and
06; the Rev C decks and their results are kept untouched as the reference). `hardware/tools/check_netlist_reve.py` proves, node by node, that the
Rev E KiCad netlist is that simulated circuit. Every bought part carries its LCSC code in the schematic; `hardware/outputs/rev_e_v1/BOM_RevE_JLC.csv`
is the live-priced BOM.

Drawing conventions (A3, JetBrains Mono, block frames, no overlaps, 3-wire junctions, hop-overs, power tree) are listed in `../hardware/README.md`
and enforced by the generator's lint pass. Page 1 is a block diagram: each sheet is a block, each connection a wire between sheet pins.

## 1. Rev D to Rev E: what was cut, what it cost, what it changed

| Rev D | Rev E | Saving (1 unit, JLC prices) | Consequence |
|---|---|---|---|
| LT1014 + 2 × LT1013 ($24 at LCSC) | 2 × TLV9154IDR (16 V RRIO quad, 4.5 MHz, Vos 0.83 mV max), $2.70 | $21 | Rb 22M → 15M: deliberate offset +2.6 mV, dead zone 106 mA (42 DAC codes) instead of 72 mA. Loop margins re-simulated: IRFP250N / 240 / 530 PM ≥ 87°, GM ≥ 22 dB; the big-die IXTH proxy falls to 80° / 9 dB and overshoots on hot-plug (section 2) |
| 2 × MAX7219, 74AHCT125, 3 × 4-digit displays, 8 LEDs | 1.3" SH1106 (or 0.96" SSD1306) I2C OLED module on J5, 2 LEDs (ON, FAULT) | $8 to $20 | Mode and REMOTE are shown on the OLED; the module is an off-board AliExpress item (about $2.50) |
| MT3608 boost, 10 µH, SS34, 2 × 22 µF for a 12 V fan | 5 V 5015 blower on VBUS through the existing P-FET switch | $2 | Lower static pressure: measure Rsa with the duct (`heatsink_and_thermal.md`). USB draw about 0.45 A total |
| MCP1703 5 V LDO ($1.41, 18 in stock) | L78L05 SOT-89 ($0.07) | $1.30 | +5V_ISO is 4 % instead of 0.4 %: every threshold is a ratio of the rail and the DAC / ADC carry their own references, so nothing depends on it |
| ISO7761DW ($2.85) | CA-IS3761HW ($1.85, pin-compatible, 5 kVrms, default-high outputs; the TI part drops in) | $1 | none |
| STM32G0B1CBT6 LQFP48 ($8.58, 0 stock at JLC) | STM32G0B1RBT6 LQFP64 ($3.45, 958 in stock; same die, same pin names) | $5 | 10 × 10 mm package; 20 more NC pins. (STM32F103C8T6 would be $1.50 but has no ROM USB DFU and needs a crystal) |
| Bourns PEC11L ($4.50) | Bourns PEC11R-4215F-S0024 ($2.37; any EC11 with switch fits) | $2 | none |
| Würth REDCUBE M4 studs ($4 to $8) | plated 4.3 mm holes with 10 mm pads, M4 bolt + ring lug | $4 to $8 | the lug sits under the bolt head |
| Keystone 3568 mini-blade holder ($3.26) | fuse soldered into `Fuse_Blade_Mini_directSolder` (Littelfuse 178.6764.0001, $1.84, if you want it pluggable) | $3 | a blown fuse means a shorted FET, so the board is on the bench anyway |
| 13 × 0.1 % resistors | all 1 % | $2 | section 8 lists the known errors; the two-point calibration absorbs them |
| 4-layer 200 × 120 mm panel | 2-layer 2 oz 170 × 100 mm panel | about $25 to $40 per 5 boards | DGND / AGND are ground pours instead of planes; the barrier rule and the star point are unchanged |

Kept on purpose: the galvanic isolation (the reason Rev D exists), the MCP4822 (a PWM DAC would save $2.40 and lose µs set-point settling), the
hardware CV loop (about $1 once the LT parts are gone), the ADS1118 ($1.72 at LCSC), the IRFP250N (genuine Infineon, $1.00; not the sub-$1 clones),
USB-C as the only power input (a 12 V barrel input would add about $1 and a second cable for nothing the 5 V blower cannot do).

## 2. Ratings

| Parameter | Value | Basis |
|---|---|---|
| Current | 0 to 10.1 A, four equal channels of 2.53 A | 2.50 A/V × 0 to 4.095 V LOAD_CTRL minus the 106 mA zero offset (rev_e deck 01) |
| Set resolution | 2.44 mA per DAC LSB (12 bit) | MCP4822 channel A |
| Zero offset | about −106 mA: the first 42 codes give 0 A | deliberate +2.6 mV op-amp offset (15M from +12V_ISO) so code 0 is truly 0 A with the TLV9154's 0.83 mV Vos limit |
| DUT voltage | 0.6 to **58 V** operating; OVP trips at 62 V; MOSFETs 200 V | 58 V is the DC rating of the fuse (0997015.WXN); dropout detector disables the load below 0.45 V |
| Modes in hardware | CC; CV 0.1 to 10 A with LOAD_CTRL as the current ceiling | rev_e deck 06. Below 0.1 A CV hunts |
| Full current from | about 1 V at the terminals | deck 01 |
| Power | **150 W continuous with the blower**, about 25 W without | deck 05 (unchanged from Rev C); heatsink Rsa still to be measured (`heatsink_and_thermal.md`) |
| Step response | about 20 to 30 µs (10 to 90 %), no overshoot with the planar FETs | rev_e deck 02 |
| Stability | PM ≥ 87°, GM ≥ 22 dB for IRFP250N / IRFP240 / IRF530, 50 mA to 2.5 A per channel, 1 to 10 µH leads. The IXTH big-die proxy: 80° / 9 dB | rev_e deck 03 |
| Readback | ISEN 0.300 V/A + 0.15 V (0.4 mA/LSB); VSEN 0.049 V/V + 0.10 V (2.5 mV/LSB), true 4-wire | ADS1118 at ±4.096 V FSR |
| Protection | 15 A 58 V fuse, TVS, OTP 85 °C, OVP 62 V, NTC-open, dropout/KILL anti-wind-up, hardware OFF, gate zeners, ADC clamps | rev_e deck 04; thresholds in section 7 |
| **Not protected in hardware** | **Power.** 58 V × 10 A is reachable if firmware misbehaves. The heatsink OTP is far too slow to save the die | firmware power limit is safety-critical (`firmware_requirements.md`, item 2) |
| Isolation | USB side to analog side: 150 V DC working voltage, barrier 4 mm | section 5 |
| Supply | USB-C 5 V, about 0.45 A with the blower running, 0.25 A without | section 4 |

Model-dependent note for the big-die proxy (rev_e decks 03 and 04): with the 6× faster op-amp the IXTH88N30P stand-in keeps 80° of phase margin but
its gain margin drops to 9 dB and its hot-plug / recovery peak is 13.2 A instead of the 8.1 A set point. The planar FETs in the BOM show 8.09 A, i.e. no
overshoot. If a large-die linear FET is ever fitted, re-run deck 03 with Cc = 2.2 nF before trusting it.

## 3. Architecture

```
USB-C ──┬── VBUS 5 V ──┬── AP2112K ── +3V3 ── STM32G0B1RBT6 ── I2C1 ── J5: OLED module (SH1106 / SSD1306)
        │              │                          │   │  └── TIM3 encoder, 3 buttons, ON / FAULT / heartbeat LEDs, blower PWM/tach/enable, CC1/CC2 ADC
        │              ├── AO3401 switch ── J2: 5 V 5015 blower
        │              └── B0512S-1W ═══ barrier ═══ +12V_RAW ─┬─ 4.7 Ω / 22 µF ── +12V_ISO (op-amps, LM339, pull-ups)
        └── D+ / D− ── USBLC6 ── USB FS                       │          └─ 78L05 ── +5V_ISO (DAC, ADC, isolator side 2, thresholds)
                                                              │
   SPI1 + /CS_DAC + /CS_ADC + LOAD_OFF ── CA-IS3761HW ═══ barrier ═══ MCP4822 ── A: LOAD_CTRL ── /16 ── V_SET ── 4 × (TLV9154 U11 + IRFP250N + 2 × 0.2 Ω)
                                                              │                  └─ B: CV_SET ── U12C error amp ── Q13 pulls V_SET down
                                                              └── ADS1118 ◄── ISEN (U12A, mean of 4 Rs), VSEN (U12B, 4-wire diff amp), V_NTC, V_SET
   LM339: OTP (85/70 °C) ── Q11 ─┐
          NTC-open, OVP (62 V), LOAD_OFF ── diode-OR ── Q12 ─┴── short V_SET to AGND
          dropout (DRAIN < 0.45 V) ── KILL ── 4.7k + 1N4148 into every channel's inverting input
   DUT+ (M4) ── 15 A / 58 V fuse (soldered) ── DRAIN bus ── 4 drains; sources ── 2 × 0.2 Ω ── PGND ── NT1 (star) ── AGND; DUT− (M4) on PGND
```

Grounds: **DGND** (USB side), **AGND** (isolated analog reference), **PGND** (DUT minus and the source resistors). AGND and PGND
meet only at net tie NT1, placed at the centroid of the four Rs bottom pads. On the 2-layer board both are pours, not planes: the 10 A
return runs on dedicated PGND copper from the Rs bottom pads to NT1 and on to J8; the AGND pour touches it at NT1 and nowhere else.

## 4. Power budget (USB-C, 5 V)

| Consumer | Current at 5 V |
|---|---|
| Isolated DC-DC (12 V × 30 mA / 0.8 efficiency + 5 V rail) | 0.10 A |
| STM32 + isolator side 1 + LEDs | 0.06 A |
| OLED module | 0.02 to 0.03 A |
| 5 V 5015 blower | 0.15 to 0.25 A |
| **Total** | **0.35 to 0.45 A** |

The CC1/CC2 pull-downs (5.1 k) make the board a USB-C sink; the MCU reads the CC voltage to learn the source limit (0.4 V = 500 mA default,
0.9 V = 1.5 A, 1.7 V = 3 A). Any port, including a legacy 500 mA one, runs the whole box.

## 5. Isolation design

Voltage blocks: **A** = USB side (DGND, earth-referenced through the PC), **B** = analog side (AGND/PGND = DUT minus, up to 58 V above
it on DRAIN). B floats with the DUT, so the A-to-B working voltage is whatever the DUT minus terminal sits at relative to earth.

| Pair | Grade | Working voltage (design limit) | IEC 60664-1 (PD2, material group IIIb, internal transient = V + 1200 V) | IPC-2221B B2 × 1.2 | Board rule |
|---|---|---|---|---|---|
| A to B | functional (bench instrument, no user-touchable live part) | 150 V DC | clearance 0.5 mm, creepage 1.6 mm | 0.72 mm | **4.0 mm** on both layers, no copper crosses |
| DRAIN to AGND (inside B) | functional | 60 V (77 V TVS clamp) | 0.5 / 1.24 mm | 0.72 mm | 1.5 mm |

Parts on the barrier: CA-IS3761HW (5 kVrms, 8 mm creepage; ISO7761DW is the drop-in alternative), B0512S-1W (1.5 kVDC DEXU; the Mornsun
B0512S-1WR3 is 3 kVDC and the same footprint). Hipot for the assembled board: 1 kV DC for 1 s A to B. Not for mains-referenced work: the rating
is set by the 4 mm PCB gap, not by the parts. Enclosure, USB shield, encoder shaft and buttons are on side A; binding posts / M4 bolts, heatsink
hardware and NTC lug are on side B (insulated TO-247 mounting, plastic NTC lug).

## 6. Connectors

| Ref | Function | Pinout / part |
|---|---|---|
| J1 | USB-C 2.0 receptacle (HRO TYPE-C-31-M-12, C165948) | power, D+/D−, CC1/CC2 to the MCU ADC |
| J2 | Blower, JST-XH 4 (C144395) | 1 GND, 2 +5 V (switched), 3 tach, 4 PWM 25 kHz open-drain. 2-wire 5 V blower: pins 1 to 2, on/off |
| J3 | SWD, 1×5 header (C124379) | 1 +3V3, 2 SWDIO, 3 SWCLK/BOOT0, 4 NRST, 5 GND |
| J4 | Debug UART 3.3 V, 1×3 header (C124376) | 1 GND, 2 TX, 3 RX |
| J5 | OLED module, 1×4 header (C124378) | 1 GND, 2 +3V3, 3 SCL, 4 SDA. Check the module: some are VCC GND SCL SDA |
| J6 | Heatsink NTC 10 k B3950, JST-XH 2 (C158012) | isolated side |
| J7, J8 | DUT+, DUT− plated 4.3 mm holes with 10 mm pads, M4 bolt, nut, washers, ring lug | isolated side |
| J9 | 4-wire sense pair, JST-XH 2 (C158012) | 100 Ω local fallback when open |
| J10 | Board link, control board: 2×6 box header 2.54 mm, vertical, hand-soldered on the BACK face (C9136) | 1, 2 VBUS; 3 +3V3; 4 SCK; 5 MOSI; 6 MISO; 7 /CS_DAC; 8 /CS_ADC; 9 LOAD_OFF; 10 to 12 DGND |
| J11 | Board link, power board: same header, vertical, on the USB-side island | same pinout, pin 1 to pin 1. The J11-side nets carry the `_LK` suffix so the two boards stay separate nets in the PCB |
| CBL1 | 12-way IDC ribbon, two 2×6 sockets, about 80 mm | BOM line only, no footprint. Check pin 1 to pin 1 with a meter on the first pair |

## 7. Thresholds (all ratios of +5V_ISO, so independent of its absolute value)

NTC: 10 k B3950 on the heatsink next to FET 2, fed from +5V_ISO through 10.0 k 1 %. V_NTC = 2.50 V at 25 °C, 1.52 V at 45 °C, 0.75 V at 70 °C, 0.49 V at 85 °C.

| Comparator (LM339, open collector, 10 k pull-ups to +12V_ISO) | Threshold network | Trip / release | Acts on |
|---|---|---|---|
| U14A over-temperature | In+ 90.9 k / 10.0 k = 0.099 × rail, 402 k hysteresis; In− = V_NTC | 85 °C / 70 °C (±1.5 °C from the 1 % parts) | Q11 shorts V_SET |
| U14B dropout / KILL | In+ 100 k / 10.0 k = 0.045 × rail, 165 k hysteresis; In− = DRAIN via 47 k + 12 V zener | DRAIN < 0.45 V / > 0.54 V | KILL into every channel (anti-wind-up) |
| U14C NTC open | In+ = V_NTC; In− 10.0 k / 27.4 k = 0.73 × rail (3.66 V) | NTC > 27 k (open, or below 3 °C) | OFF_GATE through BAT54C |
| U14D over-voltage | In+ = VSEN_OA via 10 k, 1 M hysteresis; In− 5.90 k / 10.0 k = 0.629 × rail (3.15 V) | 62 V ± 1.2 V / about 60 V | OFF_GATE through 1N4148 |
| LOAD_OFF_ISO (from the MCU through the isolator) | 5 V logic into the same BAT54C | high = OFF; default high when the USB side is dead | OFF_GATE → Q12 |

## 8. Transfer functions, calibration and the 1 % budget

| Quantity | Nominal | Calibrate | Error from 1 % parts before calibration |
|---|---|---|---|
| Set current | I = 2.50 A/V × (V_DAC − 0.0424 V), clamp ≥ 0 | 2 points (0.5 A, 8 A) against a DMM in series | R31/R32 divider ±2 %, Rs ±1 %: gain error, removed |
| CV set-point | V_CVSET = 0.049 × V_DUT + 0.10 V | same scale as VSEN | as VSEN |
| ISEN (ADC AIN0) | 0.300 V/A × I + 0.15 V | zero with the load off; gain at 8 A | R43/R42 ±2 % gain, removed |
| VSEN (ADC AIN1) | 0.0490 × V_DUT + 0.10 V | zero with the DUT shorted (load off); gain at a known 24 V | R45/R46 ±2 % gain, removed; CMRR about 40 dB, harmless (SENSE_N is within mV of AGND) |
| V_NTC (ADC AIN2) | B3950 equation, rail-ratiometric | one point at room temperature | R51 ±1 % = ±0.25 °C |
| V_SET (ADC AIN3, PGA ±256 mV) | 25.6 mV/A; read-back of the node the loops follow | none; it is a diagnostic | |

ADS1118: internal reference, single-ended against AGND, 128 to 860 SPS. The MCP4822 internal reference is ±2 %; the two-point calibration absorbs it.
Channel-to-channel sharing with 1 % Rs: ±1 %, i.e. ±25 mA of the 2.5 A per FET, thermally irrelevant.

## 9. Digital interface over the barrier

SPI mode 0 (CPOL 0, CPHA 0 for the MCP4822; ADS1118 mode 1), ≤ 2 MHz because of the isolator delay on each direction. Channels:
SCK, MOSI, /CS_DAC, /CS_ADC, LOAD_OFF forward; MISO back. CA-IS3761HW (H = high) and ISO7761 (no F suffix) outputs default **high**: with the
MCU in reset, unpowered or the firmware crashed, both chip selects are de-asserted and LOAD_OFF is asserted. 10 k pull-ups on the MCU side give
the same guarantee while the MCU pins are high-impedance.

## 10. Front panel

A 1.3" SH1106 128 × 64 I2C OLED module (0.96" SSD1306 is the same protocol family) on J5 shows V, A, W, the set value, the mode (CC/CV/CR/CP/BATT),
REMOTE and the menus (limits, fan, calibration). Two panel LEDs: ON (green, PA8) while the load sinks, FAULT (red, PC7) for OTP / OVP / NTC-open /
OFF. Encoder on TIM3 with 10 k / 10 nF filters, push = digit select. Buttons: ON/OFF, MODE, MENU. The module hangs on a short 4-wire lead and
sits on the bezel over the left 36 mm of the control board (nothing tall is placed there).

## 11. Layout rules

0. **Two boards, one panel** (`hardware/tools/place_reve.py` builds the placed board): panel 170 × 100 mm, **2 layers, 2 oz outer copper**, one V-score at
   y 40 between the control board (y 0 to 40) and the power board (y 40 to 100 = the 170 × 60 heatsink base). Every part is on F.Cu except J10 (vertical box
   header hand-soldered on the back of the control board so the ribbon leaves rearward) and the four TO-247, which are hand-soldered UNDER the power
   board (tab down on the 3 mm base, leads bent up through the pad row 32 mm from the front edge, 38 mm pitch at x 31 / 69 / 107 / 145, a 7 mm access hole
   above each tab screw); the heatsink wall is the rear edge. Control board: F.Cu is the face the user sees (encoder, buttons, LEDs, OLED window), USB-C
   leaves the left edge. The USB-side island (J11, isolator side 1, DC-DC input) sits in the front-left corner of the power board behind an L-shaped 4 mm
   keep-out (rule areas `ISO_BARRIER_4mm_A/B`, both copper layers).
1. **Barrier**: 4 mm gap under the isolator and the DC-DC, no copper on either layer, no pour. Keep the two sides' decoupling on their own side.
   The SIP-4 DC-DC has its input and output pins 2.54 mm apart, so at PS1 the creepage is set by the part (about 1 mm pad to pad), not by the rule:
   mill a slot between pins 2 and 3 or accept the part's own rating there (1.5 kV).
2. **Kelvin everything around Rs** (unchanged from Rev C): each channel's Rf and ISEN averaging resistor connect at the top pad of that channel's Rs pair on their own trace; op-amp ground at the bottom pads.
3. **Star ground**: NT1 at the centroid of the four Rs bottom pads; take DUT− (J8) from the same point on dedicated PGND copper. 1 mΩ between an Rs and NT1 is 10 mV at 10 A (4 % of full scale). The AGND pour is the analog reference and must carry no load current: it touches PGND at NT1 only.
4. **Gate**: 47 Ω within 10 mm of the gate pin; 100 k and 15 V zener at the FET pins.
5. **High-current path**: DUT+ (J7) → fuse → DRAIN bus → drains; sources → Rs → PGND → J8. ≥ 5 mm of 2 oz copper on both layers in parallel, stitched with vias. TVS and snubber across DRAIN/PGND at the terminals.
6. **R45, R48 (200 k) and R60 (47 k) see 60 V**: 1206. ≥ 1.5 mm from DRAIN copper to anything else on the analog side.
7. **Blower**: C3 (10 µF) at J2, its own VBUS trace back to the USB connector so the motor noise stays off the MCU rail.
8. **ADC and DAC** next to the isolator on the analog side; the 1 k / 10 nF RC on AIN3 at the ADC pin.
9. **OLED window**: nothing taller than 2 mm in x 14 to 50 mm of the control board (J5 at its lower edge).
10. **Thermal**: U11 close to the FETs but not on the heatsink edge; the four TO-247 along the heatsink at 38 mm pitch (`heatsink_and_thermal.md`).
11. **Heatsink potential**: the heatsink is structure and its fins are reachable, so it is tied to the enclosure, i.e. the USB side. The insulator under
    each FET is therefore part of the barrier (silicone pad ≥ 2 kV, shoulder washers), and every power-board mounting hole gets a 4 mm copper keep-out ring.
12. **Mounting**: power board on four M3 standoffs tapped into the 3 mm base (six threads, 0.5 N·m, no second chance), control board on enclosure standoffs.
13. **Copper**: 2 oz outer on a 2-layer board. Top: parts and signal; bottom: DGND pour on the control board, AGND pour on the analog side of the power board,
    PGND copper for the 10 A return, the barrier gap on both.

## 12. Bring-up (summary; write the full plan before first power)

1. Unpowered: DUT+ to DUT− > 100 kΩ; each gate to source about 100 kΩ; DGND to AGND open (> 10 MΩ); DGND to PGND open.
2. USB from a current-limited supply or a USB power meter, no DUT: +3V3, VBUS, +12V_ISO (12 to 14 V), +5V_ISO (5.0 V ± 4 %). Current < 150 mA. All gates < 0.1 V. KILL about 2 V (dropout active with no DUT). LOAD_OFF_ISO high.
3. Enumerate: USB DFU with BOOT held at reset; then CDC with firmware. OLED shows a test pattern, encoder and buttons register.
4. Firmware releases LOAD_OFF; DAC A = 0.1 V with a 5 V / 1 A-limited bench supply as DUT: 0.25 A − 106 mA ≈ 0.14 A, equal on all four sources (S1 to S4 about 3.6 mV). V_SET read-back on AIN3 matches.
5. Sweep to 1 A then 5 A at 5 V (25 W). ISEN/VSEN against a DMM; record calibration points.
6. Heat-gun the NTC: blower from the firmware at 45 °C, OTP trip at about 85 °C (current 0, AIN3 shows V_SET pulled down), release at 70 °C.
7. OVP: 62 V from a supply through a 1 k resistor onto VSEN only (not the DRAIN bus), or raise CV_SET and the DUT voltage; current must go to 0.
8. Step test: 1 A ↔ 9 A at 12 V, 100 Hz; scope a source node against rev_e deck 02 (20 to 30 µs, no ringing); add 1 m of loose lead.
9. Hipot 1 kV DC between DGND and AGND for 1 s, leakage < 10 µA.
10. Heatsink characterisation with the 5 V blower and duct, then a 150 W soak for 30 min while logging the temperature.

## 13. Items to verify before ordering

- [ ] **PS1 pin numbering.** The SIP-4 footprint and symbol assume 1 VIN+, 2 VIN−, 3 VOUT−, 4 VOUT+. Check the datasheet of the exact module (DEXU B0512S-1W C5244116 or Mornsun B0512S-1WR3 C5358214) and fix the footprint in `hardware/libraries/footprints/dcload.pretty` if it differs.
- [ ] OLED module pin order (GND VCC SCL SDA vs VCC GND SCL SDA): J5 is wired GND, +3V3, SCL, SDA.
- [ ] CA-IS3761HW: confirm from its datasheet that the H variant's outputs default high with side 1 unpowered (the ISO7761DW does; both are on the same footprint).
- [ ] STM32G0B1: set option bit nBOOT_SEL = 0 once so the BOOT button works (factory default ignores the pin).
- [ ] Blower: 5 V 5015 (or 6015) with a 2-pin lead; measure its current for the USB budget.
- [ ] Heatsink Rsa with the blower and duct, then the firmware power limits.
- [ ] Hysteresis values on the bench (bring-up step 6): they assume the LM339 output high level of 12 V through 10 k and about 2 V on the clamped KILL line.
- [ ] Ribbon: J10 on the back of the control board, J11 on the power board; pin 1 to pin 1 with a meter on the first pair.
- [ ] Fuse: Littelfuse 0997015.WXN blades fit the `Fuse_Blade_Mini_directSolder` slots (MINI format).
- [ ] PS1 pad-to-pad creepage between pins 2 and 3 (about 1 mm with the 2.54 mm pitch) against the 1.6 mm requirement: slot or accept the part's own rating.

## 14. Cost (single unit, live JLCPCB / LCSC prices, 2026-11-03: `../hardware/outputs/rev_e_v1/BOM_RevE_JLC.csv`)

| Group | Parts | USD |
|---|---|---|
| MCU + USB | STM32G0B1RBT6, HRO USB-C, USBLC6, AP2112K | 3.79 |
| Isolation | CA-IS3761HW, B0512S-1W, L78L05 | 3.01 |
| Converters | MCP4822, ADS1118 | 4.11 |
| Analog | 2 × TLV9154IDR, LM339, 2N7002 × 5, zeners, diodes, BAT54 | 3.15 |
| Power stage | 4 × IRFP250NPBF (Infineon), 8 × 0.2 Ω 2 W, fuse, TVS, snubber | 5.35 |
| Front panel | PEC11R encoder, 5 tact switches, 4 LEDs, headers | 2.64 |
| Passives and connectors | about 110 resistors / capacitors, JST-XH ×3, box headers ×2 | 1.41 |
| **Catalogue parts total** | 96 BOM lines, 211 parts | **23.46** |
| Off-board | 1.3" SH1106 OLED module 2.50, 5 V 5015 blower 2.50, 10 k B3950 lug NTC 0.30, 12-way ribbon with two IDC sockets 1.00, M4 bolts / nuts / washers 0.50 | 6.80 |
| PCB | 2-layer 2 oz 170 × 100 mm panel, JLCPCB, 5 pieces | 20 to 30 (4 to 6 each) |
| **One instrument** | parts + off-board + one PCB of five | **about 34 to 36** |

Rev D at distributor prices was $70 to $85 of parts plus a $40 to $60 four-layer PCB order. The Siglent SDL1020X-E is about $574; the DL24-class
AliExpress loads are $15 to $30 and have none of the isolation, the per-FET loops or the 16-bit readback (`comparison_cheap_loads.md`).
Prices move: re-run `jlc_bom_price.py` before ordering. JLCPCB assembly would add its setup and extended-part fees; the single-side SMD build is
also a reasonable hand job (one LQFP64, one TSSOP-10, the rest SOIC / SOT / 0603 and larger).
