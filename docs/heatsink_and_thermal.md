# Heatsink and thermal plan

## The scrap heatsink (measured 2026-11-01)
An L-shaped extrusion: base 65 × 170 mm, 3 mm thick, flat on top for 60 mm then a 1 mm fillet into the wall; 17 fins of 15 mm under the base
running along the 170 mm direction (3.8 mm pitch, 2.3 mm channels); wall 45 × 170 mm, 5 mm thick, inner face flat. Behind the wall are ragged,
part-milled fins, so the outer wall face is not a mounting surface. Both usable faces look into the L pocket (60 wide, 45 tall).

The 2.3 mm channels are a forced-air fin stack: in still air the boundary layers fill them. Fin area about 0.09 m².

| Cooling | Rsa (sink → air) | Max power for an 80 °C heatsink at 30 °C ambient |
|---|---|---|
| Natural convection | ≈ 2 K/W | **≈ 25 W** |
| Blower through a closed duct over the fins | ≈ 0.3–0.4 K/W | **125–165 W** |

Deck 05 uses 0.35 K/W with the fan. **The fan is mandatory for 150 W** and the fanless firmware limit is about 25 W, not 55 W. The tunnel is only
65 × 15 mm, so an axial fan on its end cannot push air through it: use a **5 V** centrifugal blower (5015 or 6015, outlet 15 to 20 mm tall, about
0.2 A; Rev E runs it straight from VBUS through the J2 switch, there is no 12 V rail any more) at one end, or a 40 × 40 × 20 mm 5 V high-static fan
through a printed nozzle, and a printed cover that closes the open fin side into a duct. A 5 V blower has less static pressure than a 12 V one, so
measure Rsa with the duct fitted before trusting 150 W. The OTP trips at 85 °C heatsink.

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
- The power board lies on the base top on 12 mm standoffs with the four TO-247s flat underneath (tab down, leads bent up through the board) at 40 mm
  pitch, bodies toward the wall, the NTC lug between FET 2 and 3, and a 7 mm access hole in the board above each tab screw. The 3 mm base spreads heat
  about 50 mm sideways under forced air, so the 40 mm pitch covers it. M3 tapped into 3 mm is six threads: torque 0.5 N·m, no second tapping.
  (Form W / form P in the mechanical brainstorm; the wall becomes the rear panel and keeps its ragged fins as a free radiator. Rev E: the power
  board is exactly the base size, 170 × 60 mm, FETs at 31 / 69 / 107 / 145 mm, 38 mm pitch.)
- **Insulated or live heatsink?** All four tabs are DRAIN, so a common, un-insulated mount works electrically, and Rcs drops from ~0.5 to
  0.24 K/W (Tj falls by ~10 °C). The heatsink then carries the DUT voltage (up to 60 V). It must then be isolated from the enclosure and
  from your fingers. Recommended for a bench tool: **insulate** (silicone pad or Kapton MT + paste, shoulder washers on M3 screws),
  then check > 10 MΩ tab-to-sink with a meter before power-up.
- Torque the M3 screws about 0.6 N·m. Use a clip or a 3 mm steel plate across the TO-247s for even pressure if you have one.
- The heatsink is tied to the enclosure (USB side); the FET insulator is part of the isolation barrier, so use a silicone pad rated 2 kV or more with
  shoulder washers and check > 10 MΩ tab to sink before power. Keep the gate and source leads short; the 47 Ω gate resistors go right at the pins.

## MOSFET junction estimates (150 W, Ta 30 °C, Rsa 0.35 K/W, insulated)
From `mosfet_selection.md`: IRFP250N 127.5 °C, IRFP240 132.4 °C (cap at 130 W), IXTH30N25L2 114.5 °C, IRF530 ×4 184 °C (fails; ≤ 117 W only).
Rev B's 2 × IRF530 at 150 W would be about 285 °C.
