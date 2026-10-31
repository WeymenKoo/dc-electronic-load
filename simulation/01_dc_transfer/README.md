# 01_dc_transfer

**Question:** Rev C transfer: A/V, full scale, current sharing, ISEN/VSEN accuracy, dropout headroom.
**Analysis:** `.dc` LOAD_CTRL 0-4.096 V, DUT stepped 1 / 2 / 12 / 48 V

| File | What it is |
|---|---|
| `01_dc_transfer.asc` | The schematic: wired, with the test description and all directives on the sheet |
| `01_dc_transfer.plt` | LTspice plot layout. Opens automatically with the waveform window after you run the sim. Top: total current and CH1 current. Bottom: V(ISEN_ADC) and V(VSEN_ADC). |
| `plot_01_dc_transfer.py` | Reproduces `results/fig*.png` from `01_dc_transfer.raw` (matplotlib) |
| `results/01_dc_transfer.log` | The `.meas` results from the reference run (LTspice 26.0.2) |
| `results/fig*.png` | The figure used in the package README |
| `results/schematic_preview.png` | Rough layout preview from the generator, not an LTspice render. Take screenshots in LTspice. |

**Reproduce:** open `01_dc_transfer.asc` in LTspice, press Run, then read **View -> SPICE Error Log** for the numbers.
Then `python3 plot_01_dc_transfer.py` (needs numpy and matplotlib) rewrites the figure. Models come from `../lib/`.

**Reference results**
- 2.500 A/V, 10.17 A full scale (10.24 A minus the 72 mA zero offset)
- All 4 channels equal to 4 significant figures
- ISEN error -0.008 %, VSEN error < 0.005 % after zero calibration
- Full current still reached at a 1 V DUT
