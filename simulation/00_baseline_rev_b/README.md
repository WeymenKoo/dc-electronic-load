# 00_baseline_rev_b

**Question:** Why the Rev B power board (as built, Nov 2024) cannot reach full scale, and what its VSEN amplifier does.
**Analysis:** `.dc` LOAD_CTRL 0-4.096 V, IRF530 VGS(th) stepped 2 / 3 / 4 V

| File | What it is |
|---|---|
| `00_baseline_rev_b.asc` | The schematic: wired, with the test description and all directives on the sheet |
| `00_baseline_rev_b.plt` | LTspice plot layout. Opens automatically with the waveform window after you run the sim. Top: Id(Q1) (all three Vth steps). Bottom: V(gate) and V(VSEN). |
| `plot_00_baseline_rev_b.py` | Reproduces `results/fig*.png` from `00_baseline_rev_b.raw` (matplotlib) |
| `results/00_baseline_rev_b.log` | The `.meas` results from the reference run (LTspice 26.0.2) |
| `results/fig*.png` | The figure used in the package README |
| `results/schematic_preview.png` | Rough layout preview from the generator, not an LTspice render. Take screenshots in LTspice. |

**Reproduce:** open `00_baseline_rev_b.asc` in LTspice, press Run, then read **View -> SPICE Error Log** for the numbers.
Then `python3 plot_00_baseline_rev_b.py` (needs numpy and matplotlib) rewrites the figure. Models come from `../lib/`.

**Reference results**
- Current per channel at full scale: 5.68 / 2.05 / 0.04 A (target 6.14 A); gate pinned at 4.096 V
- VSEN output at DUT = 12 V: 4.10 V (latched); correct value is 1.20 V
