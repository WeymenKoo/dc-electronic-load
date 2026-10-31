# Heatsink and thermal plan

## The scrap heatsink (estimate until measured)
Your heatsink is an extruded audio-amplifier sink about the size of two stacked phone boxes (≈ 17 × 9 × 7 cm, ~1 L envelope, ~0.5–0.6 kg aluminium).
Typical figures for that volume:

| Cooling | Rsa (sink → air) | Max power for an 80 °C heatsink at 30 °C ambient |
|---|---|---|
| Natural convection, fins vertical | ≈ 0.8–1.0 K/W | **≈ 55 W** |
| 80–92 mm fan blowing along the fins | ≈ 0.25–0.35 K/W | **150–200 W** |

Deck 05 uses 0.35 K/W with the fan, which is the conservative end. **The fan is mandatory for 150 W.** The Rev C power board runs the fan
from its own thermostat (45 °C on / 35 °C off), and the OTP trips at 85 °C heatsink.

Thermal time constant with the fan is about 4 minutes to 90 % (Csa ≈ 500 J/K). Without the fan it is about 15 minutes, so a short 150 W burst with the fan
off won't trip immediately. The firmware must enforce the no-fan limit and must not rely on the OTP for it.

## Measure Rsa before trusting 150 W (≈ 1 hour)
1. Mount the four FETs (with insulators if you use them) and the NTC. Put a K-type thermocouple in a hole or under a screw next to FET 2 (the middle of the sink).
2. Fan **off**, fins vertical. Set the load to a constant 30 W (for example 12 V × 2.5 A). Log the heatsink temperature until it stops rising (~40 min).
   `Rsa_natural = (T_sink − T_ambient) / 30 W`.
3. Fan **on**, 80 W, until steady (~15 min). `Rsa_fan = ΔT / 80 W`.
4. Put the numbers into `05_thermal.asc` (`.param Rsa=…`), re-run it, and set the firmware limits:
   `P_max = (80 °C − Ta) / Rsa` for each fan state, capped at 150 W.

## Mounting
- **Flatten and clean** the mounting face. Scrap sinks often carry old pads, paste or anodising scratches. Lap it on 400-grit paper on glass if it's bowed.
- Spread the 4 TO-247s along the base at ≥ 25 mm pitch, centred under the fin root and in the fan's airflow, with the NTC between FET 2 and 3.
- **Insulated or live heatsink?** All four tabs are DRAIN, so a common, un-insulated mount works electrically, and Rcs drops from ~0.5 to
  0.24 K/W (Tj falls by ~10 °C). The heatsink then carries the DUT voltage (up to 60 V). It must then be isolated from the enclosure and
  from your fingers. Recommended for a bench tool: **insulate** (silicone pad or Kapton MT + paste, shoulder washers on M3 screws),
  then check > 10 MΩ tab-to-sink with a meter before power-up.
- Torque the M3 screws about 0.6 N·m. Use a clip or a 3 mm steel plate across the TO-247s for even pressure if you have one.
- The Rev C PCB should sit along the heatsink edge with the FET legs bent 90°. Keep the gate and source leads short; the 47 Ω gate resistors go right at the pins.

## MOSFET junction estimates (150 W, Ta 30 °C, Rsa 0.35 K/W, insulated)
From `mosfet_selection.md`: IRFP250N 127.5 °C, IRFP240 132.4 °C (cap at 130 W), IXTH30N25L2 114.5 °C, IRF530 ×4 184 °C (fails; ≤ 117 W only).
Rev B's 2 × IRF530 at 150 W would be about 285 °C.
