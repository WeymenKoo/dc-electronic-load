# 04_faults (Rev E, TLV9154)

**Question:** Hot-plug, DUT collapse / recovery (integrator wind-up) and the over-temperature trip, at an 8 A set point, with the TLV9154.
**Analysis:** `.tran` 3.5 ms, fet stepped 1-4 (4 runs). Same stimulus as `../../04_faults`.

| File | What it is |
|---|---|
| `04_faults.asc` | The schematic: wired, with the timeline and all directives on the sheet |
| `04_faults.plt` | LTspice plot layout: DUT and DRAIN voltages, total current, KILL / OTP / gate |
| `plot_04_faults.py` | Reproduces `results/fig*.png` from `04_faults.raw` (matplotlib) |
| `results/04_faults.log` | The `.meas` results from the reference run (LTspice 26.0.2, local copy) |

**Reference results** (Rev C value in brackets)
- Hot-plug and recovery peaks, IRFP250N / IRFP240 / IRF530: 8.09 A = the set point, no overshoot (8.12 A = set point)
- **IXTH88N30P big-die proxy: 13.2 A on hot-plug and on recovery** (8.12 A): the same loss of margin as decks 02 and 03; not a BOM part
- Current during dropout (DUT at 0.4 V): 0.4 mA (0.4 mA)
- OTP trip, time to < 0.8 A: 1–33 µs (2–35 µs); residual 0.7–2.6 mA
