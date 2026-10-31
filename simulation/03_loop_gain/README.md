# 03_loop_gain

**Question:** Stability of one channel (Middlebrook voltage injection) across MOSFET x current x lead inductance.
**Analysis:** `.ac` 10 Hz-10 MHz, fet 1-4 x Ich 25 mA/250 mA/2.5 A x Llead 1u/10u (24 runs)

| File | What it is |
|---|---|
| `03_loop_gain.asc` | The schematic: wired, with the test description and all directives on the sheet |
| `03_loop_gain.plt` | LTspice plot layout. Opens automatically with the waveform window after you run the sim. One pane: loop gain T = -V(src)/V(inj), magnitude (dB) and phase. Read the margins where |T| = 0 dB. |
| `plot_03_loop_gain.py` | Reproduces `results/fig*.png` from `03_loop_gain.raw` (matplotlib) |
| `results/03_loop_gain.log` | The `.meas` results from the reference run (LTspice 26.0.2) |
| `results/fig*.png` | The figure used in the package README |
| `results/schematic_preview.png` | Rough layout preview from the generator, not an LTspice render. Take screenshots in LTspice. |

**Reproduce:** open `03_loop_gain.asc` in LTspice, press Run, then read **View -> SPICE Error Log** for the numbers.
Then `python3 plot_03_loop_gain.py` (needs numpy and matplotlib) rewrites the figure. Models come from `../lib/`.

**Reference results**
- Phase margin >= 80.3 deg, gain margin >= 13.2 dB (worst: IXTH proxy, 2.5 A, 10 uH)
- Crossover 0.45-35 kHz
