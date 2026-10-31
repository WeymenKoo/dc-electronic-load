# MOSFET selection – Rev C power stage (150 W, 4 channels)

## What matters for an electronic load (not what matters for a switcher)
An e-load MOSFET runs **in saturation, continuously**, at high Vds and modest current. RDS(on), Qg and switching speed are almost irrelevant here. What matters:

1. **Thermal resistance RθJC and package.** Steady-state power is the whole job, and TO-247 beats TO-220.
2. **DC forward-bias SOA at elevated case temperature.** Modern *trench* and logic-level MOSFETs (very low RDS(on), high gm at low current)
   suffer from the **Spirito effect**: below a crossover current the threshold falls as the die heats, so current crowds into hot spots and the die fails
   *inside* the datasheet's Pd rating. Old **planar** parts (IRFP250N, IRFP240, IRF530) and parts sold as linear-mode
   (IXYS "L2", guaranteed FBSOA) are the safe choices.
3. **VDS margin.** 60 V target with a 200 V part leaves room for DUT transients and inductive kick.
4. **Gate capacitance and gm.** These set loop stability. Rev C compensation was chosen to be stable for all candidates below (deck 03).
5. **Genuine parts.** IRFP250N/IRFP240 are among the most counterfeited MOSFETs. Buy from an authorised distributor (Digi-Key, Mouser, LCSC direct stock), not from a marketplace.

**Avoid for this load:** the logic-level trench parts in `../reference/scullcom_dc_load_updates/DC_Load_Power_Mosfet_selection.pdf`
(IRLB4030, PSMN2R5-60PL, IRL60B216, BUK956R1-100E, STP80NF55L-06, IPP0xxN06L…). They are excellent switches, but most do not publish a DC SOA line,
and the Spirito effect applies. **CSD19536KCS** (in `../datasheets/`) is also a trench part. Use it only if its datasheet DC-SOA line covers 60 V at 0.7 A and Tc = 100 °C.

## Operating point used for the numbers
150 W shared by 4 FETs (per-channel loops guarantee equal current at equal Vds, so 37.5 W each); Ta = 30 °C; heatsink Rsa = 0.35 K/W
(scrap audio heatsink with a fan, estimate) → **heatsink 82.5 °C**; RθCS = 0.5 K/W (insulated TO-247) or 1.0 K/W (insulated TO-220).
Worst-case per-FET SOA points: 60 V × 0.625 A (37.5 W) and 15 V × 2.5 A (37.5 W).

| Rank | Part | VDS | Package | RθJC (K/W) | Tj max | Tj at 150 W | Margin | Allowed Pd at that Tc | Max total P (Tj ≤ Tjmax − 25 °C) | LTspice model |
|---|---|---|---|---|---|---|---|---|---|---|
| **Primary** | **Infineon IRFP250NPBF** | 200 V | TO-247AC | 0.70 | 175 °C | **127.5 °C** | 47.5 °C | 105 W (2.8 × the 37.5 W used) | **185 W** | built-in (`fet=1`) |
| Backup A | Vishay IRFP240PBF | 200 V | TO-247AC | 0.83 | 150 °C | 132.4 °C | 17.6 °C | 59 W (1.6×) | 139 W, so **cap firmware at 130 W** | built-in (`fet=2`) |
| Backup B (linear-rated) | IXYS/Littelfuse **IXTH30N25L2** | 250 V | TO-247 | ≈ 0.35 (355 W rating) | 150 °C | 114.5 °C | 35.5 °C | 138 W (3.7×) | 169 W | none; stability proxy `fet=4` |
| Backup C (linear-rated, 100 V) | IXYS/Littelfuse IXTH110N10L2 | 100 V | TO-247 | ≈ 0.2 (600 W rating) | check datasheet | ≈ 110 °C | large | very large | > 200 W | none; stability proxy `fet=4` |
| Stock only | IRF530 (Rev B part), 4 pcs | 100 V | TO-220 | 1.7 | 175 °C | **184 °C – fails** | −9 °C | 32 W (0.9×) | **117 W**, OK for 100 W tests | built-in (`fet=3`) |

Notes
- The IRFP250N VGS(th) is 2–4 V. At 2.56 A per channel it needs about 5–6 V of gate, well below the 6.8 V zener anti-wind-up clamp and the ~10.5 V the LT1014 can deliver.
- **IXYS L2 parts** cost about 10× an IRFP250N (~US$10–20) and have had long lead times (DigiKey showed 22–39 weeks on some regional sites).
  They are the "bullet-proof" option: FBSOA is *guaranteed* at Tc = 75 °C, which no planar HEXFET datasheet offers.
  Their VGS(th) is 2.5–4.5 V (IXTH30N25L2), so the 6.8 V clamp still has margin. They are big-die parts,
  which is exactly why Rev C uses Cc = 1 nF: deck 03 shows the old 220 pF would oscillate with them.
- Same TO-247 footprint for every Rank 1–3 part. Lay out once and populate whichever you can buy.
- Mixing part numbers *within one board* is electrically fine (each FET has its own loop) but not recommended thermally.

## Datasheets to drop into `04_KiCad/datasheets/`
IRFP250NPBF (Infineon), IRFP240PBF (Vishay doc 91210), IXTH30N25L2 (Littelfuse DS100919B), IXTH110N10L2 (Littelfuse).
Check RθJC, Tj max and the SOA figure against the **current** revision before ordering. The values above came from distributor
copies; IRFP240's RθJC is derived from its 1.2 W/°C derating factor.

Sources checked (Oct 2026): Infineon IRFP250NPBF datasheet via element14/radiolocman; Vishay IRFP240PBF datasheet; Littelfuse
IXT_30N25L2 and IXTH110N10L2 datasheets and DigiKey listings.
