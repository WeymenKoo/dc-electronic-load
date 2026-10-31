# Rev C compared with the AliExpress loads (DL24 / DL24P / DTL150 family)

Evidence is mostly forum measurements and one teardown of an older Atorch unit, not lab reports. Treat each row as "reported", and note that units vary.

| Reported problem on the cheap loads | Source | Rev C answer | Status |
|---|---|---|---|
| Gate spikes to 27.6 V on a ±20 V FET, ringing about 37 V; three FETs blown at about 40 V | [teardown](https://mirror.sevarg.net/2018/06/24/the-atorch-purple-fan-mosfet-destroyer/) | 15 V gate-source zener, Rg at the gate, compensated loop (PM ≥ 80°) | Simulated; bench step test pending |
| No fuse found; a shorted FET across a battery is unlimited | same | F1 15 A 58 V DC | Designed |
| Smoke at 20 V / 9 A, bang under 90 W on a 36 V pack, "practical maximum about 100 W" | [EEVblog DL24P thread](https://eevblog.com/forum/testgear/cheezeball-dc-load-dl24p-pump-or-dump/150) | 4 × TO-247 at 37.5 W each, Tj 127.5 °C at 150 W | Depends on heatsink Rsa, **still an estimate** |
| Advice to stay below 32 V and 10 A despite a 200 V / 20 A label | [done.land](https://done.land/tools/devices/electronicload/dl24atorch/) | 58 V, 10.2 A are the real limits, each with a reason | Designed |
| Weak LM321 driving the gate; instability and high current on reconnect | EEVblog, same thread | KILL line: peak = setpoint on hot-plug and recovery | Simulated, deck 04 |
| Non-CC modes likely in software, slow, with overshoot | EEVblog, same thread | Hardware CV loop | Simulated, deck 06 |
| Unbalanced FET heating, shunts of mismatched value | [EEVblog p. 14](https://eevblog.com/forum/testgear/cheezeball-dc-load-dl24p-pump-or-dump/325) | One op-amp loop per FET | Simulated, deck 01 |
| Series reverse-protection Schottky at 0.42 V, 85–100 °C; limits low-voltage use | EEVblog p. 14 | No series diode, works from about 0.6 V; reverse polarity clears the fuse instead | Designed |
| 4-wire voltage error growing with current | EEVblog, same thread | Separate sense amp and pair (J7) | Designed |
| Low-voltage cut-off re-enables on battery rebound | teardown | Firmware latch (requirement) | Firmware not written |
| Possibly used or counterfeit FETs in the unit | EEVblog p. 14 | You choose the source: buy from an authorised distributor | – |

## Where Rev C does NOT win
- **Price of a finished unit.** One older listing had a 150 W tester [at about $30](https://budgetlightforum.com/t/mini-review-150w-load-unit/43730). Rev C's parts come to about US$65–90 by my estimate, excluding your scrap heatsink and fan and the control board you already own. It beats a [Siglent SDL1020X-E at about $574](https://valuetronics.com/apps/aeo/ai/md/default/products/8359457521911.md), not a DL24.
- **Very low current.** A DL24 was reported usable down to about 10 mA. Rev C has a deliberate 72 mA dead zone in CC and a 0.1 A minimum in CV. For a small current source, use a resistor or decade box.
- **Readback resolution.** The 12-bit ADC gives 2.7 mA and 16 mV per LSB. For a precision current source, the DMM in series is the reference and the load only sets the compliance voltage.
- **Ground.** DUT− is common with USB ground, the same class of problem the DL24P thread reports. See the warning in the spec.
- **It exists today.** Firmware for every mode above CC is unwritten.

## Cost estimate (not quotes; check before ordering)
| Item | Estimate | Basis |
|---|---|---|
| 4 × IRFP250NPBF | $13 | [about $3.29 each at Mouser](https://www.flux.ai/jecstronic/irfp250npbf~3kd.md), aggregator figure |
| LT1014DSW#TRPBF | $10 | [about €9.73](https://punchouttest.digikey.es/en/products/detail/analog-devices-inc/LT1014DSW-TRPBF/962051); the non-reel #PBF showed out of stock |
| 2 × LT1013DS8 | $10–15 | my estimate, no price found |
| Passives including 0.1 % parts, LM339, small FETs, diodes | $10–15 | my estimate |
| Connectors, fuse + holder, 2 binding posts + 2 sense terminals | $10–15 | my estimate |
| 2 oz PCB | $5–15 | my estimate |

**Biggest saving not taken:** a TI TLV9104/TLV9102 would cost far less than the LT parts and has close GBW (1.1 MHz), but its Vos is ±1.5 mV max against the design's ≤ 1 mV requirement, its package differs and it is unsimulated. I kept the simulated parts. Also treat the very cheap LCSC IRFP250N listings (under $1) as suspect.
