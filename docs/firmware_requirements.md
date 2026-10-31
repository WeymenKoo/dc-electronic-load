# Firmware requirements: Rev D (STM32G0B1CBT6, LQFP48)

The Rev B bring-up firmware (`../archive/rev_b_2024-11_control_board_altium/DC Load Control Board Firmware/`) is an STM32F103 CubeIDE
project with a DAC sweep and one ADC channel. Nothing of it carries over except the intent. Rev D firmware starts from a new
STM32CubeIDE / CubeMX project for the STM32G0B1CBT6 (crystal-less: HSI48 + CRS from USB SOF).

## Must-haves (safety)

1. **Power-on state.** LOAD_OFF (PB1) high and both chip selects high before anything else; the isolator defaults do the same while the
   MCU is in reset. The MCP4822 powers up at 0 V, so there is no EEPROM to clear. Write DAC A = 0 and DAC B = 0 before releasing LOAD_OFF.
2. **Power limit (safety-critical: there is no hardware power limit).** `I_set ≤ min(10.0 A, P_max / V_measured)` on every control tick (≥ 100 Hz),
   with `P_max` = 150 W when the fan is confirmed running (tach) and the USB source gives ≥ 1.5 A, otherwise 55 W, or the measured heatsink values.
3. **Voltage limit.** V_DUT > 58 V: I = 0, FAULT, latch. The hardware OVP at 62 V is the backstop.
4. **Von / Voff arming.** Apply a set-point only above a user Von (default 0.8 V). Ramp the DAC from 0 at a slew limit (default 1 A/ms).
5. **Trip detection and latching.** Read V_SET on ADS1118 AIN3 every tick. If the commanded V_SET (DAC A / 16) and the measured V_SET differ by more than
   10 % for > 5 ms while the load is on, something pulled it down: OTP, NTC-open, OVP, LOAD_OFF or CV regulation. Decide from V_NTC and VSEN, show FAULT,
   set DAC A = 0 and stay off until the user re-arms. Dropout (KILL) is not a fault: show it as "no DUT" when VSEN < 0.5 V.
6. **Fan.** Run the fan from V_NTC: off below 40 °C, 30 % at 45 °C, 100 % at 65 °C, hysteresis 5 °C. If the tach shows no rotation with FAN_EN on, use the 55 W limit and warn.
   FAN_PWM is open-drain (Q3), so the duty cycle written to TIM17 is inverted.
7. **Watchdog.** IWDG at 100 ms. A reset returns LOAD_OFF high through the pull-up and the isolator default.

## Hardware access

| Function | Pins | Notes |
|---|---|---|
| SPI1 to the isolator | PA5 SCK, PA6 MISO, PA7 MOSI, PA4 /CS_DAC, PB0 /CS_ADC, PB1 LOAD_OFF | ≤ 2 MHz. MCP4822: 16-bit frames, mode 0,0. ADS1118: 16 or 32-bit frames, mode 1 (CPOL 0, CPHA 1). Never assert both /CS |
| MCP4822 | A = LOAD_CTRL, B = CV_SET | gain bit = 1 (2×, 0 to 4.095 V), shutdown bit = 1 (active). Write A then B, LDAC is tied low: each output updates on /CS rising |
| ADS1118 | AIN0 ISEN, AIN1 VSEN, AIN2 V_NTC, AIN3 V_SET | single-ended, PGA ±4.096 V (AIN0 to AIN2) and ±0.256 V (AIN3), 860 SPS continuous, read the previous conversion while writing the next config. Also read the internal temperature sensor once a second |
| SPI2 to the displays | PB13 SCK, PB15 MOSI, PB12 LOAD | 74AHCT125 level shift; two MAX7219 in a chain (32-bit frames, second device's data first); decode mode off, scan limit 7, intensity from the menu |
| Encoder | PB4 / PB5 TIM3 encoder mode, PB3 push | 20 PPR, 4× decoding, RC filtered |
| Buttons | PD0 ON/OFF, PD1 MODE, PD2 MENU | internal pull-ups, 20 ms debounce in software |
| Fan | PD3 FAN_EN, PB9 TIM17_CH1 PWM 25 kHz (inverted), PB8 TIM16 input capture tach | FAN_EN also enables the boost |
| USB-C source detection | PA0 CC1, PA1 CC2 (ADC) | the connected CC line is the one above 0.2 V; 0.4 V default, 0.9 V 1.5 A, 1.7 V 3 A |
| USB | PA11 DM, PA12 DP | CDC-ACM for SCPI; USBTMC class later (TinyUSB has one) for PyVISA `USB0::...::INSTR` |
| Debug | PA9 / PA10 USART1 (J4), PC6 status LED, PB6 / PB7 I2C1 OLED (J5) | |
| DFU | ROM bootloader; hold BOOT (PA14) and tap RESET; or jump to system memory from a `*DFU` SCPI command | clear nBOOT_SEL once |

## Scaling and calibration

| Quantity | Nominal | Calibrate |
|---|---|---|
| Set current | I = 2.50 A/V × (V_DAC − 0.0288 V), V_DAC = code × 1 mV | 2 points, stored in flash |
| ISEN | I = (V_AIN0 − 0.15 V) / 0.300 V/A | zero with the load off; gain at 8 A against a DMM |
| VSEN | V = (V_AIN1 − 0.10 V) / 0.0490 | zero with the DUT shorted; gain at a known 24 V |
| CV set-point | code_B = (0.049 × V_target + 0.10 V) / 1 mV | same constants as VSEN |
| Heatsink temperature | B3950 from V_AIN2 / 5.00 V | one point at room temperature |
| V_SET read-back | 25.6 mV per ampere total | diagnostic only |

Store the calibration constants and the user settings (Von, slew, fan limits, P_max with and without fan) in the last flash page.

## Modes

- **CC**: DAC A = f(I_set); DAC B = 0.
- **CV**: DAC B = f(V_target), DAC A = current ceiling, ramped from 0 over about 20 ms. Trim DAC B slowly from VSEN to remove DC error. Valid from 0.1 A (deck 06).
- **CR**: I_set = V / R_set at ≥ 1 kHz on the CC loop.
- **CP**: I_set = P_set / V, with the power limit.
- **Transient**: alternate two I_set values; the SPI DAC update takes about 20 µs, so up to about 10 kHz toggling is possible (hardware settles in 30 µs).
- **Battery**: CC or CP to a cut-off voltage on the 4-wire sense; integrate mAh and Wh; **latch off at cut-off** (no re-enable on rebound); pulse-step internal-resistance measurement (ΔV/ΔI).

## Front panel

VOLTS and AMPS show live readings (4 digits, auto-ranging decimal point). SET shows the value being edited; the encoder changes the selected digit,
push moves the cursor. ON/OFF toggles the sink with a 2 s hold for "lock". MODE cycles CC, CV, CR, CP, BATT. MENU: Von, slew, power limit, fan,
calibration, display intensity, USB source info. LEDs: mode (CC/CV/CR/CP/BATT), ON while sinking, FAULT latched until re-armed, REMOTE while a host
has sent a command in the last 10 s (front panel read-only except ON/OFF, which always works).

## SCPI over USB CDC (115200 8N1, newline terminated)

`*IDN?`, `*RST`, `*DFU`, `MEAS:VOLT?`, `MEAS:CURR?`, `MEAS:POW?`, `MEAS:TEMP?`, `SOUR:MODE CC|CV|CR|CP|BATT`, `SOUR:CURR x`, `SOUR:VOLT x`, `SOUR:RES x`,
`SOUR:POW x`, `INP ON|OFF`, `SOUR:CURR:SLEW x`, `SOUR:VOLT:ON x`, `BATT:CUT x`, `BATT:CAP?`, `SYST:FAN?`, `SYST:USB?`, `STAT:FAULT?`, `CAL:...`.
PyVISA: `rm.open_resource('ASRL/dev/tty.usbmodem...::INSTR')` until the USBTMC class exists.
