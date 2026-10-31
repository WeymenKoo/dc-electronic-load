# 04_faults

**Question:** Hot-plug, DUT collapse/recovery (integrator wind-up) and the over-temperature trip, at an 8 A setting.
**Analysis:** `.tran` 3.5 ms, fet 1-4

| File | What it is |
|---|---|
| `04_faults.asc` | The schematic: wired, with the test description and all directives on the sheet |
| `04_faults.plt` | LTspice plot layout. Opens automatically with the waveform window after you run the sim. Top: V(DUT+), V(DRAIN). Middle: total current. Bottom: KILL, OTP and gate CH1. |
| `plot_04_faults.py` | Reproduces `results/fig*.png` from `04_faults.raw` (matplotlib) |
| `results/04_faults.log` | The `.meas` results from the reference run (LTspice 26.0.2) |
| `results/fig*.png` | The figure used in the package README |
| `results/schematic_preview.png` | Rough layout preview from the generator, not an LTspice render. Take screenshots in LTspice. |

**Reproduce:** open `04_faults.asc` in LTspice, press Run, then read **View -> SPICE Error Log** for the numbers.
Then `python3 plot_04_faults.py` (needs numpy and matplotlib) rewrites the figure. Models come from `../lib/`.

**Reference results**
- Hot-plug and recovery peaks = 8.12 A = setpoint (no overshoot)
- Current during dropout 0.4 mA
- OTP: current < 0.8 A within 2-35 us
