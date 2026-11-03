# 01_dc_transfer (Rev E, TLV9154)

**Question:** Rev E transfer: A/V, full scale, current sharing, ISEN and VSEN accuracy, dropout headroom, with the TLV9154 in place of the LT1014 / LT1013 and Rb = 15M.
**Analysis:** `.dc` LOAD_CTRL 0 → 4.096 V, DUT 1 / 2 / 12 / 48 V (4 runs). Same deck as `../../01_dc_transfer`, only the op-amp model, Rb and the include lines differ.

| File | What it is |
|---|---|
| `01_dc_transfer.asc` | The schematic: wired, with the test description and all directives on the sheet (`.include ../../lib/tlv915x.lib`) |
| `01_dc_transfer.plt` | LTspice plot layout, same panes as the Rev C deck |
| `plot_01_dc_transfer.py` | Reproduces `results/fig*.png` from `01_dc_transfer.raw` (matplotlib) |
| `results/01_dc_transfer.log` | The `.meas` results from the reference run (LTspice 26.0.2, run from a local copy: `../../tools/ltrun_local.sh`) |

**Reference results** (Rev C value in brackets)
- Transfer gain 2.501 A/V (2.500); full scale 10.14 A (10.17): the 15M offset resistor costs 106 mA instead of 72 mA
- Channels identical to 4 significant figures
- ISEN error after zero subtraction −0.002 % of full scale (−0.008 %)
- VSEN error against its ideal transfer +0.13 mV, i.e. 0.005 % of reading at 48 V, 0.29 % at 0.9 V (Rev C: < 0.02 mV). The TI macromodel's input bias current into the 200k / 10k network; the zero calibration removes it
- Full current reached at DUT = 1 V (V(DUT+) = 0.90 V at 5 A)

Runtime note: the TI macromodel needs LTspice's pseudo-transient operating-point fallback at LOAD_CTRL = 0 (every op-amp output sits at 0 V in the dead zone), so this deck takes about 13 minutes instead of 2 seconds. The "Direct Newton iteration failed" lines in the log are that fallback, not a failed run.
