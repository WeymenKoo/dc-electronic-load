# Hardware: Rev D KiCad project

```
hardware/
├── rev_d/                 KiCad 10 project: DC_Load_RevD.kicad_pro, root sheet + sheets/ (13 pages)
├── libraries/             project symbols (dcload.kicad_sym) and footprints (dcload.pretty), registered as ${KIPRJMOD}/../libraries
├── tools/                 build_revd.py generates every sheet; check_netlist_revd.py verifies the result; kgen.py / sexp.py are the writer
└── outputs/rev_d_v1/      DC_Load_RevD_schematic.pdf, ERC_report.txt (0 / 0), DC_Load_RevD.xml netlist, BOM_RevD.csv
```

## Status
Schematic complete, ERC 0 errors / 0 warnings, netlist verified against LTspice deck 06 (43 simulated nodes) plus 131 same-net checks of the
digital side. **PCB not started.** Open items before layout are listed in `../docs/rev_d_specification.md`, section 13.

## Regenerating
```
cd hardware/tools
python3 build_revd.py                      # rewrites ../rev_d/*.kicad_sch and the dcload symbol library (hand edits in KiCad are lost); exits 1 on any lint violation
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
cd ../rev_d
$KC sch erc --format report --severity-all -o ../outputs/rev_d_v1/ERC_report.txt DC_Load_RevD.kicad_sch
$KC sch export netlist --format kicadxml -o ../outputs/rev_d_v1/DC_Load_RevD.xml DC_Load_RevD.kicad_sch
python3 ../tools/check_netlist_revd.py ../outputs/rev_d_v1/DC_Load_RevD.xml ../../simulation/06_cv_mode/06_cv_mode.net
$KC sch export pdf -o ../outputs/rev_d_v1/DC_Load_RevD_schematic.pdf DC_Load_RevD.kicad_sch
```
Once you start editing in KiCad, stop running the generator (or port your edits into it).

## Drawing rules (enforced by `kgen.Sch.lint`; the build fails on any violation)
- A3 landscape for every sheet. JetBrains Mono everywhere: 4.5 mm sheet title, 2.5 mm block titles, 2.0 mm notes (dark grey), 1.6 mm references and values, 1.4 mm labels. 1.27 mm grid.
- Every circuit sits in a titled block frame fitted to its content with a 6 mm margin; the whole drawing is centred in the drawable area (18 mm from the paper edge, title-block corner kept clear).
- No text overlaps any text, symbol or wire; no symbol overlaps another or a foreign wire; block frames never overlap.
- At most 3 wires per junction (staggered joints instead of 4-way crosses). Wire crossings are drawn with hop-overs (`hop_over_display` in the project file) and kept rare.
- The power sheet is a tree: VBUS trunk, one branch per regulator, rails aligned on the right.
- Net colours (legend on page 1): brown 0.6 mm = DUT current path; magenta = set-point; blue = measurement; orange = protection; purple = isolated SPI; teal = USB data; red = supply rails; red dashed = the isolation barrier.
- Page 1 is the block diagram: USB side on the left, isolated analog side on the right, the barrier between them.

## Sheets
| Page | Sheet | Content |
|---|---|---|
| 1 | Root | block diagram, legend, reading order |
| 2 | USB & Power | USB-C, CC sense, ESD; power tree: AP2112K 3.3 V, MT3608 12 V + AO3401 fan switch, B0512S isolated 12 V and MCP1703 5 V; star tie, barrier rating |
| 3 | MCU | STM32G0B1CBT6 (LQFP48), decoupling, reset/BOOT, SWD, UART, I2C OLED header, pin plan |
| 4 | Front Panel UI | 2 × MAX7219 behind a 74AHCT125, 3 × CC56-12, 8 LEDs, PEC11L encoder, 3 buttons |
| 5 | Isolated Interface | ISO7761, MCP4822 (LOAD_CTRL, CV_SET), ADS1118 (ISEN, VSEN, V_NTC, V_SET) |
| 6 | Setpoint & CV | 15 k / 1 k divider, Q11/Q12 pull-downs, LT1013 CV error amplifier |
| 7 | Sense | ISEN ×12 amplifier, 4-wire VSEN difference amplifier, ADC clamps |
| 8 | Protection | NTC, LM339: OTP, dropout/KILL, NTC-open, OVP; OFF diode-OR; op-amp supplies |
| 9 | Power Path | binding posts, 58 V fuse, TVS, snubber, sense pair with local fallback |
| 10 to 13 | Channel 1 to 4 | one LT1014 section, 3.3 k / 1 nF / 47 Ω, IRFP250N, 2 × 0.2 Ω Kelvin sense (one file, four instances) |
