# LTspice simulation package (analog stage of Rev C / Rev D / Rev E)

> The analog stage simulated here is unchanged in Rev D except for the reference rail (4.096 V became the ratiometric +5V_ISO).
> **Rev E replaces the LT1014 / LT1013 with TLV9154 quads: the same decks re-run with TI's model live in `rev_e/` (its README has the
> side-by-side results table).** The Rev C decks and results below are kept as the reference. `hardware/tools/check_netlist_reve.py` proves
> the Rev E KiCad netlist against `rev_e/06_cv_mode/06_cv_mode.net` node by node.
>
> **Run LTspice from a local copy** (`tools/ltrun_local.sh <deck>.asc`): Google Drive File Stream breaks LTspice's incremental `.raw` writes.

Six simulations, **each in its own folder** (numbered in run order). Every component is connected with drawn wires.
Net labels are used only for ground, the supply rails (+12V, +3V3, +4V096), to *name* a wire for `.meas`, and for two long
sense lines (`DRAIN`, `KILL`) that would otherwise cross all four channels. Each sheet carries its own test description,
pass criteria and every `.param / .step / .meas` directive, so a screenshot of the sheet is self-contained.

Built and checked with **LTspice 26.0.2 (macOS)**. Every `.asc` was netlisted by LTspice and compared node-by-node against the
intended circuit before it was run.

```
../simulation/
├── 00_baseline_rev_b/   ┐  each folder:  <name>.asc          schematic
├── 01_dc_transfer/      │                <name>.plt          LTspice waveform layout (loaded automatically after Run)
├── 02_step_response/    │                plot_<name>.py      matplotlib script that rebuilds results/fig*.png
├── 03_loop_gain/        │                results/            reference .log, figure, layout preview
├── 04_faults/           │                README.md           question, files, reference numbers
├── 05_thermal/          ┘
├── lib/                 shared models (decks use .include ../lib/...)
├── common/ltspice_raw.py  .raw reader used by every plot_*.py
├── measurements_summary.txt  all .meas results in one place
├── rev_e/               the TLV9154 re-run of decks 01-04 and 06 (build_decks.py --rev-e, write_plots.py --rev-e), own README and summary
├── lib/tlv915x.lib      TI TLV9152 PSpice macromodel (SBOMB53B), used for the TLV9154
└── tools/               generator: build_decks.py (schematics), write_plots.py (.plt + plot_*.py), ltrun.sh / ltrun_local.sh (headless runs)
```

| Folder | Question it answers | Analysis | Runtime |
|---|---|---|---|
| `00_baseline_rev_b/` | Why can't the Rev B power board (as built, Nov 2024) reach full scale, and what does its VSEN amp do? | `.dc`, IRF530 VGS(th) stepped 2/3/4 V | < 1 s |
| `01_dc_transfer/` | Rev C transfer: A/V, full scale, current sharing, ISEN and VSEN accuracy, dropout headroom | `.dc` LOAD_CTRL 0→4.096 V, DUT 1/2/12/48 V | ~2 s |
| `02_step_response/` | Large- and small-signal step response, all MOSFET candidates, 1 µH and 10 µH leads | `.tran` 1.3 ms × 8 | ~5 s |
| `03_loop_gain/` | Stability margins of one channel (Middlebrook injection) across MOSFET × current × lead inductance | `.ac` × 24 | ~6 s |
| `04_faults/` | Hot-plug, DUT collapse/recovery (integrator wind-up), over-temperature trip | `.tran` 3.5 ms × 4 | ~6 s |
| `05_thermal/` | Junction/heatsink temperatures at 150 W for 2/3/4 MOSFETs and four heatsink Rsa values | thermal RC analogue, 1 h | < 1 s |
| `06_cv_mode/` | Hardware CV holding a current-source DUT, 0.1–8 A, with and without 47 µF | `.tran` 150 ms × 6 | ~1 min, 500 MB `.raw` |

## How to run
1. Open `<folder>/<name>.asc` in LTspice and press **Run**. Keep `lib/` where it is, because the decks include `../lib/…`.
2. The waveform window opens with the layout from `<name>.plt`: same traces, panes and axis ranges I used. Stepped runs are overlaid; use
   right-click → *Select Steps* to isolate one.
   If you rearrange the plot, LTspice saves your layout back into that `.plt` (**File → Save Plot Settings**).
3. Read the numbers in **View → SPICE Error Log** (the `.meas` results). Nothing needs reading off a cursor.
4. `python3 <folder>/plot_<name>.py` (needs numpy and matplotlib) rebuilds that folder's `results/fig*.png` from its `.raw`.
   The step-index mapping (which `.step` combination is which run) is commented at the top of each script.

Batch (Windows/Linux): `LTspice -b 01_dc_transfer/01_dc_transfer.asc`.
macOS CrossOver build: `/Applications/LTspice.app/Contents/SharedSupport/ltspice/LTspice/wine --bottle ltspice -- "C:\Program Files\ADI\LTspice\LTspice.exe" -b "Z:<full path>.asc"`.

## Models (`lib/`)
- `fet_models.lib`: verbatim VDMOS models from LTspice's own `standard.mos` (Analog Devices, shipped with 26.0.2), so no third-party model is needed.
  `FETSEL` is a single model whose parameters are switched by `.param fet = 1..4`, so one schematic can `.step` through the candidates.
  It was checked against the four direct models: phase margin and gate voltage agree to 6 significant figures.
  - fet 1 = **IRFP250N** (primary), 2 = **IRFP240** (backup), 3 = **IRF530** (the Rev B part), 4 = **IXTH88N30P**.
    fet 4 is a large-die IXYS part (Ciss ≈ 15 nF, very high gm). It stands in for the IXYS linear-rated "L2" parts, which have no LTspice model.
    It is the worst case for loop stability. **Use it for stability only, not for DC numbers.**
- `misc_models.lib`: generic 6.8 V zener (only the breakdown knee matters).
- LT1013 / LT1014: Analog Devices encrypted macromodels, which LTspice loads itself.
- The LM339 comparators are modelled as voltage-controlled switches. That is enough to test the *function*, but it does not model comparator propagation delay (~1 µs in the datasheet).
- The "LMV358" in deck 00 is LTspice's UniversalOpAmp2 with rail-to-rail output on a 4.096 V supply. That is the **best case** for the real part, so the failure shown in deck 00 is not exaggerated.

## Results (from each `<folder>/results/<name>.log`, collected in `measurements_summary.txt`)

| # | Result | Value | Figure |
|---|---|---|---|
| 00 | Rev B current per channel at full scale (target 6.14 A) | 5.68 A / 2.05 A / **0.04 A** for VGS(th) = 2 / 3 / 4 V; gate pinned at 4.096 V | fig00 |
| 00 | Rev B VSEN output at DUT = 12 V (should be 1.20 V) | **4.10 V (latched at the rail)** | – |
| 01 | Transfer gain | 2.500 A/V (2.44 mA per DAC LSB) | fig01a |
| 01 | Full scale (LOAD_CTRL = 4.096 V) | 10.17 A (10.24 A nominal minus the 72 mA deliberate zero offset) | fig01a |
| 01 | Channel-to-channel sharing | identical to 4 significant figures (per-channel loops) | log |
| 01 | ISEN error after zero-offset subtraction | −0.008 % at full scale | fig01b |
| 01 | VSEN error against its ideal transfer (formula in the `.meas`) | < 0.005 % of reading from 0.9 V to 48 V | log |
| 01 | Full current still reached at DUT = 1 V | yes (V(DUT+) = 0.90 V at 5 A) | log |
| 02 | 10–90 % rise, 1 A → 9 A | 21–31 µs depending on MOSFET | fig02a |
| 02 | Overshoot, large and small step | **0 %** (IXTH proxy with 10 µH: 0.04 %) | fig02 |
| 03 | Phase margin, worst of 24 corners | **80.3°** (IXTH proxy, 2.5 A, 10 µH); planar FETs ≥ 86° | fig03 |
| 03 | Gain margin, worst of 24 corners | **13.2 dB** (same corner); planar FETs ≥ 22 dB | fig03 |
| 03 | Crossover frequency | 0.45–0.55 kHz at 25 mA/ch, 15–35 kHz at 2.5 A/ch | fig03 |
| 04 | Peak current on hot-plug at an 8 A setting | **8.12 A = setpoint** (no overshoot), all FETs | fig04 |
| 04 | Peak current on DUT recovery after collapse | **8.12 A = setpoint**, all FETs | fig04 |
| 04 | Current during dropout (DUT at 0.4 V) | 0.4 mA | fig04 |
| 04 | OTP trip: time to < 0.8 A | 2–35 µs | fig04 |
| 05 | Tj at 150 W, 4 FETs, Rsa 0.35 K/W, Ta 30 °C | **127.5 °C** (heatsink 82.5 °C) | fig05 |
| 05 | Same with 2 FETs (Rev B count) | 172.5 °C, above any sensible limit | fig05 |
| 05 | No fan (Rsa ≈ 0.9 K/W) | 210 °C at 150 W, so the fan is mandatory above ~55 W | fig05 |
| 06 | CV on a current source, 12 V and 10 V | settled to < 4 mV pp by 50 ms; 0.1 A with 47 µF rings at ~50 Hz and needs about 1 s | fig06 |

### What the simulation changed in the design (history, so the numbers above make sense)
1. The Rev B compensation (3.3 k / 220 p / 100 Ω) is fine for IRF530/IRFP250N, but a large-die MOSFET
   at 2.5 A gets only **−13° to 25° phase margin**, so it would oscillate. Rev C uses **3.3 k / 1 nF / 47 Ω**: ≥ 80° for every candidate.
2. In the first Rev C draft, a hot-plug or DUT recovery produced **115–170 A spikes** from integrator wind-up.
   A 6.8 V zener across Cc alone only halved this. Pulling V_SET low alone left the integrators unwinding at
   ~0.45 V/ms, which is too slow. The fix that works is the **KILL line**: the dropout comparator lifts every op-amp's In− through 1N4148 + 4.7 k.
   Together with the zener and the 22 MΩ zero-offset bias, the peak is now 8.12 A (the setpoint).
3. The LT1013 output floor (~35 mV with its inverting input near 0 V) hid DUT voltages below ~0.7 V.
   Fix: 470 k / 1 M offset resistors from +4.096 V give ~+85 mV / +120 mV offsets, which a zero calibration removes.

## Model-dependent numbers – read before quoting them
- Rise times and margins depend on the LT1013/LT1014 macromodel and on the VDMOS capacitances. Treat them as ±30 %.
  Verify on the bench with the step test (bring-up step 6 in `03_Hardware_Spec`).
- The IXTH88N30P is a proxy. When you buy an IXYS L2 part, put its datasheet Ciss/Crss and transfer
  characteristic into a fifth `FETSEL` entry and re-run deck 03.
- Thermal (deck 05): Rsa is an **estimate** for your scrap heatsink. Measure it (see `heatsink_and_thermal.md`) and re-run.
- The recovery case in deck 04 uses a deliberately brutal 24 V/µs DUT edge. A real PSU or battery is slower.

## Derived requirements (for the downstream blocks)
- **DAC / LOAD_CTRL source**: must drive 16 kΩ (15 k + 1 k) to ground. MCP4725 is fine. Power-on value must be 0 (program the MCP4725 EEPROM to 0x000).
- **Op-amp substitution**: input common mode must include 0 V, supply ≥ 12 V, |Vos| ≤ 1 mV (the zero-offset bias is +1.8 mV), and output high ≥ 8 V into 47 Ω + gate.
  If GBW differs from ~0.8 MHz, re-run deck 03. (Done for the TLV9154 in Rev E: Vos limit 0.83 mV, bias raised to +2.6 mV, GBW 4.5 MHz, margins in `rev_e/README.md`.)
- **ADC**: ISEN 0.300 V/A + 0.12 V; VSEN 0.0490 V/V + 0.085 V. 1 kΩ / 10 nF source, so use an STM32 sample time ≥ 41.5 cycles.
  Inputs are clamped to 3V3 by BAT54S.
- **+12 V rail**: ~5 mA for the analog parts plus the fan (≤ 0.5 A).
  **+4.096 V rail (REF5040)**: < 1 mA (offset and NTC networks only). Rev C no longer powers any op-amp from the reference.
- **Minimum DUT voltage**: load disables below 0.5 V at DRAIN; full 10 A available from ≈ 1 V.
- **Firmware power limit**: 150 W with the fan running and the heatsink measured at Rsa ≤ 0.35 K/W; otherwise P_max = (85 °C − Ta) / Rsa_measured.

## Regenerating the schematics and plot files
`tools/build_decks.py` (with `ascgen.py`) writes every `<folder>/<name>.asc`, runs the LTspice netlister and checks each node against
the intended netlist. `tools/write_plots.py` writes the `.plt` files, the `plot_*.py` scripts and `common/ltspice_raw.py`.
You only need these to change things programmatically; normal edits can be made in LTspice directly.
`tools/ltrun.sh` is the headless LTspice runner for the macOS CrossOver build; `tools/ltrun_local.sh` is the same on a local copy of the tree (use this one on Google Drive).
`python3 tools/build_decks.py --rev-e` and `python3 tools/write_plots.py --rev-e` regenerate the Rev E folder.
