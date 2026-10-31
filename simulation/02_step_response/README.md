# 02_step_response

**Question:** Large- and small-signal step response for all MOSFET candidates, with 1 uH and 10 uH leads.
**Analysis:** `.tran` 1.3 ms, fet stepped 1-4 x Llead 1u/10u (8 runs)

| File | What it is |
|---|---|
| `02_step_response.asc` | The schematic: wired, with the test description and all directives on the sheet |
| `02_step_response.plt` | LTspice plot layout. Opens automatically with the waveform window after you run the sim. Top: total current. Middle: gate CH1 and CH4. Bottom: LOAD_CTRL and V_SET. |
| `plot_02_step_response.py` | Reproduces `results/fig*.png` from `02_step_response.raw` (matplotlib) |
| `results/02_step_response.log` | The `.meas` results from the reference run (LTspice 26.0.2) |
| `results/fig*.png` | The figure used in the package README |
| `results/schematic_preview.png` | Rough layout preview from the generator, not an LTspice render. Take screenshots in LTspice. |

**Reproduce:** open `02_step_response.asc` in LTspice, press Run, then read **View -> SPICE Error Log** for the numbers.
Then `python3 plot_02_step_response.py` (needs numpy and matplotlib) rewrites the figure. Models come from `../lib/`.

**Reference results**
- 10-90 % rise 21-31 us (1 A -> 9 A)
- Overshoot 0 % (0.04 % worst case, IXTH proxy with 10 uH)
