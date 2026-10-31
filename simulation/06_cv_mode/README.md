# 06_cv_mode

**Question:** Can the Rev C stage hold a current-source DUT at a set voltage? This is what the added CV block (schematic sheet `cv_mode`) is for.
**Analysis:** `.tran` 150 ms, source 0.1 / 1 / 8 A with 30 V compliance, with and without 47 uF across the DUT.

| File | What it is |
|---|---|
| `06_cv_mode.asc` | The schematic: decks 01-04 plus U7 / Mcv, with all directives on the sheet |
| `06_cv_mode.net` | LTspice netlist; `04_KiCad/tools/check_netlist.py` compares the KiCad schematic against it |
| `plot_06_cv_mode.py` | Rebuilds `results/fig06_cv_mode.png` from the `.raw` (about 500 MB, so it is not kept) |
| `results/06_cv_mode.log` | `.meas` results from the reference run (LTspice 26.0.2) |

**Reference results**
- 1 A and 8 A, with or without 47 uF: settled at the CV setting within 1 mV peak-to-peak by 50 ms; 0.1 A without C also settled (3 mV pp).
- 0.1 A with 47 uF: stable but underdamped, a ~50 Hz ring that was still 1.7 V pp at 149 ms. Allow about a second.
- 30 mA (reduced one-channel test): hunts, so 0.1 A is the stated CV minimum.
- A +10 % source step lifts V(DUT+) by about 6 V for tens of ms, then it recovers. CV here is for static tests, not fast transients.
- The -0.27 % DC error at 12 V and 10 V is the nominal 0.049 scaling used for CV_SET; calibration removes it.
- CC regression (reduced one-channel, CV_SET = 0): hot-plug and recovery peaks 8.119 A with or without the CV block.

Model limits: 2N7002 is a generic VDMOS estimate, DUT is ideal. Margin is not measured here; verify on the bench.
