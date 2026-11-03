# Hardware: Rev E KiCad project

```
hardware/
├── rev_e/                 KiCad 10 project: DC_Load_RevE.kicad_pro, root sheet + sheets/ (14 pages), DC_Load_RevE.kicad_pcb (placed, not routed)
├── libraries/             project symbols (dcload.kicad_sym) and footprints (dcload.pretty), registered as ${KIPRJMOD}/../libraries
├── tools/                 build_reve.py generates every sheet; check_netlist_reve.py verifies the result; place_reve.py builds the placed PCB;
│                          jlc_price.py / jlc_bom_price.py price parts at JLCPCB (LCSC); kgen.py / sexp.py are the writer
└── outputs/rev_e_v1/      DC_Load_RevE_schematic.pdf, ERC_report.txt (0 / 0), DC_Load_RevE.xml netlist, BOM_RevE.csv (with LCSC codes),
                           BOM_RevE_JLC.csv (priced), DC_Load_RevE_placement.pdf, placement_top.png
```

## Status
Rev E is the cost-reduced build of the Rev D architecture (what changed and why: `../docs/rev_e_specification.md`, section 1).
Schematic complete, ERC 0 errors / 0 warnings, lint 0, netlist verified against the Rev E LTspice deck 06 (`../simulation/rev_e`).
**PCB: every footprint placed on a 2-layer 170 × 100 mm panel, no tracks or zones yet.** `place_reve.py` builds the panel (control board 170 × 40
on top, V-score at y 40, power board 170 × 60 = the heatsink base), the L-shaped 4 mm isolation keep-out on both copper layers, the heatsink and
FET drawing, mounting and screw-access holes, places all 211 footprints (J10 on the back of the control board, the TO-247 hand-soldered under the
power board, everything else on F.Cu) and puts every reference label in a free spot. DRC on the placed board: no violations (the 4
`lib_footprint_issues` are KiCad library-revision notes). Routing is the next step, by hand in KiCad, rules in the spec section 11.

## Regenerating
```
cd hardware/tools
python3 build_reve.py                      # rewrites ../rev_e/*.kicad_sch and the dcload symbol library (hand edits in KiCad are lost); exits 1 on any lint violation
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
cd ../rev_e
$KC sch erc --format report --severity-all -o ../outputs/rev_e_v1/ERC_report.txt DC_Load_RevE.kicad_sch
$KC sch export netlist --format kicadxml -o ../outputs/rev_e_v1/DC_Load_RevE.xml DC_Load_RevE.kicad_sch
python3 ../tools/check_netlist_reve.py ../outputs/rev_e_v1/DC_Load_RevE.xml ../../simulation/rev_e/06_cv_mode/06_cv_mode.net
$KC sch export pdf -o ../outputs/rev_e_v1/DC_Load_RevE_schematic.pdf DC_Load_RevE.kicad_sch
$KC sch export bom --fields 'Reference,Value,Footprint,MPN,LCSC,Tolerance,${QUANTITY}' --labels 'Refs,Value,Footprint,MPN,LCSC,Tolerance,Qty' \
    --group-by 'Value,Footprint,MPN,LCSC,Tolerance' --ref-range-delimiter '' --exclude-dnp -o ../outputs/rev_e_v1/BOM_RevE.csv DC_Load_RevE.kicad_sch
python3 ../tools/jlc_bom_price.py ../outputs/rev_e_v1/BOM_RevE.csv 1       # -> BOM_RevE_JLC.csv, live JLCPCB prices (argument = number of boards)
# placed PCB from the netlist (KiCad's own python has pcbnew):
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 ../tools/place_reve.py
$KC pcb drc --format json --severity-all -o /tmp/drc.json DC_Load_RevE.kicad_pcb
```
Once you start editing in KiCad, stop running the generator and the placer (or port your edits into them): both overwrite their output files.

## Sourcing
Every bought part carries an `LCSC` field in the schematic, so the BOM export and JLCPCB's assembly upload line up. `jlc_price.py KEYWORD` looks a
part up (code, stock, basic/extended, price ladder); `jlc_bom_price.py` prices the whole BOM, searching JLC basic parts for the generic 0603 / 0805 /
1206 resistors and capacitors that have no code. Off-board items (OLED module, 5 V blower, NTC lug, ribbon cable, M4 hardware) are listed in the
spec, section 14.

## Drawing rules (enforced by `kgen.Sch.lint`; the build fails on any violation)
- A3 landscape for every sheet. JetBrains Mono everywhere: 4.5 mm sheet title, 2.5 mm block titles, 2.0 mm notes (dark grey), 1.6 mm references and values, 1.4 mm labels. 1.27 mm grid.
- Every circuit sits in a titled block frame fitted to its content with a 6 mm margin; the whole drawing is centred in the drawable area (18 mm from the paper edge, title-block corner kept clear).
- No text overlaps any text, symbol or wire; no symbol overlaps another or a foreign wire; block frames never overlap.
- At most 3 wires per junction (staggered joints instead of 4-way crosses). Wire crossings are drawn with hop-overs (`hop_over_display` in the project file) and kept rare.
- The power sheet is drawn as a tree (trunk, branches, one rail symbol per branch end). The isolation barrier is a red dashed line on every sheet it crosses.
- The root sheet is a wired block diagram: sheet pins on all four sides of a block (`kgen.add_sheet` sides L / R / T / B), straight wires between pins at the same row, one hop-over (DRAIN over KILL). Nets that reach three or more blocks use a second, pass-through pin name on the sub-sheet (`VSET_MON`, `VSEN_OA_OVP`, `KILL_T` / `VSET_T` / `AVG_T` / `DRAIN_T`); KiCad's `multiple_net_names` warning is set to *ignore* in the project file for that reason, and `check_netlist_reve.py` folds those names back onto their nets.
- Nets are colour-coded (key on the root sheet): DUT current path (0.6 mm, brown), set-point (magenta), measurement (blue), protection (orange), isolated SPI (violet), USB data (teal), supply rails (red).

## Sheets
| Page | Sheet | Content |
|---|---|---|
| 1 | Root | **Block diagram**: every sub-sheet is a block and every connection a wire between sheet pins (no net labels); signal flow left to right, the four channels daisy-chained through `*_T` pass-through pins, barrier, colour key |
| 2 | USB & Power | USB-C, CC sense, ESD; power tree: AP2112K 3.3 V, isolated DC-DC + 78L05; blower switch (5 V); star point |
| 3 | MCU | STM32G0B1RBT6, decoupling, reset / BOOT / SWD, UART, heartbeat LED |
| 4 | Front Panel UI | OLED header + I2C pull-ups, encoder, 3 buttons, ON / FAULT LEDs |
| 5 | Board Link | J10 (control board, back face) to J11 (power board) over the 12-way IDC ribbon; `_LK` nets; CBL1 BOM line |
| 6 | Isolated Interface | CA-IS3761HW isolator, MCP4822 DAC, ADS1118 ADC |
| 7 | Setpoint & CV | V_SET divider, OTP / OFF pull-downs, hardware CV error amp (U12C) |
| 8 | Sense | ISEN averaging amp (U12A), VSEN 4-wire difference amp (U12B), ADC clamps |
| 9 | Protection | NTC, LM339 OTP / dropout-KILL / NTC-open / OVP, OFF diode-OR, analog supplies |
| 10 | Power Path | M4 terminals, soldered 58 V mini-blade fuse, TVS, snubber, 4-wire sense with fallback |
| 11-14 | Channel 1-4 | One TLV9154 section, 3.3k / 1n / 47R, IRFP250N, 2 × 0.2R Kelvin sense, KILL, 15M offset |
