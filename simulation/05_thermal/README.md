# 05_thermal

**Question:** Junction and heatsink temperature at 150 W for 2/3/4 MOSFETs and four heatsink Rsa values (1 V = 1 degC).
**Analysis:** `.tran` 3600 s thermal RC network, N stepped 2/3/4 x Rsa 0.25/0.35/0.5/0.9

| File | What it is |
|---|---|
| `05_thermal.asc` | The schematic: wired, with the test description and all directives on the sheet |
| `05_thermal.plt` | LTspice plot layout. Opens automatically with the waveform window after you run the sim. One pane: V(J1) (junction of FET 1) and V(SINK) (heatsink), all 12 steps. |
| `plot_05_thermal.py` | Reproduces `results/fig*.png` from `05_thermal.raw` (matplotlib) |
| `results/05_thermal.log` | The `.meas` results from the reference run (LTspice 26.0.2) |
| `results/fig*.png` | The figure used in the package README |
| `results/schematic_preview.png` | Rough layout preview from the generator, not an LTspice render. Take screenshots in LTspice. |

**Reproduce:** open `05_thermal.asc` in LTspice, press Run, then read **View -> SPICE Error Log** for the numbers.
Then `python3 plot_05_thermal.py` (needs numpy and matplotlib) rewrites the figure. Models come from `../lib/`.

**Reference results**
- 4 FETs, Rsa 0.35 K/W: Tj 127.5 degC, heatsink 82.5 degC
- 2 FETs: 172.5 degC; no fan (0.9 K/W): 210 degC
