# 03_loop_gain (Rev E, TLV9154)

**Question:** Stability of one channel (Middlebrook voltage injection) across MOSFET × current × lead inductance with the TLV9154.
**Analysis:** `.ac` 10 Hz-10 MHz, fet 1-4 × Ich 50 mA / 250 mA / 2.5 A × Llead 1u / 10u (24 runs). The lowest current corner is 50 mA per channel instead of Rev C's 25 mA, because 25 mA (V_SET = 2.5 mV) now sits inside the 2.6 mV deliberate offset: the op-amp output is at 0 V and there is no loop to measure.

| File | What it is |
|---|---|
| `03_loop_gain.asc` | The schematic: wired, with the test description and all directives on the sheet |
| `03_loop_gain.plt` | LTspice plot layout: loop gain T = −V(src)/V(inj), magnitude and phase |
| `plot_03_loop_gain.py` | Reproduces `results/fig*.png` from `03_loop_gain.raw` (matplotlib) |
| `results/03_loop_gain.log` | The `.meas` results from the reference run (LTspice 26.0.2, local copy) |

**Reference results** (Rev C value in brackets)
- IRFP250N / IRFP240 / IRF530: phase margin ≥ 87.5°, gain margin ≥ 21.8 dB over all corners (≥ 86°, ≥ 22 dB)
- IXTH88N30P big-die proxy: PM 80.2° at 2.5 A / 10 uH (80.3°), **GM 9.1 dB at 2.5 A / 1 uH** (13.2 dB): below the 10 dB criterion for this proxy only
- Crossover 1.5-2.1 kHz at 50 mA, 6-13 kHz at 250 mA, 16-36 kHz at 2.5 A (0.45-0.55 kHz at 25 mA, 15-35 kHz at 2.5 A)
- The compensation (3.3k / 1n / 47R) is unchanged. Cc = 2.2n would restore the proxy's margin at the cost of a slower step; not adopted because the BOM uses the IRFP250N
