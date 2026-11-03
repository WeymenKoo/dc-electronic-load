# 02_step_response (Rev E, TLV9154)

**Question:** Large- and small-signal step response for all MOSFET candidates, with 1 uH and 10 uH leads, with the TLV9154 (4.5 MHz GBW against the LT1014's 0.8 MHz).
**Analysis:** `.tran` 1.3 ms, fet stepped 1-4 × Llead 1u / 10u (8 runs)

| File | What it is |
|---|---|
| `02_step_response.asc` | The schematic: wired, with the test description and all directives on the sheet |
| `02_step_response.plt` | LTspice plot layout. Top: total current. Middle: gate CH1 and CH4. Bottom: LOAD_CTRL and V_SET |
| `plot_02_step_response.py` | Reproduces `results/fig*.png` from `02_step_response.raw` (matplotlib) |
| `results/02_step_response.log` | The `.meas` results from the reference run (LTspice 26.0.2, local copy) |

**Reference results** (Rev C value in brackets)
- 10-90 % rise 22.5-31 us for 1 A → 9 A (21-31 us): the C33 / V_SET filter and the FET set the speed, not the op-amp
- Overshoot 0 % for IRFP250N, IRFP240, IRF530 at 1 uH and 10 uH (0 %)
- **IXTH88N30P big-die proxy, 1 uH: 53 % overshoot, 13.6 A peak, then a sustained ~300 kHz ring** (0 %); at 10 uH 0.1 %. The faster op-amp plus the proxy's 15 nF Ciss: see deck 03 (GM 9 dB). The BOM part is the IRFP250N; if a large-die linear FET is ever fitted, raise Cc to 2.2 nF and re-run decks 02 and 03
- Small step 1 A → 2 A: no overshoot
