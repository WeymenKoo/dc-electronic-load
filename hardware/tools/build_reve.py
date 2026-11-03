#!/usr/bin/env python3
"""Generates the DC Load Rev E schematic: the cheapest build of the Rev D architecture. A control board and a power board on ONE
2-layer fabrication panel (V-score), joined by a 12-way IDC ribbon cable (page 5). Galvanically isolated, USB-C powered, OLED UI.
KiCad 10, hierarchical. The analog stage is the Rev C design re-simulated with the TLV9154 (../../simulation/rev_e decks 01-04, 06);
every part is chosen from the JLCPCB / LCSC catalogue (LCSC field on the symbol, ../outputs/rev_e_v1/BOM_RevE_JLC.csv for prices).
Rev D -> Rev E: TLV9154 quads replace LT1014 / LT1013 (Rb 22M -> 15M); OLED module + 2 LEDs replace the MAX7219 7-segment panel;
5 V blower from VBUS replaces the MT3608 boost; 78L05 replaces the MCP1703; CA-IS3761HW (pin-compatible) replaces the ISO7761;
STM32G0B1RBT6 (LQFP64, the one JLC stocks) replaces the CBT6; M4 bolt terminals replace the REDCUBE studs; the mini-blade fuse is
soldered in; every 0.1 % resistor is 1 % (gain errors are calibrated out, see ../../docs/rev_e_specification.md).

Drawing rules (enforced by kgen.lint(), the build fails on any violation):
  A3 for every sheet; JetBrains Mono; 1.6 mm references and values, 1.4 mm labels, 2.0 mm notes, 2.5 mm block titles, 4.5 mm sheet title;
  every circuit lives in a titled block whose frame is fitted to the content with a 6 mm margin; the drawing is centred on the sheet;
  no text overlaps any text, symbol or wire; no symbol overlaps another or a foreign wire; at most 3 wires per junction (staggered joints
  instead of 4-way crosses); wire crossings use hop-overs; the power sheet is drawn as a tree; the isolation barrier is a red dashed line.

usage: python3 build_reve.py        (writes ../rev_e/)"""
import os, json, copy, sys
import kgen
from kgen import Sch, KLIB, flatten, set_prop, uid, find, find1, Str, dump

kgen.set_uid_namespace('dcload-reve-%d')
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = 'DC_Load_RevE'
PDIR = os.path.join(HERE, '..', 'rev_e')
ROOT_UUID = '7a1d2c3e-4f50-4b61-9c72-8d83e94fa5b6'
DATE, REV = '2026-11-03', 'E'

# ---------------------------------------------------------------- style
FONT = 'JetBrains Mono'
FS_FIELD, FS_LABEL, FS_NOTE, FS_BLOCK, FS_TITLE, FS_SUB = 1.6, 1.4, 2.0, 2.5, 4.5, 2.0
C_NOTE = (40, 40, 40)
C_PWR = (190, 0, 0)          # supply rails
C_HI = (140, 70, 0)          # high-current DUT path (0.6 mm)
C_SET = (170, 0, 170)        # set-point chain
C_MEAS = (0, 80, 200)        # measurement
C_PROT = (220, 110, 0)       # protection
C_SPI = (110, 0, 180)        # isolated SPI
C_USB = (0, 140, 140)        # USB data
C_BAR = (200, 0, 0)          # isolation barrier
FILL_D = (235, 242, 252, 0.35)
FILL_A = (240, 250, 236, 0.35)
FILL_N = (245, 245, 245, 0.35)

R0603, R1206, R2512 = ('Resistor_SMD:R_%s_%sMetric' % s for s in (('0603', '1608'), ('1206', '3216'), ('2512', '6332')))
C0603, C0805, C1206 = ('Capacitor_SMD:C_%s_%sMetric' % s for s in (('0603', '1608'), ('0805', '2012'), ('1206', '3216')))
SOT23 = 'Package_TO_SOT_SMD:SOT-23'
SOD323 = 'Diode_SMD:D_SOD-323'
TO247 = 'Package_TO_SOT_THT:TO-247-3_Vertical'
TP = 'TestPoint:TestPoint_THTPad_D1.5mm_Drill0.7mm'
LED0603 = 'LED_SMD:LED_0603_1608Metric'
PH = 'Connector_PinHeader_2.54mm:PinHeader_1x%02d_P2.54mm_Vertical'
SO14 = 'Package_SO:SOIC-14_3.9x8.7mm_P1.27mm'
FFC = 'Connector_IDC:IDC-Header_2x06_P2.54mm_Vertical'              # J10, control board: vertical, hand-soldered on the BACK face, ribbon goes rearward
FFC_V = 'Connector_IDC:IDC-Header_2x06_P2.54mm_Vertical'           # J11, power board: vertical, the ribbon plugs in from above
FFC_MPN = '2x6 shrouded box header 2.54 mm, BOOMELE 2.54-2*6P (LCSC C9136). Pin n = ribbon conductor n'
STUD = 'MountingHole:MountingHole_4.3mm_M4_Pad'                   # M4 bolt through a plated pad: ring lug on the DUT lead, nut and washers
# J10 / J11 pin assignment (pin 1 to pin 1 through the cable). Power pins at the ends keep the schematic crossing-free.
LINK_PINS = {1: 'VBUS', 2: 'VBUS', 3: '+3V3', 4: 'SPI1_SCK', 5: 'SPI1_MOSI', 6: 'SPI1_MISO', 7: '~{CS_DAC}', 8: '~{CS_ADC}', 9: 'LOAD_OFF',
             10: 'DGND', 11: 'DGND', 12: 'DGND'}
LINK_SHAPE = {'SPI1_SCK': 'input', 'SPI1_MOSI': 'input', 'SPI1_MISO': 'output', '~{CS_DAC}': 'input', '~{CS_ADC}': 'input', 'LOAD_OFF': 'input'}


# ---------------------------------------------------------------- custom symbols
def lt_symbol(base, name, pinmap, descr, dsheet, fp):
    s = flatten(KLIB + 'Amplifier_Operational.kicad_sym', base, name)
    for u in find(s, 'symbol'):
        for p in find(u, 'pin'):
            n = find1(p, 'number')
            n[1] = Str(pinmap[str(n[1])])
    set_prop(s, 'Value', name); set_prop(s, 'Description', descr); set_prop(s, 'Datasheet', dsheet); set_prop(s, 'Footprint', fp)
    return s


TLV9154 = lt_symbol('LM2902', 'TLV9154', {str(i): str(i) for i in range(1, 15)},
                    'Quad 16 V rail-to-rail op-amp, 4.5 MHz, Vos 0.83 mV max, standard quad pinout. TLV9154IDR SOIC-14, LCSC C2873614',
                    'https://www.ti.com/lit/ds/symlink/tlv9154.pdf', 'Package_SO:SOIC-14_3.9x8.7mm_P1.27mm')
AMP = 'dcload:TLV9154'
AMP_F = {'MPN': 'TLV9154IDR', 'LCSC': 'C2873614'}


def power_sym(name):
    s = flatten(KLIB + 'power.kicad_sym', 'GND' if 'GND' in name else '+12V', name)
    set_prop(s, 'Value', name)
    return s


def dcdc_symbol():
    F = lambda: ['effects', ['font', ['size', 1.27, 1.27]]]
    H = lambda: ['effects', ['font', ['size', 1.27, 1.27]], ['hide', 'yes']]
    def pin(kind, num, name, x, y, ang):
        return ['pin', kind, 'line', ['at', x, y, ang], ['length', 5.08], ['name', Str(name), F()], ['number', Str(num), F()]]
    return ['symbol', Str('dcload:DCDC_ISO_1W'), ['exclude_from_sim', 'no'], ['in_bom', 'yes'], ['on_board', 'yes'],
            ['property', Str('Reference'), Str('PS'), ['at', 0, 12.7, 0], F()],
            ['property', Str('Value'), Str('B0512S-1W'), ['at', 0, -12.7, 0], F()],
            ['property', Str('Footprint'), Str('dcload:SIP-4_P2.54mm_DCDC_1W'), ['at', 0, 0, 0], H()],
            ['property', Str('Datasheet'), Str('https://www.mornsun-power.com/public/pdf/DCDC/B_S-1WR3.pdf'), ['at', 0, 0, 0], H()],
            ['property', Str('Description'), Str('Isolated DC-DC 1 W, 5 V in, 12 V / 84 mA out, 1.5 kVDC or better, SIP-4. PIN NUMBERS TO VERIFY against the datasheet of the part bought'), ['at', 0, 0, 0], H()],
            ['symbol', Str('DCDC_ISO_1W_0_1'),
             ['rectangle', ['start', -12.7, 10.16], ['end', 12.7, -10.16], ['stroke', ['width', 0.254], ['type', 'default']], ['fill', ['type', 'background']]],
             ['polyline', ['pts', ['xy', 0, 9.0], ['xy', 0, -9.0]], ['stroke', ['width', 0.254], ['type', 'dash']], ['fill', ['type', 'none']]]],
            ['symbol', Str('DCDC_ISO_1W_1_1'),
             pin('power_in', '1', 'VIN+', -17.78, 5.08, 0), pin('power_in', '2', 'VIN-', -17.78, -5.08, 0),
             pin('power_out', '4', 'VOUT+', 17.78, 5.08, 180), pin('power_out', '3', 'VOUT-', 17.78, -5.08, 180)]]


def cable_symbol():
    """BOM-only item: the flat flex cable between J10 and J11. No pins (the boards are separate nets), not on the board."""
    F = lambda: ['effects', ['font', ['size', 1.27, 1.27]]]
    H = lambda: ['effects', ['font', ['size', 1.27, 1.27]], ['hide', 'yes']]
    return ['symbol', Str('dcload:FFC_CABLE_12'), ['exclude_from_sim', 'yes'], ['in_bom', 'yes'], ['on_board', 'no'],
            ['property', Str('Reference'), Str('CBL'), ['at', 0, 6.35, 0], F()],
            ['property', Str('Value'), Str('FFC 12-way 1.0 mm'), ['at', 0, -6.35, 0], F()],
            ['property', Str('Footprint'), Str(''), ['at', 0, 0, 0], H()],
            ['property', Str('Datasheet'), Str(''), ['at', 0, 0, 0], H()],
            ['property', Str('Description'), Str('Flat flexible cable J10 to J11, 12 conductors, 1.0 mm pitch, about 80 mm. Not a board item.'), ['at', 0, 0, 0], H()],
            ['symbol', Str('FFC_CABLE_12_0_1'),
             ['rectangle', ['start', -15.24, 3.81], ['end', 15.24, -3.81], ['stroke', ['width', 0.254], ['type', 'dash']], ['fill', ['type', 'none']]]]]


CUSTOM = {'dcload:TLV9154': TLV9154, 'dcload:DCDC_ISO_1W': dcdc_symbol(), 'dcload:FFC_CABLE_12': cable_symbol()}
for _n in ('VBUS', '+3V3', '+12V_ISO', '+5V_ISO', 'DGND', 'AGND', 'PGND', 'VBUS_LK', '+3V3_LK', 'DGND_LK'):
    CUSTOM['dcload:' + _n] = power_sym(_n)
PWRN = [0]


class S(Sch):
    def __init__(self, title, subtitle='', extra=()):
        super().__init__(PROJ, 'A3')
        self.title = dict(title=title, date=DATE, rev=REV, company='DC Load Box')
        self.face, self.fs_field, self.fs_label, self.fs_pin, self.fs_block = FONT, FS_FIELD, FS_LABEL, FS_LABEL, FS_BLOCK
        self.grid = 1.27
        self.text(title, 18, 22, size=FS_TITLE, bold=True, color=(0, 40, 90))
        self.text(subtitle, 18, 26.5, size=FS_SUB, italic=True, color=(70, 70, 70))
        for i, e in enumerate(extra):
            self.text(e, 18, 30 + i * 3.5, size=FS_SUB, color=(70, 70, 70))
        self.fixed_texts = 2 + len(extra)
        self.area = (18, 32 + 3.5 * len(extra), self.W - 18, self.H - 44)

    def ensure(self, lib_id):
        if lib_id in self.libsyms:
            return
        if lib_id in CUSTOM:
            s = copy.deepcopy(CUSTOM[lib_id]); s[1] = Str(lib_id); self.libsyms[lib_id] = s
        else:
            lib, name = lib_id.split(':')
            self.libsym(lib_id, KLIB + lib + '.kicad_sym', name)

    def part(self, lib_id, ref, value, x, y, rot=0, mirror=None, unit=1, fp=None, f=None, **kw):
        self.ensure(lib_id)
        fields = dict(f or {})
        if fp: fields['Footprint'] = fp
        return self.add(lib_id, ref, value, x, y, rot=rot, mirror=mirror, unit=unit, fields=fields, **kw)

    def res(self, ref, value, x, y, h=False, fp=R0603, tol=None, part='Device:R', f=None, fx=2.0, fy=2.4, fl=False, **kw):
        f = dict(f or {})
        if tol:
            f['Tolerance'] = tol
        x, y = self.g(x), self.g(y)
        if h:
            p = self.part(part, ref, value, x, y, rot=90, fp=fp, f=f, **kw)
            p.fpos = {'Reference': (x, y - fy, 'center'), 'Value': (x, y + fy + 0.3, 'center')}
        else:
            p = self.part(part, ref, value, x, y, fp=fp, f=f, **kw)
            if fl:
                p.fpos = {'Reference': (x - fx, y - 1.3, 'right'), 'Value': (x - fx, y + 1.5, 'right')}
            else:
                p.fpos = {'Reference': (x + fx, y - 1.3), 'Value': (x + fx, y + 1.5)}
        return p

    def cap(self, ref, value, x, y, h=False, fp=C0603, **kw):
        return self.res(ref, value, x, y, h=h, fp=fp, part='Device:C', fx=2.8, fy=3.3, **kw)

    def led(self, ref, value, x, y, rot=90, **kw):
        """LED with its fields clear of the body; the KiCad LED graphic extends past the cathode pin, so callers wire the pins"""
        d = self.part('Device:LED', ref, value, x, y, rot=rot, fp=LED0603, **kw)
        if rot in (90, 270):
            d.fpos = {'Reference': (x + 3.0, y - 1.3), 'Value': (x + 3.0, y + 1.5)}
        else:
            d.fpos = {'Reference': (x, y - 4.4, 'center'), 'Value': (x, y + 4.6, 'center')}
        return d

    def dio(self, lib_id, ref, value, x, y, rot=0, fp=SOD323, **kw):
        p = self.part(lib_id, ref, value, x, y, rot=rot, fp=fp, **kw)
        if rot in (0, 180):
            p.fpos = {'Reference': (x, y - 2.6, 'center'), 'Value': (x, y + 3.0, 'center')}
        else:
            p.fpos = {'Reference': (x + 2.6, y - 1.3), 'Value': (x + 2.6, y + 1.5)}
        return p

    def fet(self, lib_id, ref, value, x, y, fp=SOT23, rot=0, **kw):
        p = self.part(lib_id, ref, value, x, y, fp=fp, rot=rot, **kw)
        p.fpos = {'Reference': (x + 5.6, y - 1.3), 'Value': (x + 5.6, y + 1.5)}
        return p

    def amp(self, lib_id, ref, value, x, y, unit, mirror=None, **kw):
        p = self.part(lib_id, ref, value, x, y, mirror=mirror, unit=unit, **kw)
        p.fpos = {'Reference': (x + 2.54, y - 7.0), 'Value': (x + 2.54, y + 7.4)}
        return p

    def ic(self, lib_id, ref, value, x, y, ry, fp=None, **kw):
        p = self.part(lib_id, ref, value, x, y, fp=fp, **kw)
        p.fpos = {'Reference': (x, y - ry, 'center'), 'Value': (x, y + ry, 'center')}
        return p

    def rail(self, name, x, y, rot=0):
        lib = {'FLAG': 'power:PWR_FLAG'}.get(name, 'dcload:' + name)
        self.ensure(lib)
        p = self.power(lib, x, y, rot=rot)
        PWRN[0] += 1
        p.ref = ('#FLG{n}%03d' if name == 'FLAG' else '#PWR{n}%03d') % PWRN[0]
        gnd = 'GND' in name
        off = 3.9 if gnd != (rot == 180) else -3.9
        if rot in (90, 270):
            p.fpos = {'Value': (x + (-5.8 if rot == 270 else 5.8) * (1 if gnd else -1), y, 'center')}
        else:
            p.fpos = {'Value': (x, y + off, 'center')}
        return p

    def tp(self, ref, name, x, y, left=False, **kw):
        p = self.part('Connector:TestPoint', ref, name, x, y, fp=TP, **kw)
        if left:
            p.fpos = {'Reference': (x - 1.6, y - 5.0, 'right'), 'Value': (x - 1.6, y - 2.8, 'right')}
        else:
            p.fpos = {'Reference': (x + 1.6, y - 5.0), 'Value': (x + 1.6, y - 2.8)}
        return p

    def hier(self, name, x, y, ang=180, shape='passive', color=None):
        self.label(name, x, y, angle=ang, kind='hier', shape=shape, color=color)

    def lab(self, name, x, y, ang=0, color=None):
        self.label(name, x, y, angle=ang, kind='label', color=color)

    def note(self, s, x, y, size=FS_NOTE, color=C_NOTE, **kw):
        self.text(s, x, y, size=size, color=color, **kw)

    def barrier(self, x, y1, y2, label=None):
        self.polyline([(x, y1), (x, y2)], width=0.7, dash=True, color=C_BAR)
        if label:
            self.text(label, x - 1.4, y2 - 2, size=FS_SUB, bold=True, angle=90, color=C_BAR)

    def stub(self, pt, name, side, kind='hier', shape='passive', length=7.62, color=None):
        ex = pt[0] - length if side == 'L' else pt[0] + length
        self.wire(pt, (ex, pt[1]), color=color)
        if kind == 'hier':
            self.hier(name, ex, pt[1], ang=180 if side == 'L' else 0, shape=shape, color=color)
        else:
            self.lab(name, ex, pt[1], ang=180 if side == 'L' else 0, color=color)
        return (ex, pt[1])

    def pullup(self, ref, name, rail, x, y, value='10k', color=None):
        r = self.res(ref, value, x, y)
        self.rail(rail, x, r.pin('1')[1])
        self.wire(r.pin('2'), (x, r.pin('2')[1] + 2.54))
        self.hier(name, x, r.pin('2')[1] + 2.54, ang=270, color=color)
        return r

    def rowcaps(self, x0, y, specs, rail, gnd, pitch=12):
        """decoupling row: rail on top, gnd below, each cap standing alone"""
        for i, (ref, val, fp) in enumerate(specs):
            c = self.cap(ref, val, x0 + i * pitch, y, fp=fp)
            self.rail(rail, x0 + i * pitch, top(c)[1]); self.rail(gnd, x0 + i * pitch, bot(c)[1])


lft = lambda p: p.pin('1') if p.pin('1')[0] < p.pin('2')[0] else p.pin('2')
rgt = lambda p: p.pin('2') if p.pin('1')[0] < p.pin('2')[0] else p.pin('1')
top = lambda p: p.pin('1') if p.pin('1')[1] < p.pin('2')[1] else p.pin('2')
bot = lambda p: p.pin('2') if p.pin('1')[1] < p.pin('2')[1] else p.pin('1')

ZENER = 'Diode:BZX84Cxx'
BAT54S, BAT54C, D1N = 'Diode:BAT54S', 'Diode:BAT54C', 'Device:D'
Q2N, QP, QPFET = 'Transistor_FET:2N7002', 'Transistor_FET:IRF540N', 'Transistor_FET:AO3401A'


# ======================================================================= USB-C input and the power tree
def usb_power():
    s = S('USB-C input and power tree', 'One USB-C port feeds three rails and the 5 V blower. Left of the barrier is USB ground (DGND); the analog stage floats on AGND = DUT minus.')
    # ------------------------------------------------------------ block A: USB-C
    s.begin_block('A   USB-C input: 5 V, data, current advertisement (CC)', FILL_D)
    j = s.ic('Connector:USB_C_Receptacle_USB2.0_16P', 'J1', 'USB-C 16P', 50, 78, 27, fp='Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12',
             f={'MPN': 'HRO TYPE-C-31-M-12 (16 pin, USB 2.0)', 'LCSC': 'C165948'})
    j.fpos = {'Reference': (50, 47.5, 'center'), 'Value': (50, 50.5, 'center')}
    vb = j.pin('A4')
    s.wire(vb, (84, vb[1]), color=C_PWR); s.rail('VBUS', 84, vb[1]); s.rail('FLAG', 72, vb[1])
    cc1, cc2 = j.pin('A5'), j.pin('B5')
    s.wire(cc1, (124, cc1[1])); s.hier('CC1_SENSE', 124, cc1[1], ang=0, shape='output')
    s.wire(cc2, (96, cc2[1])); s.hier('CC2_SENSE', 96, cc2[1], ang=0, shape='output')
    r1 = s.res('R1', '5.1k', 114, cc1[1] + 3.81, tol='1%'); s.rail('DGND', 114, bot(r1)[1])
    r2 = s.res('R2', '5.1k', 86, cc2[1] + 3.81, tol='1%'); s.rail('DGND', 86, bot(r2)[1])
    dp1, dp2, dm1, dm2 = j.pin('A6'), j.pin('B6'), j.pin('A7'), j.pin('B7')
    s.wire(dp1, (70, dp1[1]), (70, dp2[1]), dp2, color=C_USB); s.wire(dm1, (72, dm1[1]), (72, dm2[1]), dm2, color=C_USB)
    esd = s.part('Power_Protection:USBLC6-2SC6', 'D1', 'USBLC6-2SC6', 96, 106, f={'LCSC': 'C5261088'})
    esd.fpos = {'Reference': (103, 100), 'Value': (103, 103)}
    s.wire((70, dp2[1]), (70, 110), (86, 110), (86, esd.pin('3')[1]), esd.pin('3'), color=C_USB)
    s.wire((72, dm2[1]), (72, esd.pin('1')[1]), esd.pin('1'), color=C_USB)
    s.wire(esd.pin('6'), (112, esd.pin('6')[1]), color=C_USB); s.hier('USB_DM', 112, esd.pin('6')[1], ang=0, shape='bidirectional', color=C_USB)
    s.wire(esd.pin('4'), (112, esd.pin('4')[1]), color=C_USB); s.hier('USB_DP', 112, esd.pin('4')[1], ang=0, shape='bidirectional', color=C_USB)
    s.rail('VBUS', esd.pin('5')[0], esd.pin('5')[1]); s.rail('DGND', esd.pin('2')[0], esd.pin('2')[1])
    s.nc(*j.pin('A8')); s.nc(*j.pin('B8'))
    g, sh = j.pin('A1'), j.pin('SH')
    s.wire(g, (g[0], 112), (62, 112)); s.rail('DGND', g[0], 112); s.rail('FLAG', 62, 112)
    s.wire(sh, (sh[0], 112)); s.rail('DGND', sh[0], 112)
    s.note('CC1 / CC2 5.1k pull-downs = USB-C sink. The MCU reads\n'
           'the CC voltage to learn the source limit: 0.4 V = 500 mA\n'
           '(legacy source), 0.9 V = 1.5 A, 1.7 V = 3 A. The whole box\n'
           'draws about 0.45 A with the blower at full speed.\n'
           'Shield to DGND: a metal enclosure is on the USB side;\n'
           'DUT terminals, heatsink hardware and the NTC lug must\n'
           'not touch it.', 24, 152)
    s.end_block()
    # ------------------------------------------------------------ block D: star point and isolation
    s.begin_block('D   Ground star point and the isolation barrier rating', FILL_A)
    nt = s.part('Device:NetTie_2', 'NT1', 'STAR', 60, 190, fp='NetTie:NetTie-2_SMD_Pad2.0mm')
    nt.fpos = {'Reference': (60, 186.2, 'center'), 'Value': (60, 193.8, 'center')}
    s.wire(nt.pin('1'), (50, 190), (50, 196)); s.rail('AGND', 50, 196)
    s.wire(nt.pin('2'), (70, 190), (70, 196)); s.rail('PGND', 70, 196); s.rail('FLAG', 76, 190)
    s.wire((70, 190), (76, 190))
    s.note('AGND (analog reference) meets PGND (DUT minus, source\n'
           'resistors) ONLY at NT1. Place NT1 at the centre of the four\n'
           'Rs bottom pads: 1 mR between an Rs and NT1 is 10 mV at 10 A\n'
           '(4 % of full scale).\n\n'
           'Barrier: DGND side to AGND / PGND side. Rated 150 V DC\n'
           'working (IEC 60664-1 functional, PD2, material group IIIb:\n'
           '1.6 mm creepage; IPC-2221B B2: 0.7 mm). Board rule 4 mm,\n'
           'no copper crosses on any layer. CA-IS3761 (5 kVrms, 8 mm) and\n'
           'the 1.5 kVDC DC-DC exceed it by far. Float the load on a DUT\n'
           'referenced within 150 V of earth; not for mains work.', 24, 250)
    s.end_block()
    # ------------------------------------------------------------ block B: power tree
    s.begin_block('B   Power tree: VBUS 5 V trunk, two branches, three rails', FILL_D)
    T = 164
    s.rail('VBUS', T, 46); s.wire((T, 46), (T, 62), color=C_PWR)
    # ---- branch 1: 3.3 V logic
    y = 62
    s.wire((T, y), (184.38, y), color=C_PWR)
    c = s.cap('C1', '1uF', 172, y + 6); s.wire((172, y), top(c)); s.rail('DGND', 172, bot(c)[1])
    u = s.ic('Regulator_Linear:AP2112K-3.3', 'U1', 'AP2112K-3.3', 192, y + 2.54, 10, f={'LCSC': 'C23380830'}); u.fpos = {'Reference': (192, y - 9.5, 'center'), 'Value': (192, y - 6.5, 'center')}
    vin, en, gnd, vout = u.pin('1'), u.pin('3'), u.pin('2'), u.pin('5')
    s.wire(en, (180, en[1]), (180, y))
    s.rail('DGND', gnd[0], gnd[1]); s.nc(*u.pin('4'))
    s.wire(vout, (244, y), color=C_PWR); s.rail('+3V3', 244, y)
    c = s.cap('C2', '1uF', 210, y + 6); s.wire((210, y), top(c)); s.rail('DGND', 210, bot(c)[1])
    r = s.res('R3', '1k', 228, y + 6); s.wire((228, y), top(r))
    d = s.led('D2', 'LED green', 228, y + 16, f={'MPN': 'KT-0603G', 'LCSC': 'C12624'}); s.wire(bot(r), d.pin('2')); s.wire(d.pin('1'), (228, y + 23)); s.rail('DGND', 228, y + 23)
    s.note('+3V3: MCU, isolator side 1, pull-ups, LED. 60 mA.', 170, 94)
    # ---- branch 2: isolated analog supply
    y = 108
    ps = s.ic('dcload:DCDC_ISO_1W', 'PS1', 'B0512S-1W', 200, y + 5.08, 15, f={'MPN': 'DEXU B0512S-1W (LCSC C5244116, 1.5 kV); alt Mornsun B0512S-1WR3 (C5358214, 3 kV)', 'LCSC': 'C5244116'})
    ps.fpos = {'Reference': (190, y + 17.6, 'center'), 'Value': (190, y + 20.6, 'center')}
    vip, vin_, vop, von = ps.pin('1'), ps.pin('2'), ps.pin('4'), ps.pin('3')
    s.wire((158, y), vip, color=C_PWR); s.wire((158, y), (158, y - 6), color=C_PWR); s.rail('VBUS_LK', 158, y - 6)
    c = s.cap('C6', '10uF', 172, y + 6, fp=C0805); s.wire((172, y), top(c)); s.rail('DGND_LK', 172, bot(c)[1])
    s.wire(vin_, (178, vin_[1]), (178, vin_[1] + 8)); s.rail('DGND_LK', 178, vin_[1] + 8)
    s.wire(vop, (242.19, y), color=C_PWR)
    c = s.cap('C7', '10uF 25V', 232, y + 6, fp=C0805); s.wire((232, y), top(c)); s.rail('AGND', 232, bot(c)[1])
    rf = s.res('R12', '4.7R', 246, y, h=True, fp=R1206); s.wire(rgt(rf), (294, y), color=C_PWR)
    s.rail('FLAG', 256, y); s.rail('+12V_ISO', 294, y)
    for i, (ref, val, fp) in enumerate([('C8', '22uF 25V', C1206), ('C9', '100nF', C0603)]):
        x = 264 + i * 16
        c = s.cap(ref, val, x, y + 6, fp=fp); s.wire((x, y), top(c)); s.rail('AGND', x, bot(c)[1])
    s.wire(von, (von[0], von[1] + 8)); s.rail('AGND', von[0], von[1] + 8)
    y5 = y + 34
    s.wire((222, y), (222, y5), (226, y5), color=C_PWR)
    c = s.cap('C10', '1uF 25V', 226, y5 + 6); s.wire((226, y5), top(c)); s.rail('AGND', 226, bot(c)[1])
    u = s.ic('Regulator_Linear:L78L05_SOT89', 'U3', 'L78L05', 248, y5, 10, f={'MPN': 'L78L05ABUTR (SOT-89)', 'LCSC': 'C42738'})
    u.fpos = {'Reference': (248, y5 - 9.5, 'center'), 'Value': (248, y5 - 6.5, 'center')}
    vi, vo, g = u.pin('3'), u.pin('1'), u.pin('2')
    s.wire((226, y5), vi, color=C_PWR)
    s.wire(vo, (294, y5), color=C_PWR); s.rail('+5V_ISO', 294, y5)
    for i, (ref, val) in enumerate([('C11', '1uF'), ('C12', '100nF')]):
        x = 264 + i * 16
        c = s.cap(ref, val, x, y5 + 6); s.wire((x, y5), top(c)); s.rail('AGND', x, bot(c)[1])
    s.rail('AGND', g[0], g[1])
    s.barrier(200, y - 10, y5 + 22)
    s.text('BARRIER', 198.6, y5 + 20, size=FS_SUB, bold=True, angle=90, color=C_BAR)
    s.note('+12V_ISO: op-amps, comparators, pull-ups, 30 mA. PS1 is unregulated: 12 V\n'
           'at full load, up to 14 V here; all parts on the rail are rated 16 V or more.\n'
           'R12 / C8 filter the 100 kHz ripple (fc 1.5 kHz). +5V_ISO (78L05, 4 %): DAC,\n'
           'ADC, isolator side 2 and every threshold divider, so OTP, dropout, NTC-open\n'
           'and OVP thresholds do not depend on its absolute value; the DAC and ADC\n'
           'carry their own references. VBUS_LK / DGND_LK: VBUS / DGND after the\n'
           'J10-J11 cable. VERIFY the SIP-4 pin order of the module you buy.', 170, 182)
    s.end_block()
    # ------------------------------------------------------------ block C: fan switch
    s.begin_block('C   Blower switch and connector', FILL_D)
    X0, Y0 = 358, 70
    qp = s.fet(QPFET, 'Q1', 'AO3401A', X0, Y0 + 20.46, rot=270, f={'LCSC': 'C15127'})
    qp.fpos = {'Reference': (X0 + 7, Y0 + 12.5), 'Value': (X0 + 7, Y0 + 15.3)}
    src, drn, gate = qp.pin('2'), qp.pin('3'), qp.pin('1')
    jf = s.part('Connector_Generic:Conn_01x04', 'J2', 'FAN 4-pin', X0 + 26, Y0 + 23, fp='Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical',
                f={'Note': '1 GND  2 +5V switched  3 TACH  4 PWM (PC fan pinout)', 'MPN': 'JST B4B-XH-A(LF)(SN)', 'LCSC': 'C144395'})
    jf.fpos = {'Reference': (X0 + 26, Y0 + 15, 'center'), 'Value': (X0 + 26, Y0 + 32, 'center')}
    p1, p2, p3, p4 = jf.pin('1'), jf.pin('2'), jf.pin('3'), jf.pin('4')
    s.wire(p1, (X0 + 17, p1[1])); s.rail('DGND', X0 + 17, p1[1], rot=270)
    s.wire(drn, p2, color=C_PWR); s.rail('VBUS', X0 - 16, p2[1]); s.wire((X0 - 16, p2[1]), src, color=C_PWR)
    rpu = s.res('R7', '10k', X0, Y0 - 10.81); s.rail('VBUS', X0, top(rpu)[1])
    c3 = s.cap('C3', '10uF', X0 + 33, Y0 - 2, fp=C0805, fl=True); s.rail('VBUS', X0 + 33, top(c3)[1]); s.rail('DGND', X0 + 33, bot(c3)[1])
    qn = s.fet(Q2N, 'Q2', '2N7002', X0 - 20, Y0 + 1, f={'LCSC': 'C8545'})
    s.wire(gate, (X0, Y0 - 7), (qn.pin('3')[0], Y0 - 7), qn.pin('3'))
    s.rail('DGND', qn.pin('2')[0], qn.pin('2')[1])
    s.wire(qn.pin('1'), (X0 - 36, qn.pin('1')[1])); s.hier('FAN_EN', X0 - 36, qn.pin('1')[1], ang=180)
    rpd2 = s.res('R8', '100k', X0 - 30, Y0 + 7); s.wire((X0 - 30, qn.pin('1')[1]), top(rpd2)); s.rail('DGND', X0 - 30, bot(rpd2)[1])
    s.wire(p3, (X0 + 12, p3[1]), (X0 + 12, Y0 + 38), (X0 + 6, Y0 + 38))
    rpu2 = s.res('R9', '10k', X0 + 6, Y0 + 34.19, fl=True); s.rail('+3V3', X0 + 6, top(rpu2)[1])
    rs = s.res('R10', '1k', X0 - 4, Y0 + 38, h=True); s.wire((X0 + 6, Y0 + 38), rgt(rs)); s.wire(lft(rs), (X0 - 18, Y0 + 38)); s.hier('FAN_TACH', X0 - 18, Y0 + 38, ang=180, shape='output')
    s.wire(p4, (X0 + 16, p4[1]), (X0 + 16, Y0 + 60))
    qpwm = s.fet(Q2N, 'Q3', '2N7002', X0 + 13.46, Y0 + 65.08, f={'LCSC': 'C8545'})
    s.rail('DGND', qpwm.pin('2')[0], qpwm.pin('2')[1])
    s.wire(qpwm.pin('1'), (X0 - 18, qpwm.pin('1')[1])); s.hier('FAN_PWM', X0 - 18, qpwm.pin('1')[1], ang=180)
    rpu3 = s.res('R11', '10k DNP', X0 + 6, Y0 + 56.19, dnp=True, fl=True); s.wire((X0 + 16, Y0 + 60), bot(rpu3)); s.rail('VBUS', X0 + 6, top(rpu3)[1])
    s.note('J2 = PC fan pinout on 5 V: 1 GND, 2 +5 V\n'
           'switched by Q1, 3 tach (open collector,\n'
           'pulled to 3.3 V), 4 PWM 25 kHz. A 5 V 5015\n'
           'blower (2 wires) uses pins 1 and 2 and is\n'
           'on/off through FAN_EN; a 4-wire fan gets\n'
           'PWM from Q3 (open-drain, firmware inverts\n'
           'the duty). R11 only for fans without a PWM\n'
           'pull-up. C3 is the blower bulk capacitor:\n'
           'keep the motor noise on its own VBUS trace.', X0 - 40, Y0 + 100)
    s.end_block()
    return s


# ======================================================================= MCU
def mcu():
    s = S('MCU: STM32G0B1RBT6 (LQFP64, the G0B1 JLC stocks), USB device, SPI to the isolated stage, I2C to the OLED',
          'Crystal-less: USB SOF trims the 48 MHz HSI. DFU over USB is in ROM (hold BOOT, tap RESET). Everything here is on DGND.')
    s.begin_block('A   Microcontroller', FILL_D)
    X, Y = 110, 120
    u = s.ic('MCU_ST_STM32G0:STM32G0B1RBTx', 'U4', 'STM32G0B1RBT6', X, Y, 54, f={'MPN': 'STM32G0B1RBT6', 'LCSC': 'C5143679'}); u.fpos = {'Reference': (X - 22, Y - 58), 'Value': (X, Y + 57, 'center')}
    H, L = 'hier', 'label'
    # name -> (label, kind, shape, colour)
    plan = {
        'PA0': ('CC1_SENSE', H, 'input', None), 'PA1': ('CC2_SENSE', H, 'input', None),
        'PA4': ('~{CS_DAC}', H, 'output', C_SPI), 'PA5': ('SPI1_SCK', H, 'output', C_SPI), 'PA6': ('SPI1_MISO', H, 'input', C_SPI), 'PA7': ('SPI1_MOSI', H, 'output', C_SPI),
        'PB0': ('~{CS_ADC}', H, 'output', C_SPI), 'PB1': ('LOAD_OFF', H, 'output', C_PROT),
        'PA8': ('LED_ON', H, 'output', None), 'PC7': ('LED_FAULT', H, 'output', None),
        'PC6': ('LED_STATUS', L, None, None), 'PA9/UCPD1_DBCC1': ('UART_TX', L, None, None), 'PA10/UCPD1_DBCC2': ('UART_RX', L, None, None),
        'PA9/PA11': ('USB_DM', H, 'bidirectional', C_USB), 'PA10/PA12': ('USB_DP', H, 'bidirectional', C_USB),
        'PA13': ('SWDIO', L, None, None), 'PA14': ('SWCLK_BOOT0', L, None, None),
        'PB3': ('ENC_SW', H, 'input', None), 'PB4': ('ENC_A', H, 'input', None), 'PB5': ('ENC_B', H, 'input', None),
        'PB6': ('I2C_SCL', H, 'bidirectional', None), 'PB7': ('I2C_SDA', H, 'bidirectional', None), 'PB8': ('FAN_TACH', H, 'input', None), 'PB9': ('FAN_PWM', H, 'output', None),
        'PD0': ('BTN_ON', H, 'input', None), 'PD1': ('BTN_MODE', H, 'input', None), 'PD2': ('BTN_MENU', H, 'input', None),
        'PD3': ('FAN_EN', H, 'output', None), 'PF2': ('NRST', L, None, None),
    }
    names = {}
    for sub in find(u.sym, 'symbol'):
        for p in find(sub, 'pin'):
            names[str(find1(p, 'number')[1])] = str(find1(p, 'name')[1])
    for n in sorted(names, key=int):
        nm = names[n]
        if nm in ('VBAT', 'VREF+', 'VDD', 'VSS'):
            continue
        p = u.pin(n)
        if nm in plan:
            name, kind, shape, col = plan[nm]
            side = 'L' if p[0] < X else 'R'
            s.stub(p, name, side, kind=kind, shape=shape or 'passive', color=col, length=7.62 if kind == H else 17.78)
        else:
            s.nc(*p)
    vbat, vref, vdd, vss = u.pin('6'), u.pin('7'), u.pin('8'), u.pin('9')
    s.wire(vbat, (vbat[0], vbat[1] - 5), (vdd[0], vbat[1] - 5), vdd, color=C_PWR); s.rail('+3V3', vdd[0], vbat[1] - 5)
    s.wire(vref, (vref[0] - 8, vref[1]), (vref[0] - 8, vref[1] - 8), color=C_PWR); s.rail('+3V3', vref[0] - 8, vref[1] - 8)
    s.rail('DGND', vss[0], vss[1])
    s.note('Pin plan (STM32G0B1RBT6, LQFP64; the CBT6 of Rev D is not stocked at JLC, same die, same pin names)\n'
           'SPI1   PA5 SCK, PA6 MISO, PA7 MOSI, PA4 /CS DAC, PB0 /CS ADC, PB1 LOAD_OFF (isolator)\n'
           'I2C1   PB6 SCL, PB7 SDA: the OLED module (page 4). No display driver, no level shifter.\n'
           'TIM3   PB4 / PB5 encoder, PB3 push.  TIM17 PB9 fan PWM, TIM16 PB8 tach, PD3 FAN_EN\n'
           'ADC    PA0 / PA1 = CC1 / CC2.  USB PA11 DM, PA12 DP, crystal-less (CRS)\n'
           'USART1 PA9 / PA10 debug.  PD0 ON/OFF, PD1 MODE, PD2 MENU.  PC6 heartbeat LED, PA8 ON LED, PC7 FAULT LED\n'
           'Why not the STM32F103C8T6 ($1.50 at JLC): no USB DFU in its ROM (USART only), needs a crystal, no\n'
           'CRS; the G0B1 ROM DFU is what removes the second USB port. Swap it in if you have an ST-Link and F103s.\n'
           'Spare: PA2, PA3, PA15, PB2, PB10-PB15, PC0-PC5, PC8-PC15, PD4-PD9, PF0, PF1 (NC).', 48, 236)
    s.end_block()
    # ------------------------------------------------------------ support blocks
    bx = 262
    s.begin_block('B   Decoupling', FILL_D)
    s.rowcaps(bx + 10, 58, [('C13', '4.7uF', C0805), ('C14', '100nF', C0603), ('C15', '100nF', C0603), ('C16', '100nF', C0603), ('C17', '100nF', C0603), ('C18', '1uF', C0603)], '+3V3', 'DGND', pitch=16)
    s.note('All X7R. One 100 nF per VDD pin, 1 uF + 100 nF at VREF+ (C17, C18).\nPlace within 2 mm of the pins.', bx + 6, 80)
    s.end_block()
    s.begin_block('C   Reset, BOOT0 (DFU), SWD', FILL_D)
    y0 = 104
    sw = s.part('Switch:SW_Push', 'SW1', 'RESET', bx + 28, y0, fp='Button_Switch_THT:SW_PUSH_6mm', f={'MPN': 'KH-6X6X5H-TJ', 'LCSC': 'C2837515'}); sw.fpos = {'Reference': (bx + 28, y0 - 4.5, 'center'), 'Value': (bx + 28, y0 + 4.5, 'center')}
    s.wire(sw.pin('1'), (bx + 12, y0)); s.lab('NRST', bx + 12, y0, ang=180); s.wire(sw.pin('2'), (bx + 42, y0)); s.rail('DGND', bx + 42, y0)
    c = s.cap('C19', '100nF', bx + 16, y0 + 7); s.wire((bx + 16, y0), top(c)); s.rail('DGND', bx + 16, bot(c)[1])
    sw = s.part('Switch:SW_Push', 'SW2', 'BOOT', bx + 28, y0 + 24, fp='Button_Switch_THT:SW_PUSH_6mm', f={'MPN': 'KH-6X6X5H-TJ', 'LCSC': 'C2837515'}); sw.fpos = {'Reference': (bx + 28, y0 + 19.5, 'center'), 'Value': (bx + 28, y0 + 28.5, 'center')}
    r = s.res('R13', '1k', bx + 44, y0 + 24, h=True); s.wire(sw.pin('2'), lft(r)); s.wire(rgt(r), (bx + 58, y0 + 24)); s.rail('+3V3', bx + 58, y0 + 24)
    s.wire(sw.pin('1'), (bx + 12, y0 + 24)); s.lab('SWCLK_BOOT0', bx + 12, y0 + 24, ang=180)
    jh = s.part('Connector_Generic:Conn_01x05', 'J3', 'SWD', bx + 110, y0 + 12, fp=PH % 5, f={'Note': '1 +3V3  2 SWDIO  3 SWCLK  4 NRST  5 GND', 'MPN': 'B-2100S05P-A110', 'LCSC': 'C124379'})
    jh.fpos = {'Reference': (bx + 110, y0 + 3, 'center'), 'Value': (bx + 110, y0 + 21.5, 'center')}
    for n, name in (('2', 'SWDIO'), ('3', 'SWCLK_BOOT0'), ('4', 'NRST')):
        p = jh.pin(n); s.wire(p, (p[0] - 8, p[1])); s.lab(name, p[0] - 8, p[1], ang=180)
    p = jh.pin('1'); s.wire(p, (p[0] - 4, p[1]), (p[0] - 4, p[1] - 6)); s.rail('+3V3', p[0] - 4, p[1] - 6)
    p = jh.pin('5'); s.wire(p, (p[0] - 4, p[1]), (p[0] - 4, p[1] + 5)); s.rail('DGND', p[0] - 4, p[1] + 5)
    s.note('BOOT0 shares PA14 (SWCLK) on the STM32G0. Hold BOOT, tap RESET: the ROM bootloader\n'
           'enumerates as USB DFU. Once, with STM32CubeProgrammer, clear option bit nBOOT_SEL so\n'
           'the pin is honoured (the factory default ignores it).', bx + 6, y0 + 50)
    s.end_block()
    s.begin_block('D   Debug UART and heartbeat LED', FILL_D)
    y0 = 188
    r = s.res('R16', '1k', bx + 24, y0, h=True); s.wire(lft(r), (bx + 12, y0)); s.lab('LED_STATUS', bx + 12, y0, ang=180)
    d = s.led('D4', 'LED blue', bx + 38, y0, rot=180, f={'MPN': 'KT-0603B', 'LCSC': 'C2288'})
    s.wire(rgt(r), d.pin('2')); s.wire(d.pin('1'), (bx + 48, y0)); s.rail('DGND', bx + 48, y0)
    ju = s.part('Connector_Generic:Conn_01x03', 'J4', 'UART 3V3', bx + 110, y0 + 2.54, fp=PH % 3, f={'Note': '1 GND  2 TX  3 RX', 'MPN': 'B-2100S03P-A110', 'LCSC': 'C124376'})
    ju.fpos = {'Reference': (bx + 110, y0 - 4, 'center'), 'Value': (bx + 110, y0 + 9.5, 'center')}
    p = ju.pin('1'); s.wire(p, (p[0] - 4, p[1]), (p[0] - 4, p[1] - 5)); s.rail('DGND', p[0] - 4, p[1] - 5, rot=180)
    for n, name in (('2', 'UART_TX'), ('3', 'UART_RX')):
        p = ju.pin(n); s.wire(p, (p[0] - 8, p[1])); s.lab(name, p[0] - 8, p[1], ang=180)
    s.end_block()
    return s


# ======================================================================= front panel UI
def ui():
    s = S('Front panel: OLED module, encoder, 3 buttons, 2 status LEDs',
          'The readout is an off-the-shelf I2C OLED module on a 4-wire lead. Everything on this sheet is on DGND (USB side).')
    s.begin_block('A   OLED module header: 1.3" SH1106 or 0.96" SSD1306, I2C address 0x3C, 3.3 V', FILL_D)
    bx, y0 = 40, 60
    ji = s.part('Connector_Generic:Conn_01x04', 'J5', 'I2C OLED', bx + 110, y0 + 2.54, fp=PH % 4,
                f={'Note': '1 GND  2 +3V3  3 SCL  4 SDA. CHECK the module: some are VCC GND SCL SDA', 'MPN': 'B-2100S04P-A110 (the OLED module itself comes from AliExpress)', 'LCSC': 'C124378'})
    ji.fpos = {'Reference': (bx + 110, y0 - 4.5, 'center'), 'Value': (bx + 110, y0 + 11, 'center')}
    p = ji.pin('1'); s.wire(p, (p[0] - 4, p[1]), (p[0] - 4, p[1] - 5)); s.rail('DGND', p[0] - 4, p[1] - 5, rot=180)
    p = ji.pin('2'); s.wire(p, (p[0] - 14, p[1]), (p[0] - 14, p[1] - 8)); s.rail('+3V3', p[0] - 14, p[1] - 8)
    for n, name in (('3', 'I2C_SCL'), ('4', 'I2C_SDA')):
        p = ji.pin(n); s.wire(p, (p[0] - 20, p[1])); s.hier(name, p[0] - 20, p[1], ang=180, shape='bidirectional')
    for i, name in enumerate(('I2C_SCL', 'I2C_SDA')):
        r = s.res('R%d' % (14 + i), '4.7k', bx + 20 + i * 16, y0 - 2); s.rail('+3V3', bx + 20 + i * 16, top(r)[1])
        s.wire(bot(r), (bx + 20 + i * 16, bot(r)[1] + 2.54)); s.lab(name, bx + 20 + i * 16, bot(r)[1] + 2.54, ang=270)
    s.note('The module shows V, A, W, the set value, mode and status; menus for limits, fan and calibration.\n'
           'Short lead (under 15 cm) to the bezel. 1.3" SH1106 modules are the readable choice at arm\'s length;\n'
           'the 0.96" SSD1306 is the same pinout and protocol family. R14 / R15 pull up the bus here because\n'
           'the module may or may not carry its own.', bx - 16, y0 + 30)
    s.end_block()
    s.begin_block('B   Encoder and buttons (MCU pull-ups on the buttons, RC on the encoder)', FILL_D)
    ye = 134
    e = s.part('Device:RotaryEncoder_Switch', 'ENC1', 'PEC11R-4215F-S0024', 50, ye, fp='Rotary_Encoder:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm',
               f={'MPN': 'Bourns PEC11R-4215F-S0024 (24 detents, push switch, 15 mm flatted shaft; any EC11 with switch fits)', 'LCSC': 'C143790'})
    e.fpos = {'Reference': (50, ye - 7.5, 'center'), 'Value': (50, ye + 8.0, 'center')}
    s.stub(e.pin('A'), 'ENC_A', 'L', shape='output', length=16)
    s.stub(e.pin('B'), 'ENC_B', 'L', shape='output', length=16)
    s.rail('DGND', e.pin('C')[0] - 3, e.pin('C')[1], rot=270); s.wire(e.pin('C'), (e.pin('C')[0] - 3, e.pin('C')[1]))
    s.stub(e.pin('S1'), 'ENC_SW', 'R', shape='output'); s.rail('DGND', e.pin('S2')[0] + 3, e.pin('S2')[1], rot=90); s.wire(e.pin('S2'), (e.pin('S2')[0] + 3, e.pin('S2')[1]))
    for i, name in enumerate(('ENC_A', 'ENC_B')):
        x = 120 + i * 26
        r = s.res('R%d' % (19 + i), '10k', x, ye - 2); s.rail('+3V3', x, top(r)[1]); s.wire(bot(r), (x, ye + 6)); s.hier(name, x, ye + 6, ang=270, shape='output')
        c = s.cap('C%d' % (24 + i), '10nF', x + 16, ye + 10); s.wire((x, ye + 6), (x + 16, ye + 6), top(c)); s.rail('DGND', x + 16, bot(c)[1])
    for i, (ref, name, lab) in enumerate([('SW3', 'ON/OFF', 'BTN_ON'), ('SW4', 'MODE', 'BTN_MODE'), ('SW5', 'MENU', 'BTN_MENU')]):
        x = 50 + i * 60
        sw = s.part('Switch:SW_Push', ref, name, x, ye + 22, fp='Button_Switch_THT:SW_PUSH_6mm', f={'MPN': 'KH-6X6X5H-TJ 6 x 6 mm tact switch', 'LCSC': 'C2837515'})
        sw.fpos = {'Reference': (x, ye + 17.5, 'center'), 'Value': (x, ye + 26.5, 'center')}
        s.stub(sw.pin('1'), lab, 'L', shape='output', length=10); s.rail('DGND', sw.pin('2')[0] + 3, sw.pin('2')[1], rot=90); s.wire(sw.pin('2'), (sw.pin('2')[0] + 3, sw.pin('2')[1]))
    s.note('ON/OFF toggles the sink. MODE cycles CC/CV/CR/CP/BATT. MENU: limits, fan, cal. Push = digit select.', 24, ye + 34)
    s.end_block()
    s.begin_block('C   Status LEDs: ON (green) while the load sinks, FAULT (red) for OTP / OVP / NTC-open / OFF', FILL_D)
    for i, (ref, rref, name, lab, code) in enumerate([('D5', 'R17', 'LED green', 'LED_ON', 'C12624'), ('D6', 'R18', 'LED red', 'LED_FAULT', 'C2286')]):
        y = 196 + i * 12
        s.hier(lab, 40, y, shape='input')
        r = s.res(rref, '1k', 54, y, h=True); s.wire((40, y), lft(r))
        d = s.led(ref, name, 68, y, rot=180, f={'MPN': 'KT-0603' + name[-1].upper(), 'LCSC': code})
        s.wire(rgt(r), d.pin('2')); s.wire(d.pin('1'), (78, y)); s.rail('DGND', 78, y)
    s.note('Panel LEDs beside the display: ON = the load is sinking, FAULT = a hardware trip or the firmware latch.\n'
           'The heartbeat LED is on the MCU sheet. The mode (CC/CV/CR/CP/BATT) and REMOTE are shown on the OLED.', 24, 228)
    s.end_block()
    return s


# ======================================================================= isolated interface
def iso_interface():
    s = S('Isolated interface: digital isolator, set-point DAC, readback ADC',
          'SPI crosses the barrier. The DAC and ADC carry their own references, so no precision reference or trimmer is needed.')
    s.begin_block('A   Digital isolator', FILL_N)
    u = s.ic('Isolator:ISO7761DW', 'U8', 'CA-IS3761HW', 82, 92, 25, f={'MPN': 'Chipanalog CA-IS3761HW, 5 kVrms, default-HIGH outputs (pin-compatible: TI ISO7761DW, C2871529)', 'LCSC': 'C528656'})
    left = [('2', 'SPI1_SCK_LK', 'input', C_SPI), ('3', 'SPI1_MOSI_LK', 'input', C_SPI), ('4', '~{CS_DAC}_LK', 'input', C_SPI),
            ('5', '~{CS_ADC}_LK', 'input', C_SPI), ('6', 'LOAD_OFF_LK', 'input', C_PROT), ('7', 'SPI1_MISO_LK', 'output', C_SPI)]
    for pn, name, sh, col in left:
        s.stub(u.pin(pn), name, 'L', shape=sh, length=12, color=col)
    right = [('15', 'SCK_ISO', C_SPI), ('14', 'MOSI_ISO', C_SPI), ('13', '~{CS_DAC}_ISO', C_SPI), ('12', '~{CS_ADC}_ISO', C_SPI),
             ('11', 'LOAD_OFF_ISO', C_PROT), ('10', 'MISO_ISO', C_SPI)]
    for pn, name, col in right:
        s.stub(u.pin(pn), name, 'R', kind='label', length=10, color=col)
    v1, g1, v2, g2 = u.pin('1'), u.pin('8'), u.pin('16'), u.pin('9')
    s.wire(v1, (v1[0], v1[1] - 5), color=C_PWR); s.rail('+3V3_LK', v1[0], v1[1] - 5); s.rail('DGND_LK', g1[0], g1[1])
    s.wire(v2, (v2[0], v2[1] - 5), color=C_PWR); s.rail('+5V_ISO', v2[0], v2[1] - 5); s.rail('AGND', g2[0], g2[1])
    c = s.cap('C27', '100nF', 58, 50); s.rail('+3V3_LK', 58, top(c)[1]); s.rail('DGND_LK', 58, bot(c)[1])
    c = s.cap('C28', '100nF', 108, 50); s.rail('+5V_ISO', 108, top(c)[1]); s.rail('AGND', 108, bot(c)[1])
    s.barrier(82, 36, 124)
    s.text('ISOLATION BARRIER', 80.6, 62, size=FS_SUB, bold=True, angle=90, color=C_BAR)
    s.wire((128, 108), (142, 108)); s.hier('LOAD_OFF_ISO', 142, 108, ang=0, shape='output', color=C_PROT); s.lab('LOAD_OFF_ISO', 128, 108, ang=180, color=C_PROT)
    for i, name in enumerate(('~{CS_DAC}_LK', '~{CS_ADC}_LK', 'LOAD_OFF_LK')):
        s.pullup('R%d' % (21 + i), name, '+3V3_LK', 24 + i * 12, 48, color=C_SPI if i < 2 else C_PROT)
    s.note('Side 1 = USB side after the J10/J11 cable (3.3 V_LK), side 2 = analog\n'
           '(5 V). Five channels cross, MISO comes back. CA-IS3761HW (the H suffix) and\n'
           'the TI ISO7761 are pin-compatible; both have outputs that default HIGH\n'
           'when side 1 is unpowered or an input floats: chip selects stay\n'
           'de-asserted and LOAD_OFF_ISO is asserted, so the load is OFF until\n'
           'firmware says otherwise. R21-R23 (on this board) give the same guarantee\n'
           'with the MCU in reset or the cable unplugged. 11 ns delay: SPI <= 2 MHz.', 24, 146)
    s.end_block()
    # ------------------------------------------------------------ DAC
    s.begin_block('B   Set-point DAC: A = current ceiling, B = CV voltage', FILL_A)
    d = s.ic('Analog_DAC:MCP4822', 'U9', 'MCP4822', 256, 62, 20, fp='Package_SO:SOIC-8_3.9x4.9mm_P1.27mm', f={'MPN': 'MCP4822-E/SN', 'LCSC': 'C16040'})
    for pn, name in (('3', 'SCK_ISO'), ('4', 'MOSI_ISO'), ('2', '~{CS_DAC}_ISO')):
        s.stub(d.pin(pn), name, 'L', kind='label', length=8, color=C_SPI)
    ld = d.pin('5'); s.wire(ld, (ld[0] - 22, ld[1])); s.rail('AGND', ld[0] - 22, ld[1], rot=270)
    s.stub(d.pin('8'), 'LOAD_CTRL', 'R', shape='output', length=12, color=C_SET)
    s.stub(d.pin('6'), 'CV_SET', 'R', shape='output', length=12, color=C_SET)
    vdd, vss = d.pin('1'), d.pin('7')
    s.wire(vdd, (vdd[0], vdd[1] - 4), color=C_PWR); s.rail('+5V_ISO', vdd[0], vdd[1] - 4); s.rail('AGND', vss[0], vss[1])
    c = s.cap('C29', '100nF', 290, 46); s.rail('+5V_ISO', 290, top(c)[1]); s.rail('AGND', 290, bot(c)[1])
    s.note('12 bit, internal 2.048 V reference, gain 2: 0 - 4.095 V in 1 mV steps.\n'
           'A: LOAD_CTRL, 2.5 A per volt = 2.44 mA per LSB. B: CV_SET in VSEN volts.\n'
           'Both outputs are 0 V after power-up (POR shutdown): no EEPROM surprise\n'
           'like the MCP4725.', 212, 104)
    s.end_block()
    # ------------------------------------------------------------ ADC
    s.begin_block('C   Readback ADC: 16 bit, 4 channels', FILL_A)
    a = s.ic('Analog_ADC:ADS1118IDGS', 'U10', 'ADS1118', 262, 150, 20, fp='Package_SO:TSSOP-10_3x3mm_P0.5mm', f={'MPN': 'ADS1118IDGSR', 'LCSC': 'C55347'}); a.fpos = {'Reference': (274, 136), 'Value': (262, 170, 'center')}
    for pn, name in (('1', 'SCK_ISO'), ('10', 'MOSI_ISO'), ('2', '~{CS_ADC}_ISO'), ('9', 'MISO_ISO')):
        s.stub(a.pin(pn), name, 'R', kind='label', length=8, color=C_SPI)
    s.stub(a.pin('4'), 'ISEN_ADC', 'L', shape='input', length=14, color=C_MEAS)
    s.stub(a.pin('5'), 'VSEN_ADC', 'L', shape='input', length=14, color=C_MEAS)
    s.stub(a.pin('6'), 'TEMP_MON', 'L', shape='input', length=14, color=C_MEAS)
    p = a.pin('7')
    r = s.res('R24', '1k', p[0] - 16, p[1], h=True); r.fpos = {'Reference': (r.x, p[1] + 2.9, 'center'), 'Value': (r.x, p[1] + 5.4, 'center')}; s.wire(p, rgt(r)); s.wire(lft(r), (p[0] - 28, p[1]), color=C_SET); s.hier('VSET', p[0] - 28, p[1], shape='input', color=C_SET)
    c = s.cap('C30', '10nF C0G', p[0] - 7, p[1] + 8, fl=True); s.wire((p[0] - 7, p[1]), top(c)); s.rail('AGND', p[0] - 7, bot(c)[1])
    vdd, g = a.pin('8'), a.pin('3')
    s.wire(vdd, (vdd[0], vdd[1] - 4), color=C_PWR); s.rail('+5V_ISO', vdd[0], vdd[1] - 4); s.rail('AGND', g[0], g[1])
    s.rowcaps(300, 134, [('C31', '100nF', C0603), ('C32', '1uF', C0603)], '+5V_ISO', 'AGND', pitch=16)
    s.note('AIN0 ISEN (0.30 V/A), AIN1 VSEN (0.049 V/V), AIN2 heatsink NTC, AIN3 the\n'
           'live V_SET node (PGA +-256 mV): shows what the loops really get after OTP,\n'
           'OFF, KILL or CV pull it down. Internal reference 0.01 %, 7 ppm/K, 860 SPS,\n'
           'plus a die temperature sensor.', 212, 200)
    s.end_block()
    return s


# ======================================================================= setpoint and CV
def setpoint_cv():
    s = S('Set-point and hardware CV: V_SET divider, protective pull-downs, CV error amplifier',
          'V_SET = LOAD_CTRL / 16 is the only node the four channels follow. Anything that must stop the load pulls it to AGND.')
    s.begin_block('A   V_SET: 0 - 256 mV = 0 - 10.24 A', FILL_A)
    y = 62
    s.hier('LOAD_CTRL', 30, y, shape='input', color=C_SET)
    rt = s.res('R31', '15k', 48, y, h=True, tol='1%'); s.wire((30, y), lft(rt), color=C_SET)
    s.wire(rgt(rt), (250, y), color=C_SET); s.hier('VSET', 250, y, ang=0, shape='bidirectional', color=C_SET)
    rb = s.res('R32', '1k', 64, y + 10, tol='1%'); s.wire((64, y), top(rb), color=C_SET); s.rail('AGND', 64, bot(rb)[1])
    c = s.cap('C33', '10nF C0G', 80, y + 10); s.wire((80, y), top(c), color=C_SET); s.rail('AGND', 80, bot(c)[1])
    for i, (ref, name) in enumerate([('Q11', 'OTP_GATE'), ('Q12', 'OFF_GATE')]):
        x = 130 + i * 48
        q = s.fet(Q2N, ref, '2N7002', x, y + 13, f={'LCSC': 'C8545'})
        s.wire(q.pin('3'), (q.pin('3')[0], y), color=C_SET); s.rail('AGND', q.pin('2')[0], q.pin('2')[1])
        s.wire(q.pin('1'), (x - 16, y + 13), color=C_PROT); s.hier(name, x - 16, y + 13, shape='input', color=C_PROT)
    s.tp('TP11', 'VSET', 230, y)
    s.note('R31 / R32 = 15 : 1, 1 % (the gain is calibrated): 4.096 V in gives 256 mV = 2.56 A per channel. C33 slews the\n'
           'step in 9 us so the loops never see a step edge. Q11 and Q12 are hardware and work with\n'
           'the MCU dead. CV (block B) pulls this node down too, so LOAD_CTRL stays the ceiling in CV.', 24, 100)
    s.end_block()
    s.begin_block('B   Hardware constant-voltage loop (LTspice rev_e deck 06)', FILL_A)
    y = 150
    s.hier('CV_SET', 30, y, shape='input', color=C_SET)
    r1 = s.res('R33', '1k', 44, y, h=True); s.wire((30, y), lft(r1), color=C_SET)
    c1 = s.cap('C34', '100nF', 56, y + 9); s.wire(rgt(r1), (56, y), (72, y), color=C_SET); s.wire((56, y), top(c1)); s.rail('AGND', 56, bot(c1)[1])
    r3 = s.res('R34', '100k', 74, y + 9, tol='1%'); s.wire((74, y), top(r3)); s.rail('AGND', 74, bot(r3)[1])
    u = s.amp(AMP, 'U12', 'TLV9154', 90, y - 2.54, unit=3, mirror='x', f=AMP_F)
    plus, minus, out = u.pin('10'), u.pin('9'), u.pin('8')
    s.wire((72, y), plus, color=C_SET)
    s.tp('TP31', 'CV_SET', 62, y)
    fbx = 77
    s.wire(minus, (fbx, minus[1]), (fbx, y - 18), color=C_MEAS)
    rin = s.res('R35', '100k', 62, y - 18, h=True, tol='1%')
    s.hier('VSEN_OA', 44, y - 18, shape='input', color=C_MEAS); s.wire((44, y - 18), lft(rin), color=C_MEAS); s.wire(rgt(rin), (fbx, y - 18), color=C_MEAS)
    rz = s.res('R36', '10k', 88, y - 18, h=True, tol='1%'); cz = s.cap('C35', '47nF X7R', 104, y - 18, h=True)
    s.wire((fbx, y - 18), lft(rz)); s.wire(rgt(rz), lft(cz))
    ox = 114
    s.wire(rgt(cz), (ox, y - 18), (ox, out[1])); s.wire(out, (ox, out[1]))
    rg = s.res('R37', '1k', 122, out[1], h=True); s.wire((ox, out[1]), lft(rg))
    q = s.fet(Q2N, 'Q13', '2N7002', 142, out[1], f={'LCSC': 'C8545'}); s.wire(rgt(rg), q.pin('1'))
    s.rail('AGND', q.pin('2')[0], q.pin('2')[1])
    s.wire(q.pin('3'), (164, q.pin('3')[1]), color=C_SET); s.hier('VSET', 164, q.pin('3')[1], ang=0, shape='bidirectional', color=C_SET)
    v = s.amp(AMP, 'U12', 'TLV9154', 224, y - 2.54, unit=4, f=AMP_F)
    p2, m2, o2 = v.pin('12'), v.pin('13'), v.pin('14')
    s.wire(p2, (212, p2[1])); s.rail('AGND', 212, p2[1])
    s.wire(m2, (214, m2[1]), (214, y + 8), (236, y + 8), (236, o2[1])); s.wire(o2, (236, o2[1]))
    s.note('spare section: follower at AGND', 240, y + 11)
    s.note('Why: a current-source DUT cannot be held in CC (two current sources in series rail to\n'
           'compliance), and a firmware CV loop on the DAC cannot either: 1 LSB into the 2.2 uF snubber\n'
           'slews 11 V in one 10 ms update. Here: V_DUT below CV_SET -> U12C rises -> Q13 pulls V_SET\n'
           'down -> less current. CV_SET = 0 V: VSEN_OA (85 mV minimum) > CV_SET, U12C stays low, Q13\n'
           'off, plain CC (decks 01-04). Deck 06: settles for 0.1 - 8 A with and without 47 uF across\n'
           'the DUT. Below 0.1 A it hunts: use CC or a resistor there.', 24, 200)
    s.end_block()
    s.begin_block('C   Pass-through pins for the block diagram on page 1', FILL_A)
    y = 236
    s.hier('VSET', 40, y, shape='bidirectional', color=C_SET); s.wire((40, y), (70, y), color=C_SET); s.hier('VSET_MON', 70, y, ang=0, shape='output', color=C_SET)
    s.hier('VSEN_OA', 40, y + 8, shape='input', color=C_MEAS); s.wire((40, y + 8), (70, y + 8), color=C_MEAS); s.hier('VSEN_OA_OVP', 70, y + 8, ang=0, shape='output', color=C_MEAS)
    s.note('Same nets, second names: VSET_MON feeds the ADC read-back (page 6), VSEN_OA_OVP hands the VSEN amplifier\n'
           'output on to the over-voltage comparator (page 9). They exist so the top sheet can be drawn as a block diagram\n'
           'with wires, without a net label.', 84, y + 2)
    s.end_block()
    return s


# ======================================================================= channel (one file, 4 instances)
def channel():
    s = S('Current-sink channel (4 instances, one TLV9154 section each)',
          'Each MOSFET gets its own loop forced to V_SET / 0.1 R, so current and power share equally whatever the threshold spread.')
    s.begin_block('Channel (one of four): TLV9154 section, 3.3k / 1n / 47R compensation, IRFP250N, 2 x 0.2R Kelvin sense', FILL_A)
    X, Y = -30, -27
    s.hier('VSET', 60.96 + X, 106.68 + Y, shape='input', color=C_SET)
    u = s.amp(AMP, 'U11', 'TLV9154', 134.62 + X, 104.14 + Y, unit=1, mirror='x', fp=None, f=AMP_F)
    u.unit_fn = lambda v: v['n']
    fb, plus, out = u.pin('2'), u.pin('3'), u.pin('1')
    s.wire((60.96 + X, 106.68 + Y), plus, color=C_SET)
    s.hier('KILL', 60.96 + X, fb[1], shape='input', color=C_PROT)
    rk = s.res('R{n}01', '4.7k', 71.12 + X, fb[1], h=True, tol='1%')
    dk = s.dio(D1N, 'D{n}01', '1N4148WS', 88.9 + X, fb[1], rot=180, f={'LCSC': 'C2128'})
    s.wire((60.96 + X, fb[1]), lft(rk), color=C_PROT); s.wire(rgt(rk), dk.pin('2'), color=C_PROT)
    fbx = 119.38 + X
    s.wire(dk.pin('1'), (fbx, fb[1]), fb)
    rb = s.res('R{n}02', '15M', 106.68 + X, 88.9 + Y, tol='5%')
    s.wire(rb.pin('2'), (106.68 + X, fb[1])); s.rail('+12V_ISO', 106.68 + X, rb.pin('1')[1])
    cc = s.cap('C{n}01', '1nF C0G 50V', 134.62 + X, 88.9 + Y, h=True)
    dz = s.dio(ZENER, 'D{n}02', 'BZX84C6V8', 134.62 + X, 76.2 + Y, rot=180, fp=SOT23, f={'LCSC': 'C118571'})
    outx = 149.86 + X
    s.wire((fbx, fb[1]), (fbx, 88.9 + Y), (fbx, 76.2 + Y))
    s.wire((outx, out[1]), (outx, 88.9 + Y), (outx, 76.2 + Y))
    s.wire((fbx, 88.9 + Y), lft(cc)); s.wire(rgt(cc), (outx, 88.9 + Y))
    s.wire((fbx, 76.2 + Y), dz.pin('1')); s.wire(dz.pin('3'), (outx, 76.2 + Y))
    rg = s.res('R{n}04', '47', 157.48 + X, out[1], h=True, tol='1%')
    s.wire(out, (outx, out[1]), lft(rg))
    qx = 190.5 + X
    q = s.fet(QP, 'Q{n}01', 'IRFP250NPBF', qx, out[1], fp=TO247, f={'MPN': 'IRFP250NPBF (Infineon, LCSC C2580; not the sub-$1 clones)', 'LCSC': 'C2580', 'Alt': 'IRFP240PBF'})
    q.fpos = {'Reference': (qx + 5, out[1] - 9.5), 'Value': (qx + 5, out[1] - 6.7)}
    s.wire(rgt(rg), (165.1 + X, out[1]), (177.8 + X, out[1]), q.pin('1'))
    s.tp('TP{n}01', 'GATE', 171.45 + X, out[1])
    rgs = s.res('R{n}05', '100k', 165.1 + X, 119.38 + Y)
    dgs = s.dio(ZENER, 'D{n}03', 'BZX84C15', 177.8 + X, 119.38 + Y, rot=270, fp=SOT23, f={'LCSC': 'C328579'})
    s.wire((165.1 + X, out[1]), rgs.pin('1')); s.wire((177.8 + X, out[1]), dgs.pin('3'))
    sbus = 129.54 + Y
    s.wire(rgs.pin('2'), (165.1 + X, sbus)); s.wire(dgs.pin('1'), (177.8 + X, sbus))
    d, src = q.pin('2'), q.pin('3')
    s.hier('DRAIN', 218.44 + X, 88.9 + Y, ang=0, color=C_HI)
    s.wire(d, (d[0], 88.9 + Y), (218.44 + X, 88.9 + Y), width=0.6, color=C_HI)
    s.wire(src, (src[0], sbus), width=0.6, color=C_HI)
    xa, xb = src[0] + 6.35, src[0] + 19.05
    ra = s.res('R{n}06', '0R2 2W', xa, 140.97 + Y, fp=R2512, tol='1%', f={'LCSC': 'C5375444'})
    rbb = s.res('R{n}07', '0R2 2W', xb, 140.97 + Y, fp=R2512, tol='1%', f={'LCSC': 'C5375444'})
    s.wire((165.1 + X, sbus), (177.8 + X, sbus), (src[0], sbus))
    s.wire((src[0], sbus), (xa, sbus), (xb, sbus), (src[0] + 27.94, sbus), (226.06 + X, sbus), width=0.6, color=C_HI)
    s.wire((xa, sbus), ra.pin('1'), width=0.6, color=C_HI); s.wire((xb, sbus), rbb.pin('1'), width=0.6, color=C_HI)
    s.wire(ra.pin('2'), (xa, 152.4 + Y), (xb, 152.4 + Y), width=0.6, color=C_HI)
    s.wire(rbb.pin('2'), (xb, 152.4 + Y), width=0.6, color=C_HI)
    s.rail('PGND', src[0] + 12.7, 152.4 + Y)
    s.tp('TP{n}02', 'SOURCE', src[0] + 27.94, sbus, left=True)
    rf = s.res('R{n}03', '3.3k', 134.62 + X, 63.5 + Y, h=True, tol='1%')
    s.wire((fbx, 76.2 + Y), (fbx, 63.5 + Y), lft(rf), color=C_MEAS)
    s.wire(rgt(rf), (226.06 + X, 63.5 + Y), (226.06 + X, sbus), color=C_MEAS)
    rav = s.res('R{n}08', '10k', 233.68 + X, sbus, h=True, tol='1%')
    s.wire((226.06 + X, sbus), lft(rav), color=C_MEAS)
    s.hier('AVG', 248.92 + X, sbus, ang=0, shape='output', color=C_MEAS)
    s.wire(rgt(rav), (248.92 + X, sbus), color=C_MEAS)
    s.note('Rs: two 0.2 R 2512 in parallel = 0.1 R, so I_ch = V_SET / 0.1 R (2.56 A full scale).\n'
           'KELVIN: Rn03 and Rn08 connect at the TOP PAD of the Rs pair on their own trace, never\n'
           'along the high-current source copper. Rg within 10 mm of the gate pin. Dn03 and Rn05 sit\n'
           'at the FET pins. Dn02 limits integrator wind-up; Rn02 (15M) gives +2.6 mV offset, above the\n'
           'TLV9154 0.83 mV Vos limit, so DAC code 0 is truly 0 A (dead zone about 106 mA in total, 42\n'
           'codes). Loop values from rev_e deck 03: PM >= 87 deg, GM >= 22 dB for the IRFP250N / 240 / 530\n'
           '(the big-die IXTH proxy drops to 80 deg / 9 dB). Change them only with a re-run of deck 03.\n'
           '(n = channel number)', 24, 166)
    s.end_block()
    s.begin_block('Chain pins: the four channels are daisy-chained on page 1 (each net enters on the left and leaves on the right)', FILL_A)
    for i, (name, shape, col) in enumerate([('KILL', 'input', C_PROT), ('VSET', 'input', C_SET), ('AVG', 'output', C_MEAS), ('DRAIN', 'passive', C_HI)]):
        y = 196 + i * 6
        s.hier(name, 40, y, shape=shape, color=col); s.wire((40, y), (70, y), color=col, width=0.6 if name == 'DRAIN' else 0); s.hier(name + '_T', 70, y, ang=0, shape=shape, color=col)
    s.note('Same nets, second names (KILL_T = KILL ...). Channel 4 leaves KILL_T, VSET_T and AVG_T open; its DRAIN_T\n'
           'carries DRAIN on to the dropout comparator. Electrically every channel still hangs directly on the four nets.', 84, 198)
    s.end_block()
    return s


# ======================================================================= sense
def sense():
    s = S('Sense: ISEN = mean of the four source nodes, VSEN = true 4-wire difference amplifier',
          'Both outputs are scaled for the 4.096 V ADC range and clamped to +5V_ISO. Offsets are deliberate and calibrated out in firmware.')

    def adc(x, y, rref, cref, dref, name, tp):
        r = s.res(rref, '1k', x + 8.89, y, h=True, tol='1%')
        s.wire((x, y), lft(r), color=C_MEAS)
        c = s.cap(cref, '10nF C0G 50V', x + 22.86, y + 10.16, fl=True)
        s.wire((x + 22.86, y), c.pin('1')); s.rail('AGND', x + 22.86, c.pin('2')[1])
        d = s.dio(BAT54S, dref, 'BAT54S', x + 40.64, y, rot=270, mirror='x', fp=SOT23, f={'LCSC': 'C12765'})
        com, ka, an = d.pin('3'), d.pin('2'), d.pin('1')
        s.wire(rgt(r), (x + 22.86, y), (x + 33.02, y), com, color=C_MEAS)
        s.rail('+5V_ISO', ka[0], ka[1], rot=(0 if ka[1] < an[1] else 180))
        s.rail('AGND', an[0], an[1])
        d.fpos = {'Reference': (x + 44.5, y - 2.6), 'Value': (x + 44.5, y + 0.3)}
        s.wire((x + 33.02, y), (x + 33.02, y + 15.24), (x + 58.42, y + 15.24), color=C_MEAS)
        s.hier(name, x + 58.42, y + 15.24, ang=0, shape='output', color=C_MEAS)
        s.tp(tp, name, x + 50.8, y + 15.24)

    s.begin_block('A   ISEN: 0.300 V/A + 0.15 V', FILL_A)
    X, Y = -40, -20
    ax, ay = 121.92 + X, 76.2 + Y
    u = s.amp(AMP, 'U12', 'TLV9154', ax, ay, unit=1, f=AMP_F)
    plus, minus, out = u.pin('3'), u.pin('2'), u.pin('1')
    s.hier('AVG', 71.12 + X, plus[1], shape='input', color=C_MEAS)
    s.wire((71.12 + X, plus[1]), plus, color=C_MEAS)
    ro = s.res('R41', '1M', 96.52 + X, 63.5 + Y, tol='1%')
    s.wire(ro.pin('2'), (96.52 + X, plus[1])); s.rail('+5V_ISO', 96.52 + X, ro.pin('1')[1])
    fbx = 106.68 + X
    s.wire(minus, (fbx, minus[1]), (fbx, 93.98 + Y))
    rg = s.res('R42', '10k', fbx, 97.79 + Y, tol='1%'); s.rail('AGND', fbx, rg.pin('2')[1])
    rf = s.res('R43', '110k', 124.46 + X, 93.98 + Y, h=True, tol='1%')
    s.wire((fbx, 93.98 + Y), lft(rf))
    ox = 139.7 + X
    s.wire(rgt(rf), (ox, 93.98 + Y), (ox, out[1])); s.wire(out, (ox, out[1]))
    adc(ox, out[1], 'R44', 'C41', 'D41', 'ISEN_ADC', 'TP21')
    s.note('Gain 12 (R43 / R42 + 1, 1 %: up to 2 % gain error, removed by the 2-point calibration).\n'
           'R41 injects +12 mV at the input (= +0.15 V out), kept from Rev C: a zero calibration removes\n'
           'it. Full scale 3.22 V at 10.24 A, 0.4 mA per ADS1118 LSB. U12A, standard quad pinout.', 24, 104)
    s.end_block()
    s.begin_block('B   VSEN: 0.049 V/V + 0.10 V, true 4-wire', FILL_A)
    X, Y = -28, -20
    ox = 139.7 + X
    vx, vy = 121.92 + X, 167.64 + Y
    v = s.amp(AMP, 'U12', 'TLV9154', vx, vy, unit=2, f=AMP_F)
    p, m, o = v.pin('5'), v.pin('6'), v.pin('7')
    s.hier('SENSE_P', 60.96 + X, p[1], shape='input', color=C_MEAS)
    r1 = s.res('R45', '200k', 78.74 + X, p[1], h=True, tol='1%', fp=R1206, f={'LCSC': 'C17954'})
    s.wire((60.96 + X, p[1]), lft(r1), color=C_MEAS)
    s.wire(rgt(r1), (86.36 + X, p[1]), (99.06 + X, p[1]), p)
    r2 = s.res('R46', '10k', 86.36 + X, p[1] + 10.16, tol='1%'); s.wire((86.36 + X, p[1]), r2.pin('1')); s.rail('AGND', 86.36 + X, r2.pin('2')[1])
    r3 = s.res('R47', '470k', 99.06 + X, p[1] + 10.16, tol='1%')
    s.wire((99.06 + X, p[1]), top(r3)); s.rail('+5V_ISO', bot(r3)[0], bot(r3)[1], rot=180)
    s.hier('SENSE_N', 60.96 + X, m[1] - 22.86, shape='input', color=C_MEAS)
    r4 = s.res('R48', '200k', 78.74 + X, m[1] - 22.86, h=True, tol='1%', fp=R1206, f={'LCSC': 'C17954'})
    s.wire((60.96 + X, m[1] - 22.86), lft(r4), color=C_MEAS)
    s.wire(rgt(r4), (106.68 + X, m[1] - 22.86), (106.68 + X, m[1]), m)
    r5 = s.res('R49', '10k', 124.46 + X, m[1] - 22.86, h=True, tol='1%')
    s.wire((106.68 + X, m[1] - 22.86), lft(r5))
    s.wire(rgt(r5), (ox, m[1] - 22.86), (ox, o[1])); s.wire(o, (ox, o[1]))
    s.hier('VSEN_OA', ox + 2.54, o[1] + 12.7, ang=180, shape='output', color=C_MEAS)
    s.wire((ox + 2.54, o[1]), (ox + 2.54, o[1] + 12.7), color=C_MEAS)
    adc(ox, o[1], 'R50', 'C42', 'D42', 'VSEN_ADC', 'TP22')
    s.note('VSEN = 0.049 x (SENSE_P - SENSE_N) + 0.10 V: 2.5 mV of DUT per LSB, clips at 65 V.\n'
           'R45 and R48 see 60 V: 1206. 1 % resistors: up to 2 % gain error (calibrated out) and\n'
           'CMRR about 40 dB, harmless because SENSE_N sits within millivolts of AGND. R49 feeds\n'
           'back to -IN (Rev B had it on +IN and latched). VSEN_OA also feeds CV and OVP.', 24, 198)
    s.end_block()
    return s


# ======================================================================= protection
def protection():
    s = S('Protection: over-temperature, dropout / KILL, NTC-open, over-voltage, hardware OFF',
          'LM339 open-collector comparators on +12V_ISO. Thresholds are ratios of +5V_ISO, the same rail that feeds the NTC divider.')
    s.begin_block('A   Heatsink NTC and TEMP_MON', FILL_A)
    nx = 42
    rn = s.res('R51', '10.0k', nx, 60, tol='1%')
    s.rail('+5V_ISO', nx, top(rn)[1])
    jn = s.part('Connector_Generic:Conn_01x02', 'J6', 'NTC 10k B3950', nx + 26, 82, fp='Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical', f={'MPN': 'JST B2B-XH-A(LF)(SN); NTC = 10k B3950 ring-lug thermistor', 'LCSC': 'C158012'})
    jn.fpos = {'Reference': (nx + 26, 76, 'center'), 'Value': (nx + 26, 89.5, 'center')}
    s.wire(bot(rn), (nx, jn.pin('1')[1]), jn.pin('1'), color=C_MEAS)
    s.wire(jn.pin('2'), (nx + 14, jn.pin('2')[1]), (nx + 14, 98)); s.rail('AGND', nx + 14, 98)
    cn = s.cap('C51', '100nF', nx, 92, fl=True)
    s.wire((nx, jn.pin('1')[1]), top(cn)); s.rail('AGND', nx, bot(cn)[1])
    s.wire((nx, 68), (nx + 14, 68), color=C_MEAS); s.lab('V_NTC', nx + 14, 68, color=C_MEAS)
    rm = s.res('R52', '10k', 40, 124, h=True)
    cm = s.cap('C52', '100nF X7R', 56, 132)
    s.lab('V_NTC', lft(rm)[0], lft(rm)[1], ang=180, color=C_MEAS); s.wire(rgt(rm), (56, 124), (80, 124), color=C_MEAS)
    s.wire((56, 124), top(cm)); s.rail('AGND', 56, bot(cm)[1])
    s.hier('TEMP_MON', 80, 124, ang=0, shape='output', color=C_MEAS)
    s.note('V_NTC (10k B3950 lug thermistor on the\nheatsink next to FET 2): 2.50 V at 25 C,\n'
           '1.52 V at 45 C, 0.75 V at 70 C, 0.49 V at\n85 C. TEMP_MON goes to the ADC: the MCU\nruns the fan from it and shows the\ntemperature.', 24, 166)
    s.end_block()

    def comparator(x, y, unit, pplus, pminus, pout, top_val, bot_val, hyst_val, refs):
        u = s.amp('Comparator:LM339', 'U14', 'LM339', x, y, unit=unit, f={'Footprint': SO14, 'MPN': 'LM339DR', 'LCSC': 'C5236695'})
        plus, minus, out = u.pin(pplus), u.pin(pminus), u.pin(pout)
        rt = s.res(refs[0], top_val, x - 17.78, plus[1] - 10.16, tol='1%', fl=True)
        rb = s.res(refs[1], bot_val, x - 17.78, plus[1] + 12.7, tol='1%')
        s.wire(bot(rt), (x - 17.78, plus[1]), plus); s.wire((x - 17.78, plus[1]), top(rb))
        s.rail('+5V_ISO', x - 17.78, top(rt)[1]); s.rail('AGND', x - 17.78, bot(rb)[1])
        rh = s.res(refs[2], hyst_val, x, plus[1] - 15.24, h=True, tol='1%')
        s.wire(lft(rh), (x - 10.16, lft(rh)[1]), (x - 10.16, plus[1]))
        s.wire(rgt(rh), (x + 12.7, rgt(rh)[1]), (x + 12.7, out[1])); s.wire(out, (x + 12.7, out[1]))
        return plus, minus, out

    s.begin_block('B   Over-temperature: 85 C trip, 70 C release', FILL_A)
    x, y = 165, 68
    pl, mi, ou = comparator(x, y, 1, '5', '4', '2', '90.9k', '10.0k', '402k', ('R53', 'R54', 'R55'))
    s.wire(mi, (x - 30, mi[1]), color=C_MEAS); s.lab('V_NTC', x - 30, mi[1], ang=180, color=C_MEAS)
    pux = x + 12.7
    pu = s.res('R56', '10k', pux + 7.62, y - 15.24)
    s.rail('+12V_ISO', pux + 7.62, top(pu)[1]); s.wire(bot(pu), (pux + 7.62, y), (pux, y))
    s.hier('OTP_GATE', pux + 24, y, ang=0, shape='output', color=C_PROT); s.wire((pux + 7.62, y), (pux + 24, y), color=C_PROT)
    s.note('In+ = 0.099 x rail (0.49 V = 85 C). Output high -> Q11\nshorts V_SET. Hysteresis via R55 from the 12 V output:\nreleases at 0.75 V = 70 C.', x - 42, y + 48)
    s.end_block()
    s.begin_block('C   Dropout / anti-wind-up KILL: DRAIN below 0.45 V', FILL_A)
    x, y = 340, 68
    pl, mi, ou = comparator(x, y, 2, '7', '6', '1', '100k', '10.0k', '165k', ('R57', 'R58', 'R59'))
    rdr = s.res('R60', '47k', x - 48, mi[1], h=True, tol='1%', fp=R1206, f={'LCSC': 'C102201'})
    s.hier('DRAIN', x - 62, mi[1], shape='input', color=C_HI); s.wire((x - 62, mi[1]), lft(rdr), color=C_HI)
    s.wire(rgt(rdr), (x - 33.02, mi[1]), mi)
    dz = s.dio(ZENER, 'D43', 'BZX84C12', x - 33.02, mi[1] + 10.16, rot=270, fp=SOT23, f={'LCSC': 'C118577'})
    s.wire((x - 33.02, mi[1]), dz.pin('3')); s.rail('AGND', x - 33.02, dz.pin('1')[1])
    pux = x + 12.7
    pu = s.res('R61', '10k', pux + 7.62, y - 15.24)
    s.rail('+12V_ISO', pux + 7.62, top(pu)[1]); s.wire(bot(pu), (pux + 7.62, y), (pux, y))
    s.hier('KILL', pux + 24, y, ang=0, shape='output', color=C_PROT); s.wire((pux + 7.62, y), (pux + 24, y), color=C_PROT)
    s.tp('TP41', 'KILL', pux + 18, y)
    s.note('KILL pulls every channel In- high through 4.7k + 1N4148\nwhen the DUT is absent or below 0.45 V; releases above\n0.54 V. Stops the 115 - 170 A recovery spikes of deck 04.\nR60 sees 60 V: 1206.', x - 62, y + 50)
    s.end_block()
    s.begin_block('D   NTC open and hardware OFF: all roads to OFF_GATE', FILL_A)
    x, y = 165, 160
    u = s.amp('Comparator:LM339', 'U14', 'LM339', x, y, unit=3, f={'Footprint': SO14})
    pl, mi, ou = u.pin('11'), u.pin('10'), u.pin('13')
    s.wire(pl, (x - 10.16, pl[1]), (x - 10.16, mi[1] - 21), (x - 34, mi[1] - 21), color=C_MEAS); s.lab('V_NTC', x - 34, mi[1] - 21, ang=180, color=C_MEAS)
    r1 = s.res('R62', '10.0k', x - 17.78, mi[1] - 10, tol='1%', fl=True)
    r2 = s.res('R63', '27.4k', x - 17.78, mi[1] + 10, tol='1%')
    s.rail('+5V_ISO', x - 17.78, top(r1)[1]); s.wire(bot(r1), (x - 17.78, mi[1]), mi); s.wire((x - 17.78, mi[1]), top(r2)); s.rail('AGND', x - 17.78, bot(r2)[1])
    pux = x + 12.7
    pu = s.res('R64', '10k', pux, y - 12.7)
    s.rail('+12V_ISO', pux, top(pu)[1]); s.wire(ou, (pux, y)); s.wire(bot(pu), (pux, y))
    dc = s.dio(BAT54C, 'D44', 'BAT54C', pux + 17.78, y + 2.54, fp=SOT23, f={'LCSC': 'C2135'})
    dc.fpos = {'Reference': (pux + 17.78, y - 3.4, 'center'), 'Value': (pux + 7.62, y + 8.6, 'center')}
    s.wire((pux, y), (pux, dc.pin('1')[1]), dc.pin('1'))
    s.hier('LOAD_OFF_ISO', pux + 36, dc.pin('2')[1], ang=0, shape='input', color=C_PROT); s.wire(dc.pin('2'), (pux + 36, dc.pin('2')[1]), color=C_PROT)
    k = dc.pin('3')
    s.hier('OFF_GATE', k[0] + 18, k[1] + 5.08, ang=0, shape='output', color=C_PROT)
    rd = s.res('R65', '100k', k[0], k[1] + 12.7)
    s.wire(k, (k[0], k[1] + 5.08), top(rd)); s.wire((k[0], k[1] + 5.08), (k[0] + 18, k[1] + 5.08), color=C_PROT)
    s.rail('AGND', k[0], bot(rd)[1])
    d45 = s.dio(D1N, 'D45', '1N4148WS', k[0] + 11, k[1] + 11, rot=270, f={'LCSC': 'C2128'})
    s.wire(d45.pin('1'), (k[0] + 11, k[1] + 5.08)); s.wire(d45.pin('2'), (k[0] + 11, k[1] + 19)); s.lab('OVP_OUT', k[0] + 11, k[1] + 19, ang=270, color=C_PROT)
    s.note('NTC open or unplugged: V_NTC above 0.73 x rail (= 3.66 V, NTC > 27 k)\n'
           'forces 0 A; an open NTC would otherwise read as cold. False trip only\n'
           'below about 3 C. LOAD_OFF_ISO: the MCU-side OFF, 5 V logic through the\n'
           'isolator, asserted whenever the USB side is dead. OVP_OUT (block E)\n'
           'joins through D45. R65 defines the node when nothing drives it.', x - 42, y + 62)
    s.end_block()
    s.begin_block('E   Over-voltage: DUT above 62 V', FILL_A)
    x, y = 340, 160
    u = s.amp('Comparator:LM339', 'U14', 'LM339', x, y, unit=4, f={'Footprint': SO14})
    pl, mi, ou = u.pin('9'), u.pin('8'), u.pin('14')
    yt = mi[1] - 21
    rin = s.res('R66', '10k', x - 30, yt, h=True, tol='1%')
    s.hier('VSEN_OA', x - 48, yt, shape='input', color=C_MEAS); s.wire((x - 48, yt), lft(rin), color=C_MEAS)
    s.wire(rgt(rin), (x - 10.16, yt), (x - 10.16, pl[1]), pl)
    rh = s.res('R67', '1M', x, pl[1] - 12, h=True, tol='1%')
    s.wire(lft(rh), (x - 10.16, lft(rh)[1])); s.wire(rgt(rh), (x + 12.7, rgt(rh)[1]), (x + 12.7, ou[1]))
    r1 = s.res('R68', '5.90k', x - 17.78, mi[1] - 10, tol='1%', fl=True)
    r2 = s.res('R69', '10.0k', x - 17.78, mi[1] + 10, tol='1%')
    s.rail('+5V_ISO', x - 17.78, top(r1)[1]); s.wire(bot(r1), (x - 17.78, mi[1]), mi); s.wire((x - 17.78, mi[1]), top(r2)); s.rail('AGND', x - 17.78, bot(r2)[1])
    pux = x + 12.7
    pu = s.res('R70', '10k', pux + 7.62, y - 15.24)
    s.rail('+12V_ISO', pux + 7.62, top(pu)[1]); s.wire(bot(pu), (pux + 7.62, y), (pux, y)); s.wire(ou, (pux, y))
    s.wire((pux + 7.62, y), (pux + 24, y), color=C_PROT); s.lab('OVP_OUT', pux + 24, y, color=C_PROT)
    s.note('VSEN_OA above 0.629 x rail (3.15 V = 62 V at the terminals)\n'
           'forces 0 A through OFF_GATE. Protects the 58 V fuse rating and\n'
           'the 70 V TVS. R67 gives about 1.8 V of hysteresis. Firmware\n'
           'latches the trip; the comparator alone would re-arm when the\n'
           'DUT sags.', x - 62, y + 62)
    s.end_block()
    s.begin_block('F   Supplies of the analog ICs', FILL_A)
    YF = 256
    u = s.amp('Comparator:LM339', 'U14', 'LM339', 36, YF, unit=5, f={'Footprint': SO14})
    vp, vm = u.pin('3'), u.pin('12')
    s.wire(vp, (vp[0], vp[1] - 4), color=C_PWR); s.rail('+12V_ISO', vp[0], vp[1] - 4); s.rail('AGND', vm[0], vm[1])
    for i, (lib, ref, val, unit, vpn, vmn) in enumerate([(AMP, 'U11', 'TLV9154', 5, '4', '11'), (AMP, 'U12', 'TLV9154', 5, '4', '11')]):
        x0 = 66 + i * 28
        p = s.amp(lib, ref, val, x0, YF, unit=unit, f=AMP_F)
        vpp, vmm = p.pin(vpn), p.pin(vmn)
        s.wire(vpp, (vpp[0], vpp[1] - 6), color=C_PWR); s.rail('+12V_ISO', vpp[0], vpp[1] - 6)
        s.wire(vmm, (vmm[0], vmm[1] + 3)); s.rail('AGND', vmm[0], vmm[1] + 3)
    s.rowcaps(130, YF, [('C53', '100nF 50V', C0603), ('C54', '100nF 50V', C0603), ('C55', '100nF 50V', C0603), ('C57', '10uF 25V', C0805)], '+12V_ISO', 'AGND', pitch=18)
    s.note('100 nF 50 V at every V+ pin (LM339,\nU11, U12), 10 uF bulk near U11.', 204, YF + 2)
    s.end_block()
    return s


# ======================================================================= power path
def power_path():
    s = S('Power path: DUT terminals, 58 V fuse, TVS, snubber, 4-wire sense',
          'DUT+ -> fuse -> DRAIN bus -> four drains. The source resistors return to PGND, which meets AGND only at NT1.')
    s.begin_block('A   Terminals and DRAIN bus', FILL_A)
    W = STUD
    y = 58
    jp = s.part('Connector_Generic:Conn_01x01', 'J7', 'DUT+', 40, y, mirror='y', fp=W, f={'MPN': 'M4 x 12 bolt, nut, 2 washers (hardware store)', 'Note': 'plated M4 hole: ring lug from the DUT lead or the panel binding post under the bolt head'})
    jp.fpos = {'Reference': (34, y - 4.6), 'Value': (34, y + 5.2)}
    f = s.res('F1', '15A 58VDC mini blade', 96, y, h=True, part='Device:Fuse', fp='Fuse:Fuse_Blade_Mini_directSolder', f={'MPN': 'Littelfuse 0997015.WXN, soldered in (pluggable option: holder 178.6764.0001, LCSC C142933)', 'LCSC': 'C207027'})
    s.wire(jp.pin('1'), lft(f), width=0.6, color=C_HI); s.tp('TP51', 'DUT+', 70, y)
    s.lab('DUT_P', 52, y, color=C_HI)
    tvs = s.dio('Device:D_Zener', 'D51', 'SMCJ70A TVS', 136, y + 16, rot=270, fp='Diode_SMD:D_SMC', f={'LCSC': 'C2943781'})
    rsn = s.res('R71', '2.2R 1W', 160, y + 9, fp=R2512, tol='5%', f={'LCSC': 'C25480'})
    csn = s.cap('C58', '2.2uF 100V X7R', 160, y + 23, fp=C1206, f={'LCSC': 'C170101'})
    s.hier('DRAIN', 220, y, ang=0, color=C_HI)
    s.wire(rgt(f), (136, y), (160, y), (220, y), width=0.6, color=C_HI)
    s.tp('TP52', 'DRAIN', 192, y)
    t1, t2 = tvs.pin('1'), tvs.pin('2')
    tu, td = (t1, t2) if t1[1] < t2[1] else (t2, t1)
    s.wire((136, y), tu); s.wire((160, y), top(rsn)); s.wire(bot(rsn), top(csn))
    pg = y + 38
    s.wire(td, (136, pg)); s.wire(bot(csn), (160, pg))
    jn = s.part('Connector_Generic:Conn_01x01', 'J8', 'DUT-', 40, pg, mirror='y', fp=W, f={'MPN': 'M4 x 12 bolt, nut, 2 washers (hardware store)', 'Note': 'plated M4 hole: ring lug from the DUT lead or the panel binding post under the bolt head'})
    jn.fpos = {'Reference': (34, pg - 4.6), 'Value': (34, pg + 5.2)}
    s.wire(jn.pin('1'), (136, pg), (160, pg), (176, pg), width=0.6, color=C_HI)
    s.rail('PGND', 176, pg)
    s.note('Fuse: the 58 V DC MINI part named, soldered into the direct-solder footprint (a blown\n'
           'fuse means a shorted FET, so it is replaced on the bench anyway). Ordinary blade fuses\n'
           'are rated 32 V, so 58 V is the DUT limit of this board (OVP trips at 62 V). No series\n'
           'diode, so the load works down to 0.6 V. Reverse polarity conducts through the FET body\n'
           'diodes and the TVS and clears the fuse. Copper: >= 5 mm of 2 oz on both layers for\n'
           'DUT+ / DRAIN / PGND. C58 and D51 directly across DRAIN / PGND at the terminals.\n'
           'J7 / J8: plated 4.3 mm holes with a 10 mm pad, M4 bolt and ring lug; the panel binding\n'
           'posts (if fitted) are wired to the same bolts.', 24, 128)
    s.end_block()
    s.begin_block('B   4-wire sense with local fallback', FILL_A)
    js = s.part('Connector_Generic:Conn_01x02', 'J9', 'SENSE', 40, 172, mirror='y', fp='Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical',
                f={'Note': 'Panel S+ / S- terminals, wired to the DUT', 'MPN': 'JST B2B-XH-A(LF)(SN)', 'LCSC': 'C158012'})
    js.fpos = {'Reference': (34, 165.5), 'Value': (34, 179)}
    sp, sn = js.pin('1'), js.pin('2')
    s.hier('SENSE_P', 220, sp[1], ang=0, shape='output', color=C_MEAS); s.wire(sp, (220, sp[1]), color=C_MEAS)
    s.hier('SENSE_N', 220, sn[1] + 12.7, ang=0, shape='output', color=C_MEAS)
    s.wire(sn, (50, sn[1]), (50, sn[1] + 12.7), (220, sn[1] + 12.7), color=C_MEAS)
    rsp = s.res('R72', '100R', 84, 161, fp=R1206, f={'LCSC': 'C17901'}); s.lab('DUT_P', 84, top(rsp)[1], ang=90, color=C_HI); s.wire(bot(rsp), (84, sp[1]))
    rsnn = s.res('R73', '100R', 110, sn[1] + 12.7 + 7.62, fp=R1206, f={'LCSC': 'C17901'})
    s.wire((110, sn[1] + 12.7), top(rsnn)); s.rail('PGND', 110, bot(rsnn)[1])
    s.note('J9 open: R72 / R73 connect the sense amplifier to the terminals. J9 wired to the DUT: they\n'
           'carry only microamps and the lead drop leaves the reading. A miswired sense lead burns a\n'
           '100 R 1206 open and nothing else.', 24, 216)
    s.end_block()
    return s


# ======================================================================= board link (FFC between the two boards)
def board_link():
    s = S('Board link: control board J10 to power board J11 over a 12-way IDC ribbon cable',
          'Two boards on one V-scored fabrication panel. Only USB-side digital and 5 V / 3.3 V power cross the cable; the isolation barrier stays on the power board.')
    s.begin_block('A   J10 (control board, back face)  -  2x6 IDC ribbon  -  J11 (power board, USB-side island)', FILL_D)
    XJ, XK, YJ = 110, 236, 110
    j10 = s.part('Connector_Generic:Conn_01x12', 'J10', 'IDC 2x6 CTRL', XJ, YJ, fp=FFC, f={'MPN': FFC_MPN, 'LCSC': 'C9136', 'Note': 'control board, BACK face (hand-soldered THT), vertical header pointing rearward'})
    j11 = s.part('Connector_Generic:Conn_01x12', 'J11', 'IDC 2x6 PWR', XK, YJ, mirror='y', fp=FFC_V, f={'MPN': FFC_MPN, 'LCSC': 'C9136', 'Note': 'power board, top face, vertical header on the USB-side island'})
    j10.fpos = {'Reference': (XJ, YJ - 20.5, 'center'), 'Value': (XJ, YJ + 20.5, 'center')}
    j11.fpos = {'Reference': (XK, YJ - 20.5, 'center'), 'Value': (XK, YJ + 20.5, 'center')}

    def side(j, sgn, suffix, flags):
        p = {n: j.pin(str(n)) for n in range(1, 13)}
        col = lambda nm: C_PROT if 'LOAD_OFF' in nm else C_SPI
        for n in (4, 5, 6, 7, 8, 9):
            nm = LINK_PINS[n]
            s.stub(p[n], nm + suffix, 'L' if sgn < 0 else 'R', shape=LINK_SHAPE[nm], length=14, color=col(nm))
        # VBUS on pins 1 and 2: short vertical tie, rail above
        xv = p[1][0] + sgn * 8
        s.wire(p[1], (xv, p[1][1]), color=C_PWR); s.wire(p[2], (xv, p[2][1]), color=C_PWR); s.wire((xv, p[1][1]), (xv, p[2][1]), color=C_PWR)
        s.wire((xv, p[1][1]), (xv, p[1][1] - 6), color=C_PWR); s.rail('VBUS' + suffix, xv, p[1][1] - 6)
        # +3V3 on pin 3: out past the signal labels, rail above
        x3 = p[3][0] + sgn * 22
        s.wire(p[3], (x3, p[3][1]), color=C_PWR); s.wire((x3, p[3][1]), (x3, p[3][1] - 6), color=C_PWR); s.rail('+3V3' + suffix, x3, p[3][1] - 6)
        # DGND on pins 10 to 12: vertical tie, rail below
        xg = p[10][0] + sgn * 8
        for n in (10, 11, 12):
            s.wire(p[n], (xg, p[n][1]))
        s.wire((xg, p[10][1]), (xg, p[12][1])); s.wire((xg, p[12][1]), (xg, p[12][1] + 6)); s.rail('DGND' + suffix, xg, p[12][1] + 6)
        return p

    pj = side(j10, -1, '', False)
    pk = side(j11, +1, '_LK', True)
    # the J11-side rails are driven only by connector pins: declare them with power flags
    for i, nm in enumerate(('VBUS_LK', '+3V3_LK', 'DGND_LK')):
        x = XK + 44 + i * 16
        if 'GND' in nm:
            s.rail('FLAG', x, YJ - 40); s.wire((x, YJ - 40), (x, YJ - 32)); s.rail(nm, x, YJ - 32)
        else:
            s.rail(nm, x, YJ - 40); s.wire((x, YJ - 40), (x, YJ - 32)); s.rail('FLAG', x, YJ - 32, rot=180)
    s.note('power flags: these three rails exist only through J11', XK + 36, YJ - 20)
    # the cable: one dashed line per conductor, pin n to pin n
    for n in range(1, 13):
        s.polyline([(XJ + 4, pj[n][1]), (XK - 4, pk[n][1])], width=0.25, dash=True, color=(120, 120, 120))
    cbl = s.part('dcload:FFC_CABLE_12', 'CBL1', 'IDC ribbon 2x6, ~80 mm', (XJ + XK) / 2, YJ - 36, in_bom=True, on_board=False,
                 f={'MPN': '12-way 1.27 mm ribbon, about 80 mm, two 2x6 IDC sockets (FC-12P type, LCSC C65556 or AliExpress), pin 1 to pin 1'})
    cbl.fpos = {'Reference': ((XJ + XK) / 2, YJ - 42.5, 'center'), 'Value': ((XJ + XK) / 2, YJ - 29.5, 'center')}
    s.note('Pins 1 2 VBUS   3 +3V3   4 SCK   5 MOSI   6 MISO   7 /CS_DAC   8 /CS_ADC   9 LOAD_OFF   10 11 12 DGND.\n'
           'The two boards are separate nets in the PCB (no ratsnest across the V-score): J11-side nets carry the _LK\n'
           'suffix and CBL1 is a BOM line only. The DC-DC and the isolator sit on the power board, so the cable carries\n'
           'nothing isolated and nothing analog; 2 MHz SPI over 80 mm of ribbon needs no termination. Keyed 2x6 box\n'
           'headers (BOOMELE 2.54-2*6P, C9136, both vertical): J10 is hand-soldered on the BACK face of the control board\n'
           'so the ribbon leaves rearward, folds once and plugs into J11 from above on the power board. Check pin 1 to\n'
           'pin 1 with a meter on the first pair; if the key makes that impossible, re-crimp one socket the other way.', XJ - 36, YJ + 54)
    s.end_block()
    return s


# ======================================================================= root
SHEETS = [('USB & Power', 'sheets/usb_power.kicad_sch', usb_power), ('MCU', 'sheets/mcu.kicad_sch', mcu), ('Front Panel UI', 'sheets/ui.kicad_sch', ui),
          ('Board Link', 'sheets/board_link.kicad_sch', board_link), ('Isolated Interface', 'sheets/iso_interface.kicad_sch', iso_interface),
          ('Setpoint & CV', 'sheets/setpoint_cv.kicad_sch', setpoint_cv), ('Sense', 'sheets/sense.kicad_sch', sense),
          ('Protection', 'sheets/protection.kicad_sch', protection), ('Power Path', 'sheets/power_path.kicad_sch', power_path)]
NETCOL = {'USB_DM': C_USB, 'USB_DP': C_USB, 'SPI1_SCK': C_SPI, 'SPI1_MOSI': C_SPI, 'SPI1_MISO': C_SPI, '~{CS_DAC}': C_SPI, '~{CS_ADC}': C_SPI,
          'SPI1_SCK_LK': C_SPI, 'SPI1_MOSI_LK': C_SPI, 'SPI1_MISO_LK': C_SPI, '~{CS_DAC}_LK': C_SPI, '~{CS_ADC}_LK': C_SPI, 'LOAD_OFF_LK': C_PROT,
          'LOAD_OFF': C_PROT, 'LOAD_OFF_ISO': C_PROT, 'KILL': C_PROT, 'OTP_GATE': C_PROT, 'OFF_GATE': C_PROT,
          'LOAD_CTRL': C_SET, 'CV_SET': C_SET, 'VSET': C_SET, 'VSET_MON': C_SET, 'ISEN_ADC': C_MEAS, 'VSEN_ADC': C_MEAS, 'VSEN_OA': C_MEAS, 'VSEN_OA_OVP': C_MEAS,
          'TEMP_MON': C_MEAS, 'AVG': C_MEAS, 'SENSE_P': C_MEAS, 'SENSE_N': C_MEAS, 'DRAIN': C_HI}
G = 1.27


def root_sheet():
    """Page 1 as a block diagram: every sheet is a block, every connection a wire between sheet pins (no net labels).
    Signal flow left to right: USB-C and panel -> MCU -> ribbon -> barrier -> isolator / DAC / ADC -> set-point, sense, protection ->
    the four channels (daisy-chained) and the power path. The channel row and the column sit under the same four nets as before."""
    root = S('DC Electronic Load Rev E: block diagram',
             'Control board + power board on one 2-layer panel, isolated, USB-C powered. 150 W, 0.6 - 58 V, 0 - 10.1 A. Hardware CC and CV, firmware CR / CP / battery. OLED + encoder UI, USB CDC / DFU, SCPI. JLCPCB / LCSC parts.',
             extra=('Each block is a sheet (page number under its name); every line is a wire between sheet pins, colour-coded by net class (key bottom left). Power rails are global symbols on the sheets.',
                    'The analog stage is the Rev C design re-simulated with the TLV9154 (../simulation/rev_e); check_netlist_reve.py proves the netlist against deck 06.'))
    root.root = ROOT_UUID
    page = [2]
    fn_of = {name: (fname, fn) for name, fname, fn in SHEETS}
    built, ch_uuids = [], []

    def blk(name, x, y, w, h, pins, fname=None, show_file=True):
        u = root.add_sheet(name, fname or fn_of[name][0], x, y, w, h, pins, page[0], show_file=show_file); page[0] += 1
        if fname is None:
            built.append((fn_of[name][0], fn_of[name][1], u))
        return u

    def W(*pts, net=None, width=0):
        root.wire(*pts, color=NETCOL.get(net), width=width)

    P = lambda i: 46.99 + 5.08 * i          # pin rows of the top band
    Q = lambda j: 101.6 + 5.08 * j          # pin rows of the UI band
    usb_pins = ['USB_DM', 'USB_DP', 'CC1_SENSE', 'CC2_SENSE', 'FAN_EN', 'FAN_PWM', 'FAN_TACH']
    usb_shape = ['bidirectional', 'bidirectional', 'output', 'output', 'input', 'input', 'output']
    ui_pins = ['I2C_SCL', 'I2C_SDA', 'LED_ON', 'LED_FAULT', 'ENC_A', 'ENC_B', 'ENC_SW', 'BTN_ON', 'BTN_MODE', 'BTN_MENU']
    ui_shape = ['bidirectional', 'bidirectional', 'input', 'input', 'output', 'output', 'output', 'output', 'output', 'output']
    spi = ['SPI1_SCK', 'SPI1_MOSI', 'SPI1_MISO', '~{CS_DAC}', '~{CS_ADC}', 'LOAD_OFF']
    spi_shape = ['input', 'input', 'output', 'input', 'input', 'input']           # seen from the receiving side
    flip = {'input': 'output', 'output': 'input', 'bidirectional': 'bidirectional', 'passive': 'passive'}
    # ------------------------------------------------------------------ USB side
    root.begin_block('USB SIDE  (DGND, earth-referenced through the PC)', FILL_D)
    X_USB, X_MCU, X_BL = 25.4, 80.01, 132.08
    W_USB, W_MCU, W_BL = 38.1, 41.91, 38.1
    blk('USB & Power', X_USB, 41.91, W_USB, 41.91, [(n, s, 'R', P(i)) for i, (n, s) in enumerate(zip(usb_pins, usb_shape))])
    blk('Front Panel UI', X_USB, 96.52, W_USB, 58.42, [(n, s, 'R', Q(j)) for j, (n, s) in enumerate(zip(ui_pins, ui_shape))])
    blk('MCU', X_MCU, 41.91, W_MCU, 113.03,
        [(n, flip[s], 'L', P(i)) for i, (n, s) in enumerate(zip(usb_pins, usb_shape))] + [(n, flip[s], 'L', Q(j)) for j, (n, s) in enumerate(zip(ui_pins, ui_shape))] +
        [(n, flip[s], 'R', P(i)) for i, (n, s) in enumerate(zip(spi, spi_shape))])
    blk('Board Link', X_BL, 41.91, W_BL, 38.1, [(n, s, 'L', P(i)) for i, (n, s) in enumerate(zip(spi, spi_shape))] + [(n + '_LK', flip[s], 'R', P(i)) for i, (n, s) in enumerate(zip(spi, spi_shape))])
    for i, n in enumerate(usb_pins):
        W((X_USB + W_USB, P(i)), (X_MCU, P(i)), net=n)
    for j, n in enumerate(ui_pins):
        W((X_USB + W_USB, Q(j)), (X_MCU, Q(j)), net=n)
    for i, n in enumerate(spi):
        W((X_MCU + W_MCU, P(i)), (X_BL, P(i)), net=n)
    root.end_block()
    # ------------------------------------------------------------------ isolated side
    root.begin_block('ISOLATED ANALOG SIDE  (AGND = DUT minus, floats with the DUT)', FILL_A)
    X_ISO, W_ISO = 186.69, 40.64
    X_COL, W_COL = 248.92, 40.64
    X_R = X_COL + W_COL                                   # 289.56, right edge of the column
    Y_LOFF, Y_TMON, Y_VSET, Y_LCTL, Y_CVS, Y_ISEN, Y_VSEN = 46.99, 52.07, 105.41, 110.49, 115.57, 154.94, 160.02
    Y_KILL, Y_DRAIN, Y_VSETO, Y_AVG = 46.99, 52.07, 125.73, 185.42
    X_OTP, X_OFF, X_VOA, X_SP, X_SN = 269.24, 276.86, 284.48, 256.54, 264.16
    blk('Isolated Interface', X_ISO, 41.91, W_ISO, 127.0,
        [(n + '_LK', s, 'L', P(i)) for i, (n, s) in enumerate(zip(spi, spi_shape))] +
        [('LOAD_OFF_ISO', 'output', 'R', Y_LOFF), ('TEMP_MON', 'input', 'R', Y_TMON), ('VSET', 'input', 'R', Y_VSET), ('LOAD_CTRL', 'output', 'R', Y_LCTL),
         ('CV_SET', 'output', 'R', Y_CVS), ('ISEN_ADC', 'input', 'R', Y_ISEN), ('VSEN_ADC', 'input', 'R', Y_VSEN)])
    blk('Protection', X_COL, 41.91, W_COL, 30.48,
        [('LOAD_OFF_ISO', 'input', 'L', Y_LOFF), ('TEMP_MON', 'output', 'L', Y_TMON), ('KILL', 'output', 'R', Y_KILL), ('DRAIN', 'input', 'R', Y_DRAIN),
         ('OTP_GATE', 'output', 'B', X_OTP), ('OFF_GATE', 'output', 'B', X_OFF), ('VSEN_OA', 'input', 'B', X_VOA)])
    blk('Setpoint & CV', X_COL, 97.79, W_COL, 44.45,
        [('OTP_GATE', 'input', 'T', X_OTP), ('OFF_GATE', 'input', 'T', X_OFF), ('VSEN_OA_OVP', 'output', 'T', X_VOA),
         ('VSET_MON', 'output', 'L', Y_VSET), ('LOAD_CTRL', 'input', 'L', Y_LCTL), ('CV_SET', 'input', 'L', Y_CVS),
         ('VSET', 'bidirectional', 'R', Y_VSETO), ('VSEN_OA', 'input', 'B', X_VOA)])
    blk('Sense', X_COL, 149.86, W_COL, 39.37,
        [('VSEN_OA', 'output', 'T', X_VOA), ('ISEN_ADC', 'output', 'L', Y_ISEN), ('VSEN_ADC', 'output', 'L', Y_VSEN), ('AVG', 'input', 'R', Y_AVG),
         ('SENSE_P', 'input', 'B', X_SP), ('SENSE_N', 'input', 'B', X_SN)])
    X_PP, W_PP, Y_ROW, H_ROW = 248.92, 35.56, 199.39, 36.83
    blk('Power Path', X_PP, Y_ROW, W_PP, 36.83, [('SENSE_P', 'output', 'T', X_SP), ('SENSE_N', 'output', 'T', X_SN), ('DRAIN', 'passive', 'R', 220.98)])
    # the four channels, daisy-chained
    X_CH0, W_CH, PITCH = 295.91, 20.32, 24.13
    ch_rows = [('KILL', 'input', 205.74), ('VSET', 'input', 210.82), ('AVG', 'output', 215.9), ('DRAIN', 'passive', 220.98)]
    for n in range(4):
        x = X_CH0 + PITCH * n
        u = blk('Channel %d' % (n + 1), x, Y_ROW, W_CH, H_ROW, [(nm, sh, 'L', y) for nm, sh, y in ch_rows] + [(nm + '_T', sh, 'R', y) for nm, sh, y in ch_rows],
                fname='sheets/channel.kicad_sch', show_file=(n == 0))
        ch_uuids.append((n + 1, u))
        if n < 3:
            for nm, sh, y in ch_rows:
                W((x + W_CH, y), (x + PITCH, y), net=nm, width=0.6 if nm == 'DRAIN' else 0)
    X_CH4R = X_CH0 + PITCH * 3 + W_CH                      # 388.62
    for nm, sh, y in ch_rows:
        if nm != 'DRAIN':
            root.nc(X_CH4R, y)
    # -- wires: isolator to the column
    for y, n in ((Y_LOFF, 'LOAD_OFF_ISO'), (Y_TMON, 'TEMP_MON'), (Y_VSET, 'VSET_MON'), (Y_LCTL, 'LOAD_CTRL'), (Y_CVS, 'CV_SET'), (Y_ISEN, 'ISEN_ADC'), (Y_VSEN, 'VSEN_ADC')):
        W((X_ISO + W_ISO, y), (X_COL, y), net=n)
    # -- wires inside the column (top / bottom pins)
    W((X_OTP, 72.39), (X_OTP, 97.79), net='OTP_GATE'); W((X_OFF, 72.39), (X_OFF, 97.79), net='OFF_GATE'); W((X_VOA, 72.39), (X_VOA, 97.79), net='VSEN_OA')
    W((X_VOA, 142.24), (X_VOA, 149.86), net='VSEN_OA')
    W((X_SP, 189.23), (X_SP, Y_ROW), net='SENSE_P'); W((X_SN, 189.23), (X_SN, Y_ROW), net='SENSE_N')
    # -- the four channel nets: KILL and VSET drop down the right of the column, AVG comes back up, DRAIN in from the power path
    X_AVG, X_VS, X_KL, X_DR = 290.83, 292.1, 293.37, 391.16
    W((X_R, Y_KILL), (X_KL, Y_KILL), (X_KL, 205.74), (X_CH0, 205.74), net='KILL')
    W((X_R, Y_VSETO), (X_VS, Y_VSETO), (X_VS, 210.82), (X_CH0, 210.82), net='VSET')
    W((X_R, Y_AVG), (X_AVG, Y_AVG), (X_AVG, 215.9), (X_CH0, 215.9), net='AVG')
    W((X_PP + W_PP, 220.98), (X_CH0, 220.98), net='DRAIN', width=0.6)
    W((X_CH4R, 220.98), (X_DR, 220.98), (X_DR, Y_DRAIN), (X_R, Y_DRAIN), net='DRAIN', width=0.6)
    root.end_block()
    # ------------------------------------------------------------------ cable and barrier, drawn over the blocks
    for i, n in enumerate(spi):
        W((X_BL + W_BL, P(i)), (X_ISO, P(i)), net=n + '_LK')
    root.barrier(176.53, 36.83, 250.19)
    root.text('ISOLATION BARRIER, 4 mm', 175.2, 122, size=FS_SUB, bold=True, angle=90, color=C_BAR)
    # ------------------------------------------------------------------ key and reading guide (bottom left, under the MCU)
    lx, ly = 25.4, 166
    root.text('NET COLOUR KEY', lx, ly, size=FS_SUB, bold=True, color=(0, 50, 120))
    items = [(C_HI, 'DUT current path', 0.6), (C_SET, 'set-point (LOAD_CTRL, V_SET, CV_SET)', 0), (C_MEAS, 'measurement (AVG, ISEN, VSEN, V_NTC)', 0),
             (C_PROT, 'protection (KILL, OTP, OFF, LOAD_OFF)', 0), (C_SPI, 'isolated SPI', 0), (C_USB, 'USB data', 0), (C_PWR, 'supply rails (on the sheets)', 0), (C_BAR, 'isolation barrier', -1)]
    for i, (col, txt, wd) in enumerate(items):
        cx, cy = lx + (i // 4) * 72, ly + 5 + (i % 4) * 4.5
        root.polyline([(cx, cy - 0.7), (cx + 8, cy - 0.7)], width=0.7 if wd < 0 else (wd or 0.3), dash=wd < 0, color=col)
        root.text(txt, cx + 11, cy, size=1.8)
    root.note('How to read this page: signals flow left to right. The 12-way ribbon (page 5)\n'
              'carries the SPI and the 5 V / 3.3 V rails from the control board to the power board;\n'
              'the isolator, DAC and ADC (page 6) straddle the barrier. V_SET (page 7) is the one\n'
              'node the four channels follow; KILL (page 9) stops them; the source-node average AVG\n'
              'returns to the sense amplifier (page 8); DRAIN comes from the terminals (page 10) and\n'
              'ends at the dropout comparator. The channels (pages 11-14, sheets/channel.kicad_sch)\n'
              'are drawn as a chain: a *_T pin is the same net leaving on the right. PGND / AGND /\n'
              'DGND and the rails are global power symbols on the sheets.', lx, 238)
    root.translate(0, 10.16)         # block titles clear of the page header; the frames stay out of the title-block corner
    return root, built, ch_uuids


def finish(sh, name, centre=True):
    if centre:
        sh.centre_on_sheet()
    errs = sh.lint()
    for e in errs:
        print('  LINT %s: %s' % (name, e))
    if sh.crossings:
        print('  %s: %d wire crossing(s) drawn with hop-overs: %s' % (name, len(sh.crossings), sh.crossings[:6]))
    return errs


def main():
    os.makedirs(os.path.join(PDIR, 'sheets'), exist_ok=True)
    root, built, ch_uuids = root_sheet()
    nerr = 0
    for fname, fn, u in built:
        sh = fn(); sh.instances = [('/%s/%s' % (ROOT_UUID, u), {'n': ''})]
        nerr += len(finish(sh, fname))
        open(os.path.join(PDIR, fname), 'w').write(sh.render())
    sh = channel()
    sh.instances = [('/%s/%s' % (ROOT_UUID, u), {'n': n}) for n, u in ch_uuids]
    nerr += len(finish(sh, 'channel'))
    open(os.path.join(PDIR, 'sheets/channel.kicad_sch'), 'w').write(sh.render())
    nerr += len(finish(root, 'root', centre=False))
    open(os.path.join(PDIR, PROJ + '.kicad_sch'), 'w').write(root.render())
    open(os.path.join(PDIR, 'fp-lib-table'), 'w').write('(fp_lib_table\n\t(version 7)\n\t(lib (name "dcload")(type "KiCad")(uri "${KIPRJMOD}/../libraries/footprints/dcload.pretty")(options "")(descr "DC Load project footprints"))\n)\n')
    open(os.path.join(PDIR, 'sym-lib-table'), 'w').write('(sym_lib_table\n\t(version 7)\n\t(lib (name "dcload")(type "KiCad")(uri "${KIPRJMOD}/../libraries/symbols/dcload.kicad_sym")(options "")(descr "DC Load project symbols"))\n)\n')
    syms = []
    for k, v in CUSTOM.items():
        c = copy.deepcopy(v); c[1] = Str(k.split(':')[1]); syms.append(c)
    open(os.path.join(HERE, '..', 'libraries', 'symbols', 'dcload.kicad_sym'), 'w').write(
        dump(['kicad_symbol_lib', ['version', 20251024], ['generator', Str('kgen')], ['generator_version', Str('10.0')]] + syms) + '\n')
    pro = os.path.join(PDIR, PROJ + '.kicad_pro')
    d = json.load(open(pro))
    d['sheets'] = [[ROOT_UUID, 'Root']]
    d.setdefault('meta', {})['filename'] = PROJ + '.kicad_pro'
    d.setdefault('schematic', {}).setdefault('drawing', {})['hop_over_size_choice'] = 1
    d['schematic']['hop_over_display'] = True
    # the block-diagram root uses pass-through pin names (VSET_MON, VSEN_OA_OVP, KILL_T ...) on the sub-sheets; KiCad would warn
    # 'multiple net names' for each of them, which is exactly the intent, so that check is switched off for this project
    d.setdefault('erc', {}).setdefault('rule_severities', {})['multiple_net_names'] = 'ignore'
    json.dump(d, open(pro, 'w'), indent=2)
    print('lint violations: %d' % nerr)
    sys.exit(1 if nerr else 0)


if __name__ == '__main__':
    main()
