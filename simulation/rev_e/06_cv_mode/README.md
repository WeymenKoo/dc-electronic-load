# 06_cv_mode (Rev E, TLV9154)

**Question:** Can the Rev E stage hold a current-source DUT at a set voltage with the TLV9154 as the CV error amplifier (U12C) and in the sense amplifiers?
**Analysis:** `.tran` 150 ms, source 0.1 / 1 / 8 A with 30 V compliance, with and without 47 uF across the DUT (6 runs). Same stimulus as `../../06_cv_mode`.

| File | What it is |
|---|---|
| `06_cv_mode.asc` | The schematic: decks 01-04 plus U7 / Mcv, with all directives on the sheet |
| `06_cv_mode.net` | LTspice netlist; `hardware/tools/check_netlist_reve.py` compares the Rev E KiCad schematic against it |
| `plot_06_cv_mode.py` | Rebuilds `results/fig06_cv_mode.png` from the `.raw` (about 500 MB, so it is not kept) |
| `results/06_cv_mode.log` | `.meas` results from the reference run (LTspice 26.0.2, local copy; about 35 minutes with the TI model) |

**Reference results** (Rev C value in brackets)
- 1 A and 8 A, with or without 47 uF: settled at exactly the CV setting (12.00 V, 9.998 V) within 0.2 mV pp by 50 ms (11.97 / 9.97 V, 4 mV pp): the rail-to-rail output removes the LT1013's 0.25 % floor error, so the CV scale error is only the 0.049 ratio
- 0.1 A without C: settled, 0.2 mV pp (3 mV pp)
- **0.1 A with 47 uF: underdamped, a ~50 Hz ring of 10.6 V pp at 50 ms that is still 4.1 V pp at 149 ms** (7.3 V pp, 1.7 V pp): worse than Rev C. 0.1 A stays the CV minimum; a capacitive source at that current wants CC or several seconds to settle
- A +10 % source step lifts V(DUT+) by 1 to 6 V for tens of ms, then it recovers (same as Rev C). CV here is for static tests, not fast transients

Model limits: 2N7002 is a generic VDMOS estimate, the DUT is ideal, and the TLV9152 macromodel is TI's. Verify on the bench.
