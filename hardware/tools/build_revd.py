#!/usr/bin/env python3
"""Generates the DC Load Rev D schematic: ONE board, galvanically isolated, USB-C powered, local 7-segment UI.
KiCad 10, hierarchical. The analog stage is the verified Rev C design (../../simulation decks 01-06, same part values
except where the reference rail changed from 4.096 V to the ratiometric +5V_ISO, see ../../docs/rev_d_specification.md).

Readability rules used here (the Rev C complaint): outline font, 1.5 mm reference/value/label text, 2 mm block
titles, 4 mm sheet title, A4 sheets where the circuit fits and A3 only where it does not, colour-coded nets with a
legend on the root sheet, filled block frames with a title, and the isolation barrier drawn as a red dashed line.

usage: python3 build_revd.py        (writes ../rev_d/)"""
import os, json, copy, math
import kgen
from kgen import Sch, KLIB, flatten, set_prop, uid, find, find1, Str, dump

kgen.set_uid_namespace('dcload-revd-%d')
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = 'DC_Load_RevD'
PDIR = os.path.join(HERE, '..', 'rev_d')
ROOT_UUID = '7a1d2c3e-4f50-4b61-9c72-8d83e94fa5b6'
DATE, REV = '2026-10-31', 'D'

# ---------------------------------------------------------------- style
FONT = 'Arial'
FS_FIELD, FS_LABEL, FS_NOTE, FS_BLOCK, FS_TITLE, FS_SUB = 1.5, 1.5, 1.5, 2.2, 4.0, 1.8
# net colours (r, g, b): see the legend on the root sheet
C_PWR = (190, 0, 0)          # supply rails
C_HI = (140, 70, 0)          # high-current DUT path (drawn 0.6 mm wide)
C_SET = (170, 0, 170)        # set-point chain: LOAD_CTRL, V_SET, CV_SET
C_MEAS = (0, 80, 200)        # measurement: AVG, ISEN, VSEN, V_NTC
C_PROT = (220, 110, 0)       # protection: KILL, OTP_GATE, OFF_GATE, LOAD_OFF
C_SPI = (110, 0, 180)        # isolated SPI
C_USB = (0, 140, 140)        # USB data
C_BAR = (200, 0, 0)          # isolation barrier
C_FRAME = (120, 120, 120, 1)
FILL_D = (235, 242, 252, 0.35)   # digital / USB side blocks
FILL_A = (240, 250, 236, 0.35)   # isolated analog side blocks
FILL_N = (245, 245, 245, 0.35)   # neutral

R0603, R1206, R2512 = ('Resistor_SMD:R_%s_%sMetric' % s for s in (('0603', '1608'), ('1206', '3216'), ('2512', '6332')))
C0603, C0805, C1206 = ('Capacitor_SMD:C_%s_%sMetric' % s for s in (('0603', '1608'), ('0805', '2012'), ('1206', '3216')))
SOT23 = 'Package_TO_SOT_SMD:SOT-23'
SOD323 = 'Diode_SMD:D_SOD-323'
TO247 = 'Package_TO_SOT_THT:TO-247-3_Vertical'
TP = 'TestPoint:TestPoint_THTPad_D1.5mm_Drill0.7mm'
LED0603 = 'LED_SMD:LED_0603_1608Metric'
PH = 'Connector_PinHeader_2.54mm:PinHeader_1x%02d_P2.54mm_Vertical'


# ---------------------------------------------------------------- custom symbols
def lt_symbol(base, name, pinmap, descr, dsheet, fp):
    """Stock LM2902/LM2904 symbol with the LT1014 / LT1013 package pin numbers."""
    s = flatten(KLIB + 'Amplifier_Operational.kicad_sym', base, name)
    for u in find(s, 'symbol'):
        for p in find(u, 'pin'):
            n = find1(p, 'number')
            n[1] = Str(pinmap[str(n[1])])
    set_prop(s, 'Value', name); set_prop(s, 'Description', descr); set_prop(s, 'Datasheet', dsheet); set_prop(s, 'Footprint', fp)
    return s


LT1014 = lt_symbol('LM2902', 'LT1014', {'1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '10', '9': '11',
                                        '10': '12', '11': '13', '12': '14', '13': '15', '14': '16'},
                   'Quad precision op-amp, SW16 package pinout (pins 8, 9 NC)', 'https://www.analog.com/media/en/technical-documentation/data-sheets/10134fd.pdf',
                   'Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm')
LT1013 = lt_symbol('LM2904', 'LT1013_S8', {'1': '7', '2': '8', '3': '1', '4': '2', '5': '3', '6': '4', '7': '5', '8': '6'},
                   'Dual precision op-amp, S8 package: NOT the standard dual pinout (datasheet p. 2)',
                   'https://www.analog.com/media/en/technical-documentation/data-sheets/1013fd.pdf', 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm')


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
            ['property', Str('Value'), Str('B0512S-1WR3'), ['at', 0, -12.7, 0], F()],
            ['property', Str('Footprint'), Str('dcload:SIP-4_P2.54mm_DCDC_1W'), ['at', 0, 0, 0], H()],
            ['property', Str('Datasheet'), Str('https://www.mornsun-power.com/public/pdf/DCDC/B_S-1WR3.pdf'), ['at', 0, 0, 0], H()],
            ['property', Str('Description'), Str('Isolated DC-DC 1 W, 5 V in, 12 V / 84 mA out, 3 kVDC, SIP-4. PIN NUMBERS TO VERIFY against the datasheet'), ['at', 0, 0, 0], H()],
            ['symbol', Str('DCDC_ISO_1W_0_1'),
             ['rectangle', ['start', -12.7, 10.16], ['end', 12.7, -10.16], ['stroke', ['width', 0.254], ['type', 'default']], ['fill', ['type', 'background']]],
             ['polyline', ['pts', ['xy', 0, 9.0], ['xy', 0, -9.0]], ['stroke', ['width', 0.254], ['type', 'dash']], ['fill', ['type', 'none']]]],
            ['symbol', Str('DCDC_ISO_1W_1_1'),
             pin('power_in', '1', 'VIN+', -17.78, 5.08, 0), pin('power_in', '2', 'VIN-', -17.78, -5.08, 0),
             pin('power_out', '4', 'VOUT+', 17.78, 5.08, 180), pin('power_out', '3', 'VOUT-', 17.78, -5.08, 180)]]


CUSTOM = {'dcload:LT1014': LT1014, 'dcload:LT1013_S8': LT1013, 'dcload:DCDC_ISO_1W': dcdc_symbol()}
for _n in ('VBUS', '+3V3', '+12V_FAN', '+12V_ISO', '+5V_ISO', 'DGND', 'AGND', 'PGND'):
    CUSTOM['dcload:' + _n] = power_sym(_n)
PWRN = [0]


class S(Sch):
    def __init__(self, title, paper='A4', subtitle=''):
        super().__init__(PROJ, paper)
        self.title = dict(title=title, date=DATE, rev=REV, company='DC Load Box')
        self.face, self.fs_field, self.fs_label, self.fs_pin = FONT, FS_FIELD, FS_LABEL, FS_LABEL
        self.grid = 1.27
        self.W, self.H = (297, 210) if paper == 'A4' else (420, 297)
        self.header(title, subtitle)

    def header(self, title, subtitle):
        self.text(title, 12, 18, size=FS_TITLE, bold=True, color=(0, 40, 90))
        if subtitle:
            self.text(subtitle, 12, 22.5, size=FS_SUB, italic=True, color=(70, 70, 70))

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

    def res(self, ref, value, x, y, h=False, fp=R0603, tol=None, part='Device:R', f=None, **kw):
        f = dict(f or {})
        if tol:
            f['Tolerance'] = tol
        if h:
            p = self.part(part, ref, value, x, y, rot=90, fp=fp, f=f, **kw)
            p.fpos = {'Reference': (x, y - 2.3, 'center'), 'Value': (x, y + 2.6, 'center')}
        else:
            p = self.part(part, ref, value, x, y, fp=fp, f=f, **kw)
            p.fpos = {'Reference': (x + 2.2, y - 1.3), 'Value': (x + 2.2, y + 1.5)}
        return p

    def cap(self, ref, value, x, y, h=False, fp=C0603, **kw):
        return self.res(ref, value, x, y, h=h, fp=fp, part='Device:C', **kw)

    def dio(self, lib_id, ref, value, x, y, rot=0, fp=SOD323, **kw):
        p = self.part(lib_id, ref, value, x, y, rot=rot, fp=fp, **kw)
        if rot in (0, 180):
            p.fpos = {'Reference': (x, y - 2.5, 'center'), 'Value': (x, y + 2.9, 'center')}
        else:
            p.fpos = {'Reference': (x + 2.5, y - 1.3), 'Value': (x + 2.5, y + 1.5)}
        return p

    def fet(self, lib_id, ref, value, x, y, fp=SOT23, rot=0, **kw):
        p = self.part(lib_id, ref, value, x, y, fp=fp, rot=rot, **kw)
        p.fpos = {'Reference': (x + 4.5, y - 1.3), 'Value': (x + 4.5, y + 1.5)}
        return p

    def amp(self, lib_id, ref, value, x, y, unit, mirror=None, **kw):
        p = self.part(lib_id, ref, value, x, y, mirror=mirror, unit=unit, **kw)
        p.fpos = {'Reference': (x + 2.54, y - 6.5), 'Value': (x + 2.54, y + 6.9)}
        return p

    def ic(self, lib_id, ref, value, x, y, ry, fp=None, **kw):
        """big IC with Reference above and Value below the body, centred"""
        p = self.part(lib_id, ref, value, x, y, fp=fp, **kw)
        p.fpos = {'Reference': (x, y - ry, 'center'), 'Value': (x, y + ry, 'center')}
        return p

    def rail(self, name, x, y, rot=0):
        """power symbol. *GND point down, supplies up; rot 180 flips."""
        lib = {'FLAG': 'power:PWR_FLAG'}.get(name, 'dcload:' + name)
        self.ensure(lib)
        p = self.power(lib, x, y, rot=rot)
        PWRN[0] += 1
        p.ref = ('#FLG{n}%03d' if name == 'FLAG' else '#PWR{n}%03d') % PWRN[0]
        gnd = 'GND' in name
        off = 3.6 if gnd != (rot == 180) else -3.6
        if rot in (90, 270):
            p.fpos = {'Value': (x + (-4.5 if rot == 270 else 4.5) * (1 if gnd else -1), y, 'center')}
        else:
            p.fpos = {'Value': (x, y + off, 'center')}
        return p

    def tp(self, ref, name, x, y, **kw):
        p = self.part('Connector:TestPoint', ref, name, x, y, fp=TP, **kw)
        p.fpos = {'Reference': (x + 1.5, y - 4.6), 'Value': (x + 1.5, y - 2.6)}
        return p

    def hier(self, name, x, y, ang=180, shape='passive', color=None):
        self.label(name, x, y, angle=ang, kind='hier', shape=shape, color=color)

    def lab(self, name, x, y, ang=0, color=None):
        self.label(name, x, y, angle=ang, kind='label', color=color)

    def path(self, *pts, **kw):
        """wire through points, inserting an L corner (x first) when a segment is diagonal"""
        out = [pts[0]]
        for q in pts[1:]:
            a = out[-1]
            if a[0] != q[0] and a[1] != q[1]:
                out.append((q[0], a[1]))
            out.append(q)
        self.wire(*out, **kw)

    def pathv(self, *pts, **kw):
        """same, y first"""
        out = [pts[0]]
        for q in pts[1:]:
            a = out[-1]
            if a[0] != q[0] and a[1] != q[1]:
                out.append((a[0], q[1]))
            out.append(q)
        self.wire(*out, **kw)

    def note(self, s, x, y, size=FS_NOTE, **kw):
        self.text(s, x, y, size=size, **kw)

    def block(self, title, x1, y1, x2, y2, fill=FILL_N):
        self.rect(x1, y1, x2, y2, dash=False, width=0.25, color=C_FRAME, fill=fill)
        self.text(title, x1 + 1.5, y1 + 3.4, size=FS_BLOCK, bold=True, color=(0, 50, 120))

    def barrier(self, x, y1, y2, label=True):
        self.polyline([(x, y1), (x, y2)], width=0.7, dash=True, color=C_BAR)
        if label:
            self.text('GALVANIC ISOLATION BARRIER  -  4 mm minimum, no copper crosses it on any layer', x - 1.2, y2 - 2, size=FS_SUB, bold=True, angle=90, color=C_BAR)

    def stub(self, pt, name, side, kind='hier', shape='passive', length=7.62, color=None):
        """wire from a pin end to a label. side 'L' = label to the left, 'R' = to the right"""
        ex = pt[0] - length if side == 'L' else pt[0] + length
        self.wire(pt, (ex, pt[1]), color=color)
        if kind == 'hier':
            self.hier(name, ex, pt[1], ang=180 if side == 'L' else 0, shape=shape, color=color)
        else:
            self.lab(name, ex, pt[1], ang=180 if side == 'L' else 0, color=color)
        return (ex, pt[1])

    def pullup(self, ref, name, rail, x, y, value='10k', color=None):
        """stand-alone pull-up: rail on top, label on the bottom pin (connects by name)"""
        r = self.res(ref, value, x, y)
        self.rail(rail, x, r.pin('1')[1])
        self.wire(r.pin('2'), (x, r.pin('2')[1] + 2.54))
        self.hier(name, x, r.pin('2')[1] + 2.54, ang=270, color=color)
        return r


lft = lambda p: p.pin('1') if p.pin('1')[0] < p.pin('2')[0] else p.pin('2')
rgt = lambda p: p.pin('2') if p.pin('1')[0] < p.pin('2')[0] else p.pin('1')
top = lambda p: p.pin('1') if p.pin('1')[1] < p.pin('2')[1] else p.pin('2')
bot = lambda p: p.pin('2') if p.pin('1')[1] < p.pin('2')[1] else p.pin('1')

ZENER = 'Diode:BZX84Cxx'
BAT54S, BAT54C, D1N = 'Diode:BAT54S', 'Diode:BAT54C', 'Device:D'
Q2N, QP, QN5, QPFET = 'Transistor_FET:2N7002', 'Transistor_FET:IRF540N', 'Transistor_FET:AO3400A', 'Transistor_FET:AO3401A'


# ======================================================================= USB-C input, 3.3 V, fan boost, isolated supply
def usb_power():
    s = S('USB-C input, logic supply, fan supply, isolated analog supply', 'A3',
          'Everything left of the barrier is USB ground (DGND). The analog stage floats on AGND, which is the DUT minus terminal.')
    # ------------------------------------------------------------ block A: USB-C
    s.block('A   USB-C input: power, data, current advertisement (CC)', 15, 30, 150, 125, FILL_D)
    j = s.ic('Connector:USB_C_Receptacle_USB2.0_16P', 'J1', 'USB-C 16P', 50, 78, 27, fp='Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12',
             f={'MPN': 'HRO TYPE-C-31-M-12 (16 pin, USB 2.0)'})
    vb = j.pin('A4')
    s.wire(vb, (78, vb[1]), color=C_PWR); s.rail('VBUS', 78, vb[1]); s.rail('FLAG', 68, vb[1])
    cc1, cc2 = j.pin('A5'), j.pin('B5')
    s.wire(cc1, (120, cc1[1])); s.hier('CC1_SENSE', 120, cc1[1], ang=0, shape='output')
    s.wire(cc2, (92, cc2[1])); s.hier('CC2_SENSE', 92, cc2[1], ang=0, shape='output')
    r1 = s.res('R1', '5.1k', 112, cc1[1] + 3.81, tol='1%'); s.rail('DGND', 112, bot(r1)[1])
    r2 = s.res('R2', '5.1k', 84, cc2[1] + 3.81, tol='1%'); s.rail('DGND', 84, bot(r2)[1])
    # D+ / D- pairs joined, then down and across to the ESD diode
    dp1, dp2, dm1, dm2 = j.pin('A6'), j.pin('B6'), j.pin('A7'), j.pin('B7')
    s.wire(dp1, (70, dp1[1]), (70, dp2[1]), dp2, color=C_USB); s.wire(dm1, (72, dm1[1]), (72, dm2[1]), dm2, color=C_USB)
    esd = s.part('Power_Protection:USBLC6-2SC6', 'D1', 'USBLC6-2SC6', 95, 100)
    esd.fpos = {'Reference': (103, 94.5), 'Value': (103, 97)}
    s.wire((70, dp2[1]), (70, 104), (86, 104), (86, esd.pin('3')[1]), esd.pin('3'), color=C_USB)
    s.wire((72, dm2[1]), (72, esd.pin('1')[1]), esd.pin('1'), color=C_USB)
    s.wire(esd.pin('6'), (112, esd.pin('6')[1]), color=C_USB); s.hier('USB_DM', 112, esd.pin('6')[1], ang=0, shape='bidirectional', color=C_USB)
    s.wire(esd.pin('4'), (112, esd.pin('4')[1]), color=C_USB); s.hier('USB_DP', 112, esd.pin('4')[1], ang=0, shape='bidirectional', color=C_USB)
    s.rail('VBUS', esd.pin('5')[0], esd.pin('5')[1]); s.rail('DGND', esd.pin('2')[0], esd.pin('2')[1])
    s.nc(*j.pin('A8')); s.nc(*j.pin('B8'))
    g, sh = j.pin('A1'), j.pin('SH')
    s.wire(g, (g[0], 109), (62, 109)); s.rail('DGND', g[0], 109); s.rail('FLAG', 62, 109)
    s.wire(sh, (sh[0], 109)); s.rail('DGND', sh[0], 109)
    s.note('CC1 / CC2: 5.1k pull-downs = USB-C sink (UFP). The MCU reads the CC voltage to learn the source limit:\n'
           '0.4 V = 500 mA (legacy / USB 2.0 source), 0.9 V = 1.5 A, 1.7 V = 3 A. Below 1.5 A the firmware keeps the fan slow and limits power to 55 W.\n'
           'Shield to DGND directly: the enclosure, if metal, is on the USB side. The DUT terminals and heatsink hardware must not touch it.', 18, 123)
    # ------------------------------------------------------------ block B: 3.3 V
    s.block('B   Logic supply 3.3 V', 160, 30, 275, 80, FILL_D)
    u = s.ic('Regulator_Linear:AP2112K-3.3', 'U1', 'AP2112K-3.3', 200, 55, 10); u.fpos = {'Reference': (200, 44, 'center'), 'Value': (200, 47, 'center')}
    vin, en, gnd, vout = u.pin('1'), u.pin('3'), u.pin('2'), u.pin('5')
    s.rail('VBUS', 180, vin[1] - 6); s.wire((180, vin[1] - 6), (180, vin[1]), vin, color=C_PWR)
    s.wire(en, (186, en[1]), (186, vin[1]))
    c = s.cap('C1', '1uF X7R', 180, vin[1] + 6); s.wire((180, vin[1]), top(c)); s.rail('DGND', 180, bot(c)[1])
    s.wire(vout, (230, vout[1]), color=C_PWR); s.rail('+3V3', 230, vout[1] - 6); s.wire((230, vout[1] - 6), (230, vout[1]), color=C_PWR)
    c = s.cap('C2', '1uF X7R', 222, vout[1] + 6); s.wire((222, vout[1]), top(c)); s.rail('DGND', 222, bot(c)[1])
    s.rail('DGND', gnd[0], gnd[1]); s.nc(*u.pin('4'))
    r = s.res('R3', '1k', 250, 52); s.rail('+3V3', 250, top(r)[1])
    d = s.part('Device:LED', 'D2', 'LED green', 250, 61, rot=90, fp=LED0603); d.fpos = {'Reference': (254, 59.5), 'Value': (254, 62.3)}
    s.wire(bot(r), d.pin('2')); s.rail('DGND', d.pin('1')[0], d.pin('1')[1])
    s.note('USB budget at 5 V: analog supply 0.12 A, MCU + isolator 0.06 A, displays up to 0.15 A, fan 0.45 A = 0.8 A.\n'
           'Needs a 1.5 A or 3 A USB-C source for 150 W (fan). A 500 mA source still runs everything but the fan.', 163, 73)
    # ------------------------------------------------------------ block C: fan supply
    s.block('C   Fan supply: 5 V to 12 V boost, high-side switch, 4-pin PWM fan', 160, 88, 405, 215, FILL_D)
    u = s.ic('Regulator_Switching:MT3608', 'U2', 'MT3608', 200, 150, 10); u.fpos = {'Reference': (200, 140.5, 'center'), 'Value': (209, 158)}
    pin_in, pen, sw, fb, pgnd = u.pin('5'), u.pin('4'), u.pin('1'), u.pin('3'), u.pin('2')
    y12 = 134
    s.rail('VBUS', 175, y12 - 6); s.wire((175, y12 - 6), (175, y12), (210.19, y12), color=C_PWR)
    s.wire((185, y12), (185, pin_in[1]), pin_in)
    c = s.cap('C3', '10uF X7R 10V', 170, y12 + 6, fp=C0805); s.wire((170, y12), (175, y12)); s.wire((170, y12), top(c)); s.rail('DGND', 170, bot(c)[1])
    l = s.part('Device:L', 'L1', '10uH 2A', 214, y12, rot=90, fp='Inductor_SMD:L_Bourns_SRN6045TA', f={'MPN': 'SRN6045TA-100M or CD54 10uH'})
    l.fpos = {'Reference': (214, y12 - 2.6, 'center'), 'Value': (214, y12 + 3.2, 'center')}
    s.wire(rgt(l), (220, y12)); s.wire(sw, (sw[0], 142), (220, 142), (220, y12))
    d = s.dio('Device:D_Schottky', 'D3', 'SS34', 226, y12, rot=180, fp='Diode_SMD:D_SMA')
    s.wire((220, y12), d.pin('2')); s.wire(d.pin('1'), (268, y12), color=C_PWR)
    s.rail('FLAG', 236, y12); s.rail('+12V_FAN', 268, y12)
    for i, (ref, val) in enumerate([('C4', '22uF 25V X5R'), ('C5', '22uF 25V X5R')]):
        c = s.cap(ref, val, 244 + i * 14, y12 + 6, fp=C1206); s.wire((244 + i * 14, y12), top(c)); s.rail('DGND', 244 + i * 14, bot(c)[1])
    rt = s.res('R4', '191k', 232, y12 + 6.27, tol='1%'); s.wire((232, y12), top(rt))
    s.wire(fb, (232, fb[1])); s.wire(bot(rt), (232, fb[1]))
    rb = s.res('R5', '10.0k', 232, fb[1] + 7.46, tol='1%'); s.wire((232, fb[1]), top(rb)); s.rail('DGND', 232, bot(rb)[1])
    s.rail('DGND', pgnd[0], pgnd[1]); s.nc(*u.pin('6'))
    s.wire(pen, (188, pen[1]), (188, 166), (176, 166)); s.hier('FAN_EN', 176, 166, ang=180)
    rpd = s.res('R6', '100k', 188, 171); s.wire((188, 166), top(rpd)); s.rail('DGND', 188, bot(rpd)[1])
    s.note('Vout = 0.6 V x (1 + 191k / 10k) = 12.06 V. 12 V at 0.3 A costs about 0.8 A from USB.\n'
           'EN low: the boost stops and the output sits at VBUS minus a diode (4.7 V); Q1 is then off, so the fan sees nothing.', 163, 196)
    # high-side P-FET switch, 2N7002 level shifter, fan connector
    qp = s.fet(QPFET, 'Q1', 'AO3401A', 316, 147.46, rot=270)
    qp.fpos = {'Reference': (320, 141), 'Value': (320, 143.6)}
    src, drn, gate = qp.pin('2'), qp.pin('3'), qp.pin('1')
    jf = s.part('Connector_Generic:Conn_01x04', 'J2', 'FAN 4-pin', 340, 150, fp='Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical',
                f={'Note': '1 GND  2 +12V  3 TACH  4 PWM (PC fan pinout)'})
    jf.fpos = {'Reference': (338, 142.5), 'Value': (338, 161.5)}
    p1, p2, p3, p4 = jf.pin('1'), jf.pin('2'), jf.pin('3'), jf.pin('4')
    s.wire(p1, (331, p1[1])); s.rail('DGND', 331, p1[1], rot=270)
    s.wire(drn, p2, color=C_PWR); s.rail('+12V_FAN', 300, p2[1]); s.wire((300, p2[1]), src, color=C_PWR)
    rpu = s.res('R7', '10k', 316, 116.19); s.rail('+12V_FAN', 316, top(rpu)[1])
    qn = s.fet(Q2N, 'Q2', '2N7002', 296, 128)
    s.wire(gate, (316, 120), (qn.pin('3')[0], 120), qn.pin('3'))
    s.rail('DGND', qn.pin('2')[0], qn.pin('2')[1])
    s.wire(qn.pin('1'), (282, qn.pin('1')[1])); s.hier('FAN_EN', 282, qn.pin('1')[1], ang=180)
    rpd2 = s.res('R8', '100k', 288, 134); s.wire((288, qn.pin('1')[1]), top(rpd2)); s.rail('DGND', 288, bot(rpd2)[1])
    # tach and pwm
    s.wire(p3, (326, p3[1]), (326, 164), (322, 164))
    rpu2 = s.res('R9', '10k', 322, 160.19); s.rail('+3V3', 322, top(rpu2)[1])
    rs = s.res('R10', '1k', 312, 164, h=True); s.wire((322, 164), rgt(rs)); s.wire(lft(rs), (300, 164)); s.hier('FAN_TACH', 300, 164, ang=180, shape='output')
    s.wire(p4, (330, p4[1]), (330, 186))
    qpwm = s.fet(Q2N, 'Q3', '2N7002', 327.46, 191.08)
    s.rail('DGND', qpwm.pin('2')[0], qpwm.pin('2')[1])
    s.wire(qpwm.pin('1'), (300, qpwm.pin('1')[1])); s.hier('FAN_PWM', 300, qpwm.pin('1')[1], ang=180)
    rpu3 = s.res('R11', '10k DNP', 322, 182.19, dnp=True); s.wire((330, 186), bot(rpu3)); s.rail('VBUS', 322, top(rpu3)[1])
    s.note('J2 follows the 4-pin PC fan standard: 1 GND, 2 +12 V, 3 tach (open collector, pulled to 3.3 V here), 4 PWM 25 kHz.\n'
           '2- and 3-wire fans use pins 1-3 and are on/off only. Q3 drives the PWM pin open-drain, so firmware inverts the duty cycle.\n'
           'R11 only for fans without an internal PWM pull-up.', 255, 208)
    # ------------------------------------------------------------ block D: isolated supply
    s.block('D   Isolated analog supply: 1 W DC-DC, 12 V filtered rail, 5 V reference rail', 15, 135, 150, 240, FILL_A)
    ps = s.ic('dcload:DCDC_ISO_1W', 'PS1', 'B0512S-1WR3', 60, 172, 14, f={'MPN': 'Mornsun B0512S-1WR3 (alt: Murata NXE1S0512MC)'})
    vip, vin_, vop, von = ps.pin('1'), ps.pin('2'), ps.pin('4'), ps.pin('3')
    s.rail('VBUS', 34, vip[1] - 6); s.wire((34, vip[1] - 6), (34, vip[1]), vip, color=C_PWR)
    s.wire((26, vip[1]), (34, vip[1]), color=C_PWR)
    c = s.cap('C6', '10uF X7R 10V', 26, vip[1] + 6, fp=C0805); s.wire((26, vip[1]), top(c)); s.rail('DGND', 26, bot(c)[1])
    s.wire(vin_, (34, vin_[1])); s.rail('DGND', 34, vin_[1])
    s.wire(vop, (96.19, vop[1]), color=C_PWR)
    c = s.cap('C7', '10uF X7R 25V', 86, vop[1] + 6, fp=C0805); s.wire((86, vop[1]), top(c)); s.rail('AGND', 86, bot(c)[1])
    rf = s.res('R12', '4.7R', 100, vop[1], h=True, fp=R1206); s.wire(rgt(rf), (134, vop[1]), color=C_PWR)
    s.rail('FLAG', 106, vop[1]); s.rail('+12V_ISO', 134, vop[1])
    for i, (ref, val, fp) in enumerate([('C8', '22uF 25V', C1206), ('C9', '100nF', C0603)]):
        x = 110 + i * 12
        c = s.cap(ref, val, x, vop[1] + 6, fp=fp); s.wire((x, vop[1]), top(c)); s.wire(bot(c), (x, 186))
    s.wire((110, 186), (122, 186)); s.rail('AGND', 116, 186)
    s.wire(von, (80, von[1]), (80, 186)); s.rail('AGND', 80, 186)
    # 5 V reference rail
    u = s.ic('Regulator_Linear:MCP1703Ax-500xxTT', 'U3', 'MCP1703A-5002', 100, 204, 10, f={'MPN': 'MCP1703AT-5002E/CB'}); u.fpos = {'Reference': (100, 196, 'center'), 'Value': (100, 219.5, 'center')}
    vi, vo, g = u.pin('3'), u.pin('2'), u.pin('1')
    s.wire((90, vop[1]), (90, vi[1]), vi, color=C_PWR); s.wire((84, vi[1]), (90, vi[1]))
    c = s.cap('C10', '1uF 25V', 84, vi[1] + 6); s.wire((84, vi[1]), top(c)); s.rail('AGND', 84, bot(c)[1])
    s.wire(vo, (138, vo[1]), color=C_PWR); s.rail('+5V_ISO', 138, vo[1])
    for i, (ref, val) in enumerate([('C11', '1uF'), ('C12', '100nF')]):
        x = 114 + i * 12
        c = s.cap(ref, val, x, vo[1] + 6); s.wire((x, vo[1]), top(c)); s.rail('AGND', x, bot(c)[1])
    s.rail('AGND', g[0], g[1])
    s.barrier(60, 140, 238, label=False)
    s.text('BARRIER', 58.5, 228, size=FS_SUB, bold=True, angle=90, color=C_BAR)
    s.note('PS1: unregulated. 12 V at full load, up to about 14 V at the 30 mA this board draws. Every part on +12V_ISO is rated 16 V or more.\n'
           'R12 / C8 filter the 100 kHz switching ripple (fc = 1.5 kHz) before it reaches the op-amps.\n'
           '+5V_ISO (MCP1703, 0.4 % typ) feeds the DAC and ADC logic and every threshold network. OTP, dropout, NTC-open and\n'
           'OVP thresholds are divider ratios of this same rail, so they do not depend on its absolute value.\n'
           'VERIFY the SIP-4 pin numbers of the DC-DC you buy before ordering the PCB (Mornsun and Murata differ).', 18, 237.5)
    # ------------------------------------------------------------ block E: star point
    s.block('E   Ground star point', 160, 222, 275, 250, FILL_A)
    nt = s.part('Device:NetTie_2', 'NT1', 'STAR', 215, 236, fp='NetTie:NetTie-2_SMD_Pad2.0mm')
    nt.fpos = {'Reference': (215, 232.5, 'center'), 'Value': (215, 239.5, 'center')}
    s.wire(nt.pin('1'), (205, 236), (205, 242)); s.rail('AGND', 205, 242)
    s.wire(nt.pin('2'), (225, 236), (225, 242)); s.rail('PGND', 225, 242); s.rail('FLAG', 230, 236)
    s.wire((225, 236), (230, 236))
    s.note('AGND (analog reference) meets PGND (DUT minus, source resistors) ONLY at NT1.\nPlace NT1 at the centre of the four Rs bottom pads: 1 mR between an Rs and NT1 is 10 mV at 10 A,\n4 % of the 256 mV set-point full scale.', 163, 262)
    s.note('Isolation: USB side (DGND) to analog side (AGND / PGND). Working voltage rating of this barrier: 150 V DC\n'
           '(IEC 60664-1 functional, PD2, material group IIIb: 1.6 mm creepage; IPC-2221B B2: 0.7 mm). Board rule: 4 mm.\n'
           'ISO7761 (5 kVrms, 8 mm) and the 3 kVDC DC-DC exceed it by far. Use it to float the load on a DUT referenced anywhere\n'
           'within 150 V of earth, not for mains-referenced work.', 285, 232)
    return s


# ======================================================================= MCU
def mcu():
    s = S('MCU: STM32G0B1RET6, USB device, SPI to the isolated analog stage, SPI to the display', 'A3',
          'Crystal-less: USB SOF trims the 48 MHz HSI. DFU over USB is in ROM (hold BOOT, tap RESET). Everything here is on DGND.')
    s.block('A   Microcontroller and pin assignment', 15, 30, 300, 275, FILL_D)
    X, Y = 150, 155
    u = s.ic('MCU_ST_STM32G0:STM32G0B1RETx', 'U4', 'STM32G0B1RET6', X, Y, 54, f={'MPN': 'STM32G0B1RET6'})
    # pin plan: (number, label, side, kind, shape, colour)
    H, L = 'hier', 'label'
    plan = {
        '17': ('CC1_SENSE', H, 'input', None), '18': ('CC2_SENSE', H, 'input', None),
        '21': ('~{CS_DAC}', H, 'output', C_SPI), '22': ('SPI1_SCK', H, 'output', C_SPI), '23': ('SPI1_MISO', H, 'input', C_SPI), '24': ('SPI1_MOSI', H, 'output', C_SPI),
        '27': ('~{CS_ADC}', H, 'output', C_SPI), '28': ('LOAD_OFF', H, 'output', C_PROT),
        '32': ('~{DISP_CS}', H, 'output', None), '33': ('SPI2_SCK', H, 'output', None), '35': ('SPI2_MOSI', H, 'output', None),
        '36': ('LED_STATUS', L, None, None), '37': ('UART_TX', L, None, None), '42': ('UART_RX', L, None, None),
        '43': ('USB_DM', H, 'bidirectional', C_USB), '44': ('USB_DP', H, 'bidirectional', C_USB),
        '45': ('SWDIO', L, None, None), '46': ('SWCLK_BOOT0', L, None, None),
        '57': ('ENC_SW', H, 'input', None), '58': ('ENC_A', H, 'input', None), '59': ('ENC_B', H, 'input', None),
        '60': ('I2C_SCL', L, None, None), '61': ('I2C_SDA', L, None, None), '62': ('FAN_TACH', H, 'input', None), '63': ('FAN_PWM', H, 'output', None),
        '13': ('BTN_ON', H, 'input', None), '14': ('BTN_MODE', H, 'input', None), '15': ('BTN_MENU', H, 'input', None),
        '25': ('FAN_EN', H, 'output', None), '12': ('NRST', L, None, None),
    }
    for n in sorted(set(nn for (uu, nn) in u.pins), key=lambda q: int(q)):
        p = u.pin(n)
        if n in ('6', '7', '8', '9'):
            continue
        if n in plan:
            name, kind, shape, col = plan[n]
            side = 'L' if p[0] < X else 'R'
            s.stub(p, name, side, kind=kind, shape=shape or 'passive', color=col, length=7.62 if kind == H else 15.24)
        else:
            s.nc(*p)
    vbat, vref, vdd, vss = u.pin('6'), u.pin('7'), u.pin('8'), u.pin('9')
    s.wire(vbat, (vbat[0], vbat[1] - 5), (vdd[0], vbat[1] - 5), vdd, color=C_PWR); s.rail('+3V3', vdd[0], vbat[1] - 5)
    s.wire(vref, (vref[0] - 8, vref[1]), (vref[0] - 8, vref[1] - 8), color=C_PWR); s.rail('+3V3', vref[0] - 8, vref[1] - 8)
    s.rail('DGND', vss[0], vss[1])
    s.note('Pin plan (STM32G0B1RET6, LQFP64)\n'
           'SPI1  PA5 SCK, PA6 MISO, PA7 MOSI, PA4 /CS DAC, PB0 /CS ADC, PB1 LOAD_OFF   (through the isolator)\n'
           'SPI2  PB13 SCK, PB15 MOSI, PB12 /CS = MAX7219 LOAD      (display chain, via 74AHCT125)\n'
           'TIM3  PB4 / PB5 encoder mode, PB3 encoder push          TIM17 PB9 fan PWM, PB8 fan tach (TIM16 capture)\n'
           'ADC   PA0 / PA1 = CC1 / CC2 (USB-C source current advertisement)\n'
           'USB   PA11 DM, PA12 DP (pins 43 / 44), crystal-less with CRS      USART1 PA9 / PA10 debug header      I2C1 PB6 / PB7 OLED header\n'
           'GPIO  PC0 ON/OFF, PC1 MODE, PC2 MENU buttons, PC4 FAN_EN, PC6 status LED\n'
           'Spare: PA2, PA3, PA8, PA15, PB2, PB10, PB11, PB14, PC3, PC5, PC7-PC15, PD0-PD9, PF0, PF1 (all NC)', 18, 262)
    # ------------------------------------------------------------ support circuits
    s.block('B   Decoupling', 310, 30, 405, 75, FILL_D)
    for i, (ref, val, fp) in enumerate([('C13', '4.7uF X7R', C0805), ('C14', '100nF X7R', C0603), ('C15', '100nF X7R', C0603),
                                        ('C16', '100nF X7R', C0603), ('C17', '100nF X7R', C0603), ('C18', '1uF X7R', C0603)]):
        x = 320 + i * 14
        c = s.cap(ref, val, x, 55, fp=fp); s.rail('+3V3', x, top(c)[1]); s.rail('DGND', x, bot(c)[1])
    s.note('One 100 nF per VDD pin pair, 1 uF + 100 nF at VREF+ (C17, C18). Place within 2 mm of the pins.', 313, 70)
    s.block('C   Reset, BOOT0 (DFU), SWD', 310, 82, 405, 150, FILL_D)
    sw = s.part('Switch:SW_Push', 'SW1', 'RESET', 330, 96, fp='Button_Switch_THT:SW_PUSH_6mm'); sw.fpos = {'Reference': (330, 91.5, 'center'), 'Value': (330, 100.5, 'center')}
    s.wire(sw.pin('1'), (316, 96)); s.lab('NRST', 316, 96, ang=180); s.wire(sw.pin('2'), (342, 96)); s.rail('DGND', 342, 96)
    c = s.cap('C19', '100nF', 320, 103); s.wire((320, 96), top(c)); s.rail('DGND', 320, bot(c)[1])
    sw = s.part('Switch:SW_Push', 'SW2', 'BOOT', 330, 118, fp='Button_Switch_THT:SW_PUSH_6mm'); sw.fpos = {'Reference': (330, 113.5, 'center'), 'Value': (330, 122.5, 'center')}
    r = s.res('R13', '1k', 344, 118, h=True); s.wire(sw.pin('2'), lft(r)); s.wire(rgt(r), (356, 118)); s.rail('+3V3', 356, 118)
    s.wire(sw.pin('1'), (318, 118)); s.lab('SWCLK_BOOT0', 318, 118, ang=180)
    jh = s.part('Connector_Generic:Conn_01x05', 'J3', 'SWD', 394, 118, fp=PH % 5, f={'Note': '1 +3V3  2 SWDIO  3 SWCLK  4 NRST  5 GND'})
    jh.fpos = {'Reference': (394, 110, 'center'), 'Value': (394, 127, 'center')}
    for n, name in (('2', 'SWDIO'), ('3', 'SWCLK_BOOT0'), ('4', 'NRST')):
        p = jh.pin(n); s.wire(p, (p[0] - 6, p[1])); s.lab(name, p[0] - 6, p[1], ang=180)
    p = jh.pin('1'); s.wire(p, (p[0] - 4, p[1]), (p[0] - 4, p[1] - 5)); s.rail('+3V3', p[0] - 4, p[1] - 5)
    p = jh.pin('5'); s.wire(p, (p[0] - 4, p[1]), (p[0] - 4, p[1] + 4)); s.rail('DGND', p[0] - 4, p[1] + 4)
    s.note('BOOT0 shares PA14 (SWCLK) on the STM32G0. Hold BOOT, tap RESET: the ROM bootloader enumerates as USB DFU.\n'
           'Once, with STM32CubeProgrammer, clear option bit nBOOT_SEL so the pin is honoured (factory default ignores it).', 313, 145)
    s.block('D   Debug UART, I2C expansion (OLED), status LED', 310, 158, 405, 230, FILL_D)
    ju = s.part('Connector_Generic:Conn_01x03', 'J4', 'UART 3V3', 394, 178, fp=PH % 3, f={'Note': '1 GND  2 TX  3 RX'})
    ju.fpos = {'Reference': (394, 172, 'center'), 'Value': (394, 184.5, 'center')}
    p = ju.pin('1'); s.wire(p, (p[0] - 4, p[1]), (p[0] - 4, p[1] - 4)); s.rail('DGND', p[0] - 4, p[1] - 4, rot=180)
    for n, name in (('2', 'UART_TX'), ('3', 'UART_RX')):
        p = ju.pin(n); s.wire(p, (p[0] - 6, p[1])); s.lab(name, p[0] - 6, p[1], ang=180)
    ji = s.part('Connector_Generic:Conn_01x04', 'J5', 'I2C OLED', 394, 200, fp=PH % 4, f={'Note': '1 GND  2 +3V3  3 SCL  4 SDA (SSD1306 module pinout)'})
    ji.fpos = {'Reference': (394, 193, 'center'), 'Value': (394, 208.5, 'center')}
    p = ji.pin('1'); s.wire(p, (p[0] - 4, p[1]), (p[0] - 4, p[1] - 4)); s.rail('DGND', p[0] - 4, p[1] - 4, rot=180)
    p = ji.pin('2'); s.wire(p, (p[0] - 8, p[1]), (p[0] - 8, p[1] - 6)); s.rail('+3V3', p[0] - 8, p[1] - 6)
    for n, name in (('3', 'I2C_SCL'), ('4', 'I2C_SDA')):
        p = ji.pin(n); s.wire(p, (p[0] - 12, p[1])); s.lab(name, p[0] - 12, p[1], ang=180)
    for i, name in enumerate(('I2C_SCL', 'I2C_SDA')):
        r = s.res('R%d' % (14 + i), '4.7k', 322 + i * 12, 198); s.rail('+3V3', 322 + i * 12, top(r)[1])
        s.wire(bot(r), (322 + i * 12, bot(r)[1] + 2.54)); s.lab(name, 322 + i * 12, bot(r)[1] + 2.54, ang=270)
    r = s.res('R16', '1k', 342, 165, h=True); s.wire(lft(r), (330, 165)); s.lab('LED_STATUS', 330, 165, ang=180)
    d = s.part('Device:LED', 'D4', 'LED blue', 352, 165, rot=180, fp=LED0603); d.fpos = {'Reference': (352, 161.2, 'center'), 'Value': (352, 169, 'center')}
    s.wire(rgt(r), d.pin('2')); s.wire(d.pin('1'), (360, 165)); s.rail('DGND', 360, 165)
    s.note('J5 takes a 0.96" SSD1306 module for menus and battery statistics; the 7-segment panel is the primary UI.', 313, 226)
    return s


# ======================================================================= front panel UI
def ui():
    s = S('Front panel: 3 x 4-digit 7-segment readouts, 8 status LEDs, encoder, 3 buttons', 'A3',
          'Two MAX7219 in a chain, fed through a 74AHCT125 level shifter (MAX7219 VIH is 3.5 V). Segment and digit nets connect by name.')
    s.block('A   Display drivers (5 V) and level shifter', 15, 30, 180, 222, FILL_D)
    seg = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'DP']
    segpin = {'A': '14', 'B': '16', 'C': '20', 'D': '23', 'E': '21', 'F': '15', 'G': '17', 'DP': '22'}
    digpin = {0: '2', 1: '11', 2: '6', 3: '7', 4: '3', 5: '10', 6: '5', 7: '8'}
    for k, (ref, y) in enumerate([('U5', 95), ('U6', 190)]):
        u = s.ic('Driver_LED:MAX7219', ref, 'MAX7219', 100, y, 33, fp='Package_SO:SOIC-24W_7.5x15.4mm_P1.27mm', f={'MPN': 'MAX7219CWG'})
        for sg in seg:
            s.stub(u.pin(segpin[sg]), 'S%d_%s' % (k + 1, sg), 'R', kind='label')
        for d in range(8):
            p = u.pin(digpin[d])
            if k == 1 and d >= 5:
                s.nc(*p)
            else:
                s.stub(p, 'D%d_%d' % (k + 1, d), 'R', kind='label')
        s.stub(u.pin('13'), 'DISP_CLK', 'L', kind='label'); s.stub(u.pin('12'), 'DISP_LOAD', 'L', kind='label')
        s.stub(u.pin('1'), 'DISP_DIN' if k == 0 else 'DISP_DOUT1', 'L', kind='label')
        if k == 0:
            s.stub(u.pin('24'), 'DISP_DOUT1', 'R', kind='label')
        else:
            s.nc(*u.pin('24'))
        r = s.res('R%d' % (17 + k), '33k', 78, u.pin('18')[1] - 7, tol='1%'); s.wire(u.pin('18'), (78, u.pin('18')[1]), bot(r)); s.rail('VBUS', 78, top(r)[1])
        vp, g = u.pin('19'), u.pin('4')
        s.wire(vp, (vp[0], vp[1] - 4), color=C_PWR); s.rail('VBUS', vp[0], vp[1] - 4); s.rail('DGND', g[0], g[1])
        c = s.cap('C%d' % (20 + k), '100nF', vp[0] + 28, vp[1] - 0.19); s.wire((vp[0], vp[1] - 4), (vp[0] + 28, vp[1] - 4), top(c), color=C_PWR); s.rail('DGND', vp[0] + 28, bot(c)[1])
    c = s.cap('C22', '10uF X7R 10V', 130, 48, fp=C0805); s.rail('VBUS', 130, top(c)[1]); s.rail('DGND', 130, bot(c)[1])
    s.note('ISET 33k: 16 mA peak per segment, 1/8 duty. Intensity register trims it further.', 18, 220)
    # level shifter
    bx, by = 55, 140
    for i, (inn, outn) in enumerate([('SPI2_MOSI', 'DISP_DIN'), ('SPI2_SCK', 'DISP_CLK'), ('~{DISP_CS}', 'DISP_LOAD')]):
        u = s.part('74xx:74AHCT125', 'U7', '74AHCT125', bx, by + i * 22, unit=i + 1, fp='Package_SO:SOIC-14_3.9x8.7mm_P1.27mm')
        u.fpos = {'Reference': (bx + 1, by + i * 22 - 6.5), 'Value': (bx + 1, by + i * 22 - 4)}
        s.stub(u.pin(('2', '5', '9')[i]), inn, 'L', kind='hier', shape='input', length=10)
        s.stub(u.pin(('3', '6', '8')[i]), outn, 'R', kind='label')
        oe = u.pin(('1', '4', '10')[i]); s.rail('DGND', oe[0], oe[1])
    u = s.part('74xx:74AHCT125', 'U7', '74AHCT125', bx, by + 66, unit=4, fp='Package_SO:SOIC-14_3.9x8.7mm_P1.27mm')
    u.fpos = {'Reference': (bx + 1, by + 66 - 6.5), 'Value': (bx + 1, by + 66 - 4)}
    s.rail('DGND', u.pin('12')[0] - 3, u.pin('12')[1], rot=270); s.wire(u.pin('12'), (u.pin('12')[0] - 3, u.pin('12')[1]))
    s.rail('DGND', u.pin('13')[0], u.pin('13')[1]); s.nc(*u.pin('11'))
    u = s.part('74xx:74AHCT125', 'U7', '74AHCT125', 30, 60, unit=5, fp='Package_SO:SOIC-14_3.9x8.7mm_P1.27mm')
    u.fpos = {'Reference': (33, 57), 'Value': (33, 60)}
    s.rail('VBUS', u.pin('14')[0], u.pin('14')[1]); s.rail('DGND', u.pin('7')[0], u.pin('7')[1])
    c = s.cap('C23', '100nF', 50, 60); s.rail('VBUS', 50, top(c)[1]); s.rail('DGND', 50, bot(c)[1])
    s.note('74AHCT125: TTL input thresholds, 5 V output. The spare gate is parked (input and /OE low).', 18, 216)
    # ------------------------------------------------------------ displays
    s.block('B   Readouts: VOLTS, AMPS, SET  (0.56" common-cathode, red)', 190, 30, 405, 215, FILL_D)
    disp = [('DS1', 'VOLTS', 1, 0), ('DS2', 'AMPS', 1, 4), ('DS3', 'SET', 2, 0)]
    dpin = {'a': '11', 'b': '7', 'c': '4', 'd': '2', 'e': '1', 'f': '10', 'g': '5', 'DPX': '3'}
    for i, (ref, name, drv, d0) in enumerate(disp):
        y = 62 + i * 52
        u = s.ic('Display_Character:CC56-12SRWA', ref, name, 300, y, 16, fp='Display_7Segment:CA56-12SRWA', f={'MPN': 'CC56-12SRWA or 5641AS (common cathode)'})
        for sg, pn in dpin.items():
            s.stub(u.pin(pn), 'S%d_%s' % (drv, 'DP' if sg == 'DPX' else sg.upper()), 'L', kind='label')
        for k in range(4):
            s.stub(u.pin(('12', '9', '8', '6')[k]), 'D%d_%d' % (drv, d0 + k), 'R', kind='label')
    s.note('Digit 1 is the left-most. VOLTS: 0.000 - 58.00, AMPS: 0.000 - 10.00 (ISEN 0.4 mA per ADC LSB), SET: the value being edited.\n'
           'CC56-12 pin numbers are from the KiCad symbol; check them against the display you buy (5641AS has the same pinout).', 193, 211)
    # ------------------------------------------------------------ status LEDs
    s.block('C   Status LEDs on U6 digit 4', 190, 222, 405, 258, FILL_D)
    names = ['CC', 'CV', 'CR', 'CP', 'BATT', 'ON', 'FAULT', 'REMOTE']
    for i, nm in enumerate(names):
        x = 206 + i * 24
        d = s.part('Device:LED', 'D%d' % (5 + i), nm, x, 237, rot=90, fp=LED0603); d.fpos = {'Reference': (x + 2.5, 235.6), 'Value': (x + 2.5, 238.6)}
        a, k = d.pin('2'), d.pin('1')
        s.wire(a, (a[0], a[1] - 2.54)); s.lab('S2_%s' % seg[i], a[0], a[1] - 2.54, ang=90)
        s.wire(k, (k[0], 248))
    s.wire((206, 248), (206 + 7 * 24, 248), (206 + 7 * 24 + 8, 248)); s.lab('D2_4', 206 + 7 * 24 + 8, 248)
    s.note('LED anode = segment A..DP, cathode = digit 4 of U6. ON is lit while the load sinks; FAULT for OTP / OVP / NTC-open; REMOTE when a host holds the instrument.', 193, 256)
    # ------------------------------------------------------------ encoder and buttons
    s.block('D   Encoder and buttons (MCU internal pull-ups on the buttons, RC on the encoder)', 15, 226, 180, 288, FILL_D)
    e = s.part('Device:RotaryEncoder_Switch', 'ENC1', 'PEC11L-4120K-S0020', 50, 244, fp='Rotary_Encoder:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm',
               f={'MPN': 'Bourns PEC11L-4120K-S0020'})
    e.fpos = {'Reference': (50, 236.8, 'center'), 'Value': (50, 251.8, 'center')}
    s.stub(e.pin('A'), 'ENC_A', 'L', shape='output', length=16)
    s.stub(e.pin('B'), 'ENC_B', 'L', shape='output', length=16)
    s.rail('DGND', e.pin('C')[0] - 3, e.pin('C')[1], rot=270); s.wire(e.pin('C'), (e.pin('C')[0] - 3, e.pin('C')[1]))
    s.stub(e.pin('S1'), 'ENC_SW', 'R', shape='output'); s.rail('DGND', e.pin('S2')[0] + 3, e.pin('S2')[1], rot=90); s.wire(e.pin('S2'), (e.pin('S2')[0] + 3, e.pin('S2')[1]))
    for i, name in enumerate(('ENC_A', 'ENC_B')):
        x = 108 + i * 24
        r = s.res('R%d' % (19 + i), '10k', x, 238); s.rail('+3V3', x, top(r)[1]); s.wire(bot(r), (x, 246)); s.hier(name, x, 246, ang=270, shape='output')
        c = s.cap('C%d' % (24 + i), '10nF', x + 9, 250); s.wire((x, 246), (x + 9, 246), top(c)); s.rail('DGND', x + 9, bot(c)[1])
    for i, (ref, name, lab) in enumerate([('SW3', 'ON/OFF', 'BTN_ON'), ('SW4', 'MODE', 'BTN_MODE'), ('SW5', 'MENU', 'BTN_MENU')]):
        x = 60 + i * 48
        sw = s.part('Switch:SW_Push', ref, name, x, 272, fp='Button_Switch_THT:SW_PUSH_6mm'); sw.fpos = {'Reference': (x, 267.5, 'center'), 'Value': (x, 276.5, 'center')}
        s.stub(sw.pin('1'), lab, 'L', shape='output', length=10); s.rail('DGND', sw.pin('2')[0] + 3, sw.pin('2')[1], rot=90); s.wire(sw.pin('2'), (sw.pin('2')[0] + 3, sw.pin('2')[1]))
    s.note('ON/OFF toggles the sink. MODE cycles CC / CV / CR / CP / BATT.\nMENU: limits, fan, calibration. Encoder push selects the digit.', 18, 286)
    return s


# ======================================================================= isolated interface
def iso_interface():
    s = S('Isolated interface: digital isolator, set-point DAC, readback ADC', 'A4',
          'SPI crosses the barrier. The DAC and ADC carry their own references, so no precision reference or trimmer is needed.')
    s.block('A   Digital isolator', 15, 30, 150, 135, FILL_N)
    u = s.ic('Isolator:ISO7761DW', 'U8', 'ISO7761DW', 82, 92, 25, f={'MPN': 'ISO7761DW (default-high outputs)'})
    left = [('2', 'SPI1_SCK', 'input', C_SPI), ('3', 'SPI1_MOSI', 'input', C_SPI), ('4', '~{CS_DAC}', 'input', C_SPI),
            ('5', '~{CS_ADC}', 'input', C_SPI), ('6', 'LOAD_OFF', 'input', C_PROT), ('7', 'SPI1_MISO', 'output', C_SPI)]
    for pn, name, sh, col in left:
        s.stub(u.pin(pn), name, 'L', shape=sh, length=12, color=col)
    right = [('15', 'SCK_ISO', C_SPI), ('14', 'MOSI_ISO', C_SPI), ('13', '~{CS_DAC}_ISO', C_SPI), ('12', '~{CS_ADC}_ISO', C_SPI),
             ('11', 'LOAD_OFF_ISO', C_PROT), ('10', 'MISO_ISO', C_SPI)]
    for pn, name, col in right:
        s.stub(u.pin(pn), name, 'R', kind='label', length=10, color=col)
    v1, g1, v2, g2 = u.pin('1'), u.pin('8'), u.pin('16'), u.pin('9')
    s.wire(v1, (v1[0], v1[1] - 5), color=C_PWR); s.rail('+3V3', v1[0], v1[1] - 5); s.rail('DGND', g1[0], g1[1])
    s.wire(v2, (v2[0], v2[1] - 5), color=C_PWR); s.rail('+5V_ISO', v2[0], v2[1] - 5); s.rail('AGND', g2[0], g2[1])
    c = s.cap('C27', '100nF', 60, 50); s.rail('+3V3', 60, top(c)[1]); s.rail('DGND', 60, bot(c)[1])
    c = s.cap('C28', '100nF', 104, 50); s.rail('+5V_ISO', 104, top(c)[1]); s.rail('AGND', 104, bot(c)[1])
    s.barrier(82, 33, 116, label=False)
    s.text('ISOLATION BARRIER', 80.5, 114, size=FS_SUB, bold=True, angle=90, color=C_BAR)
    s.wire((128, 106), (142, 106)); s.hier('LOAD_OFF_ISO', 142, 106, ang=0, shape='output', color=C_PROT); s.lab('LOAD_OFF_ISO', 128, 106, ang=180, color=C_PROT)
    for i, name in enumerate(('~{CS_DAC}', '~{CS_ADC}', 'LOAD_OFF')):
        s.pullup('R%d' % (21 + i), name, '+3V3', 24 + i * 12, 48, color=C_SPI if i < 2 else C_PROT)
    s.note('Side 1 = MCU (3.3 V), side 2 = analog (5 V). Five channels go to the analog side, MISO comes back.\n'
           'ISO7761 (no F suffix) outputs default HIGH when side 1 is unpowered or the input floats: chip selects stay\n'
           'de-asserted and LOAD_OFF_ISO is asserted, so the load is OFF until firmware says otherwise. R21-R23 give\n'
           'the same guarantee while the MCU is in reset. Propagation delay 11 ns: keep SPI at or below 2 MHz.', 18, 128)
    # ------------------------------------------------------------ DAC
    s.block('B   Set-point DAC: A = current ceiling, B = CV voltage', 160, 30, 285, 95, FILL_A)
    d = s.ic('Analog_DAC:MCP4822', 'U9', 'MCP4822', 215, 62, 20, fp='Package_SO:SOIC-8_3.9x4.9mm_P1.27mm', f={'MPN': 'MCP4822-E/SN'})
    for pn, name in (('3', 'SCK_ISO'), ('4', 'MOSI_ISO'), ('2', '~{CS_DAC}_ISO')):
        s.stub(d.pin(pn), name, 'L', kind='label', length=8, color=C_SPI)
    ld = d.pin('5'); s.wire(ld, (ld[0] - 20, ld[1])); s.rail('AGND', ld[0] - 20, ld[1], rot=270)
    s.stub(d.pin('8'), 'LOAD_CTRL', 'R', shape='output', length=12, color=C_SET)
    s.stub(d.pin('6'), 'CV_SET', 'R', shape='output', length=12, color=C_SET)
    vdd, vss = d.pin('1'), d.pin('7')
    s.wire(vdd, (vdd[0], vdd[1] - 4), color=C_PWR); s.rail('+5V_ISO', vdd[0], vdd[1] - 4); s.rail('AGND', vss[0], vss[1])
    c = s.cap('C29', '100nF', 240, 46); s.rail('+5V_ISO', 240, top(c)[1]); s.rail('AGND', 240, bot(c)[1])
    s.note('12 bit, internal 2.048 V reference, gain 2: 0 - 4.095 V in 1 mV steps.\n'
           'A: LOAD_CTRL, 2.5 A per volt = 2.44 mA per LSB. B: CV_SET in VSEN volts.\n'
           'Both outputs are 0 V after power-up (POR shutdown): no EEPROM surprise like the MCP4725.', 163, 92)
    # ------------------------------------------------------------ ADC
    s.block('C   Readback ADC: 16 bit, 4 channels', 160, 102, 285, 170, FILL_A)
    a = s.ic('Analog_ADC:ADS1118IDGS', 'U10', 'ADS1118', 220, 136, 20, fp='Package_SO:TSSOP-10_3x3mm_P0.5mm', f={'MPN': 'ADS1118IDGSR'}); a.fpos = {'Reference': (232, 122), 'Value': (220, 156, 'center')}
    for pn, name in (('1', 'SCK_ISO'), ('10', 'MOSI_ISO'), ('2', '~{CS_ADC}_ISO'), ('9', 'MISO_ISO')):
        s.stub(a.pin(pn), name, 'R', kind='label', length=8, color=C_SPI)
    s.stub(a.pin('4'), 'ISEN_ADC', 'L', shape='input', length=14, color=C_MEAS)
    s.stub(a.pin('5'), 'VSEN_ADC', 'L', shape='input', length=14, color=C_MEAS)
    s.stub(a.pin('6'), 'TEMP_MON', 'L', shape='input', length=14, color=C_MEAS)
    p = a.pin('7')
    r = s.res('R24', '1k', p[0] - 8, p[1], h=True); s.wire(p, rgt(r)); s.wire(lft(r), (p[0] - 20, p[1]), color=C_SET); s.hier('VSET', p[0] - 20, p[1], shape='input', color=C_SET)
    c = s.cap('C30', '10nF C0G', p[0] - 4, p[1] + 6); s.wire((p[0] - 4, p[1]), top(c)); s.rail('AGND', p[0] - 4, bot(c)[1])
    vdd, g = a.pin('8'), a.pin('3')
    s.wire(vdd, (vdd[0], vdd[1] - 4), color=C_PWR); s.rail('+5V_ISO', vdd[0], vdd[1] - 4); s.rail('AGND', g[0], g[1])
    c = s.cap('C31', '100nF', 246, 118); s.rail('+5V_ISO', 246, top(c)[1]); s.rail('AGND', 246, bot(c)[1])
    c = s.cap('C32', '1uF', 256, 118); s.rail('+5V_ISO', 256, top(c)[1]); s.rail('AGND', 256, bot(c)[1])
    s.note('AIN0 ISEN (0.30 V/A), AIN1 VSEN (0.049 V/V), AIN2 heatsink NTC, AIN3 the live V_SET node\n(PGA +-256 mV): shows what the loop really gets after OTP, OFF, KILL or CV pull it down.\n'
           'Internal reference 0.01 %, 7 ppm/K, 860 SPS, plus a die temperature sensor.', 163, 167)
    return s


# ======================================================================= setpoint and CV
def setpoint_cv():
    s = S('Set-point and hardware CV: V_SET divider, protective pull-downs, CV error amplifier', 'A4',
          'V_SET = LOAD_CTRL / 16 is the only node the four channels follow. Anything that must stop the load pulls it to AGND.')
    s.block('A   V_SET: 0 - 256 mV = 0 - 10.24 A', 15, 30, 285, 95, FILL_A)
    y = 62
    s.hier('LOAD_CTRL', 30, y, shape='input', color=C_SET)
    rt = s.res('R31', '15k', 48, y, h=True, tol='0.1%'); s.wire((30, y), lft(rt), color=C_SET)
    s.wire(rgt(rt), (250, y), color=C_SET); s.hier('VSET', 250, y, ang=0, shape='bidirectional', color=C_SET)
    rb = s.res('R32', '1k', 64, y + 10, tol='0.1%'); s.wire((64, y), top(rb), color=C_SET); s.rail('AGND', 64, bot(rb)[1])
    c = s.cap('C33', '10nF C0G', 78, y + 10); s.wire((78, y), top(c), color=C_SET); s.rail('AGND', 78, bot(c)[1])
    for i, (ref, name, txt) in enumerate([('Q11', 'OTP_GATE', 'over-temperature'), ('Q12', 'OFF_GATE', 'OFF / NTC-open / OVP')]):
        x = 110 + i * 40
        q = s.fet(Q2N, ref, '2N7002', x, y + 13)
        s.wire(q.pin('3'), (q.pin('3')[0], y), color=C_SET); s.rail('AGND', q.pin('2')[0], q.pin('2')[1])
        s.wire(q.pin('1'), (x - 14, y + 13), color=C_PROT); s.hier(name, x - 14, y + 13, shape='input', color=C_PROT)
    s.tp('TP11', 'VSET', 230, y)
    s.note('R31 / R32 = 15 : 1, 0.1 %: 4.096 V in gives 256 mV = 2.56 A per channel. C33 slews the step in 9 us so the loops never see a step edge.\n'
           'Q11 and Q12 are hardware. They work with the MCU dead. CV (block B) pulls this node down too, so LOAD_CTRL is the ceiling in CV.', 18, 93)
    # ------------------------------------------------------------ CV
    s.block('B   Hardware constant-voltage loop (LTspice deck 06)', 15, 100, 285, 172, FILL_A)
    y = 128
    s.hier('CV_SET', 30, y, shape='input', color=C_SET)
    r1 = s.res('R33', '1k', 44, y, h=True); s.wire((30, y), lft(r1), color=C_SET)
    c1 = s.cap('C34', '100nF X7R', 56, y + 9); s.wire(rgt(r1), (56, y), (72, y), color=C_SET); s.wire((56, y), top(c1)); s.rail('AGND', 56, bot(c1)[1])
    r3 = s.res('R34', '100k', 70, y + 9, tol='1%'); s.wire((70, y), top(r3)); s.rail('AGND', 70, bot(r3)[1])
    u = s.amp('dcload:LT1013_S8', 'U12', 'LT1013', 90, y - 2.54, unit=1, mirror='x')
    plus, minus, out = u.pin('1'), u.pin('8'), u.pin('7')
    s.wire((72, y), plus, color=C_SET)
    s.tp('TP31', 'CV_SET', 72, y)
    fbx = 77
    s.wire(minus, (fbx, minus[1]), (fbx, 110), color=C_MEAS)
    rin = s.res('R35', '100k', 62, 110, h=True, tol='1%')
    s.hier('VSEN_OA', 44, 110, shape='input', color=C_MEAS); s.wire((44, 110), lft(rin), color=C_MEAS); s.wire(rgt(rin), (fbx, 110), color=C_MEAS)
    rz = s.res('R36', '10k', 88, 110, h=True, tol='1%'); cz = s.cap('C35', '47nF X7R', 102, 110, h=True)
    s.wire((fbx, 110), lft(rz)); s.wire(rgt(rz), lft(cz))
    ox = 112
    s.wire(rgt(cz), (ox, 110), (ox, out[1])); s.wire(out, (ox, out[1]))
    rg = s.res('R37', '1k', 120, out[1], h=True); s.wire((ox, out[1]), lft(rg))
    q = s.fet(Q2N, 'Q13', '2N7002', 140, out[1]); s.wire(rgt(rg), q.pin('1'))
    s.rail('AGND', q.pin('2')[0], q.pin('2')[1])
    s.wire(q.pin('3'), (160, q.pin('3')[1]), color=C_SET); s.hier('VSET', 160, q.pin('3')[1], ang=0, shape='bidirectional', color=C_SET)
    v = s.amp('dcload:LT1013_S8', 'U12', 'LT1013', 220, 136, unit=2)
    p2, m2, o2 = v.pin('3'), v.pin('4'), v.pin('5')
    s.wire(p2, (208, p2[1])); s.rail('AGND', 208, p2[1])
    s.wire(m2, (210, m2[1]), (210, 146), (232, 146), (232, o2[1])); s.wire(o2, (232, o2[1]))
    s.note('spare half: follower at AGND', 236, 148)
    s.note('Why: a current-source DUT cannot be held in CC (two current sources in series rail to compliance) and a firmware CV loop on the\n'
           'DAC cannot either: 1 LSB into the 2.2 uF snubber slews 11 V in one 10 ms update. Here: V_DUT below CV_SET -> U12A rises -> Q13 pulls\n'
           'V_SET down -> less current. CV_SET = 0 V: VSEN_OA (85 mV minimum) > CV_SET, U12A stays low, Q13 off, plain CC (decks 01-04).\n'
           'Deck 06: settles for 0.1 - 8 A with and without 47 uF across the DUT. Below 0.1 A it hunts: use CC or a resistor there.', 18, 169)
    return s


# ======================================================================= channel (one file, 4 instances)
def channel():
    s = S('Current-sink channel (4 instances, one LT1014 section each)', 'A4',
          'Each MOSFET gets its own loop forced to V_SET / 0.1 R, so current and power share equally whatever the threshold spread.')
    s.block('Channel (one of four): LT1014 section, 3.3k / 1n / 47R compensation, IRFP250N, 2 x 0.2R Kelvin sense', 15, 30, 285, 160, FILL_A)
    X, Y = -30, -27   # shift of the verified Rev C drawing
    s.hier('VSET', 60.96 + X, 106.68 + Y, shape='input', color=C_SET)
    u = s.amp('dcload:LT1014', 'U11', 'LT1014', 134.62 + X, 104.14 + Y, unit=1, mirror='x', fp=None)
    u.unit_fn = lambda v: v['n']
    fb, plus, out = u.pin('2'), u.pin('3'), u.pin('1')
    s.wire((60.96 + X, 106.68 + Y), plus, color=C_SET)
    s.hier('KILL', 60.96 + X, fb[1], shape='input', color=C_PROT)
    rk = s.res('R{n}01', '4.7k', 71.12 + X, fb[1], h=True, tol='1%')
    dk = s.dio(D1N, 'D{n}01', '1N4148WS', 88.9 + X, fb[1], rot=180)
    s.wire((60.96 + X, fb[1]), lft(rk), color=C_PROT); s.wire(rgt(rk), dk.pin('2'), color=C_PROT)
    fbx = 119.38 + X
    s.wire(dk.pin('1'), (fbx, fb[1]), fb)
    rb = s.res('R{n}02', '22M', 106.68 + X, 88.9 + Y, tol='5%')
    s.wire(rb.pin('2'), (106.68 + X, fb[1])); s.rail('+12V_ISO', 106.68 + X, rb.pin('1')[1])
    cc = s.cap('C{n}01', '1nF C0G 50V', 134.62 + X, 88.9 + Y, h=True)
    dz = s.dio(ZENER, 'D{n}02', 'BZX84C6V8', 134.62 + X, 76.2 + Y, rot=180, fp=SOT23)
    outx = 149.86 + X
    s.wire((fbx, fb[1]), (fbx, 88.9 + Y), (fbx, 76.2 + Y))
    s.wire((outx, out[1]), (outx, 88.9 + Y), (outx, 76.2 + Y))
    s.wire((fbx, 88.9 + Y), lft(cc)); s.wire(rgt(cc), (outx, 88.9 + Y))
    s.wire((fbx, 76.2 + Y), dz.pin('1')); s.wire(dz.pin('3'), (outx, 76.2 + Y))
    rg = s.res('R{n}04', '47', 157.48 + X, out[1], h=True, tol='1%')
    s.wire(out, (outx, out[1]), lft(rg))
    qx = 190.5 + X
    q = s.fet(QP, 'Q{n}01', 'IRFP250NPBF', qx, out[1], fp=TO247, f={'MPN': 'IRFP250NPBF', 'Alt': 'IRFP240PBF / IXTH30N25L2'})
    q.fpos = {'Reference': (qx + 5, out[1] - 9), 'Value': (qx + 5, out[1] - 6.5)}
    s.wire(rgt(rg), (165.1 + X, out[1]), (177.8 + X, out[1]), q.pin('1'))
    s.tp('TP{n}01', 'GATE', 171.45 + X, out[1])
    rgs = s.res('R{n}05', '100k', 165.1 + X, 119.38 + Y)
    dgs = s.dio(ZENER, 'D{n}03', 'BZX84C15', 177.8 + X, 119.38 + Y, rot=270, fp=SOT23)
    s.wire((165.1 + X, out[1]), rgs.pin('1')); s.wire((177.8 + X, out[1]), dgs.pin('3'))
    sbus = 129.54 + Y
    s.wire(rgs.pin('2'), (165.1 + X, sbus)); s.wire(dgs.pin('1'), (177.8 + X, sbus))
    d, src = q.pin('2'), q.pin('3')
    s.hier('DRAIN', 218.44 + X, 88.9 + Y, ang=0, color=C_HI)
    s.wire(d, (d[0], 88.9 + Y), (218.44 + X, 88.9 + Y), width=0.6, color=C_HI)
    s.wire(src, (src[0], sbus), width=0.6, color=C_HI)
    ra = s.res('R{n}06', '0R2 1W', src[0], 140.97 + Y, fp=R2512, tol='1%')
    rbb = s.res('R{n}07', '0R2 1W', src[0] + 12.7, 140.97 + Y, fp=R2512, tol='1%')
    s.wire((165.1 + X, sbus), (177.8 + X, sbus), (src[0], sbus))
    s.wire((src[0], sbus), (src[0] + 12.7, sbus), (src[0] + 25.4, sbus), (226.06 + X, sbus), width=0.6, color=C_HI)
    s.wire((src[0], sbus), ra.pin('1'), width=0.6, color=C_HI); s.wire((src[0] + 12.7, sbus), rbb.pin('1'), width=0.6, color=C_HI)
    s.wire(ra.pin('2'), (src[0], 152.4 + Y), (src[0] + 12.7, 152.4 + Y), width=0.6, color=C_HI)
    s.wire(rbb.pin('2'), (src[0] + 12.7, 152.4 + Y), width=0.6, color=C_HI)
    s.rail('PGND', src[0] + 6.35, 152.4 + Y)
    s.tp('TP{n}02', 'SOURCE', src[0] + 25.4, sbus)
    rf = s.res('R{n}03', '3.3k', 134.62 + X, 63.5 + Y, h=True, tol='1%')
    s.wire((fbx, 76.2 + Y), (fbx, 63.5 + Y), lft(rf), color=C_MEAS)
    s.wire(rgt(rf), (226.06 + X, 63.5 + Y), (226.06 + X, sbus), color=C_MEAS)
    rav = s.res('R{n}08', '10k', 233.68 + X, sbus, h=True, tol='0.1% 25ppm')
    s.wire((226.06 + X, sbus), lft(rav), color=C_MEAS)
    s.hier('AVG', 248.92 + X, sbus, ang=0, shape='output', color=C_MEAS)
    s.wire(rgt(rav), (248.92 + X, sbus), color=C_MEAS)
    s.note('Rs: two 0.2 R 2512 in parallel = 0.1 R, so I_ch = V_SET / 0.1 R (2.56 A full scale).\n'
           'KELVIN: Rn03 and Rn08 connect at the TOP PAD of the Rs pair on their own trace, never along the high-current source copper.\n'
           'Rg within 10 mm of the gate pin. Dn03 and Rn05 sit at the FET pins. Dn02 limits integrator wind-up; Rn02 gives +1.8 mV offset\n'
           'so DAC code 0 is truly 0 A (dead zone about 72 mA in total). Loop values from deck 03: PM >= 80 deg, GM >= 13 dB for every FET candidate.\n'
           'Change them only with a re-run of deck 03.  (n = channel number)', 18, 170)
    return s


# ======================================================================= sense
def sense():
    s = S('Sense: ISEN = mean of the four source nodes, VSEN = true 4-wire difference amplifier', 'A4',
          'Both outputs are scaled for the 4.096 V ADC range and clamped to +5V_ISO. Offsets are deliberate and calibrated out in firmware.')
    s.block('A   ISEN: 0.300 V/A + 0.15 V', 15, 30, 285, 93, FILL_A)
    X, Y = -40, -20
    ax, ay = 121.92 + X, 76.2 + Y
    u = s.amp('dcload:LT1013_S8', 'U13', 'LT1013', ax, ay, unit=1)
    plus, minus, out = u.pin('1'), u.pin('8'), u.pin('7')
    s.hier('AVG', 71.12 + X, plus[1], shape='input', color=C_MEAS)
    s.wire((71.12 + X, plus[1]), plus, color=C_MEAS)
    ro = s.res('R41', '1M', 96.52 + X, 63.5 + Y, tol='1%')
    s.wire(ro.pin('2'), (96.52 + X, plus[1])); s.rail('+5V_ISO', 96.52 + X, ro.pin('1')[1])
    fbx = 106.68 + X
    s.wire(minus, (fbx, minus[1]), (fbx, 93.98 + Y))
    rg = s.res('R42', '10k', fbx, 97.79 + Y, tol='0.1%'); s.rail('AGND', fbx, rg.pin('2')[1])
    rf = s.res('R43', '110k', 124.46 + X, 93.98 + Y, h=True, tol='0.1%')
    s.wire((fbx, 93.98 + Y), lft(rf))
    ox = 139.7 + X
    s.wire(rgt(rf), (ox, 93.98 + Y), (ox, out[1])); s.wire(out, (ox, out[1]))

    def adc(x, y, rref, cref, dref, name, tp):
        r = s.res(rref, '1k', x + 8.89, y, h=True, tol='1%')
        s.wire((x, y), lft(r), color=C_MEAS)
        c = s.cap(cref, '10nF C0G 50V', x + 22.86, y + 10.16)
        s.wire((x + 22.86, y), c.pin('1')); s.rail('AGND', x + 22.86, c.pin('2')[1])
        d = s.dio(BAT54S, dref, 'BAT54S', x + 40.64, y, rot=270, mirror='x', fp=SOT23)
        com, ka, an = d.pin('3'), d.pin('2'), d.pin('1')
        s.wire(rgt(r), (x + 22.86, y), (x + 33.02, y), com, color=C_MEAS)
        s.rail('+5V_ISO', ka[0], ka[1], rot=(0 if ka[1] < an[1] else 180))
        s.rail('AGND', an[0], an[1])
        d.fpos = {'Reference': (x + 44.45, y - 2.54), 'Value': (x + 44.45, y + 2.54)}
        s.wire((x + 33.02, y), (x + 33.02, y + 15.24), (x + 58.42, y + 15.24), color=C_MEAS)
        s.hier(name, x + 58.42, y + 15.24, ang=0, shape='output', color=C_MEAS)
        s.tp(tp, name, x + 50.8, y + 15.24)
    adc(ox, out[1], 'R44', 'C41', 'D41', 'ISEN_ADC', 'TP21')
    s.note('Gain 12 (R43 / R42 + 1). R41 injects +12 mV at the input (= +0.15 V out) so the amp never sits on its 35 mV output floor.\n'
           'Full scale 3.22 V at 10.24 A, 0.4 mA per ADS1118 LSB. U13 is the S8 package: NON-STANDARD pinout, the symbol is correct for it.', 18, 91.5)
    s.block('B   VSEN: 0.049 V/V + 0.10 V, true 4-wire', 15, 98, 285, 172, FILL_A)
    X, Y = -28, -44
    vx, vy = 121.92 + X, 167.64 + Y
    ox = 139.7 + X
    v = s.amp('dcload:LT1013_S8', 'U13', 'LT1013', vx, vy, unit=2)
    p, m, o = v.pin('3'), v.pin('4'), v.pin('5')
    s.hier('SENSE_P', 60.96 + X, p[1], shape='input', color=C_MEAS)
    r1 = s.res('R45', '200k', 78.74 + X, p[1], h=True, tol='0.1%', fp=R1206)
    s.wire((60.96 + X, p[1]), lft(r1), color=C_MEAS)
    s.wire(rgt(r1), (86.36 + X, p[1]), (99.06 + X, p[1]), p)
    r2 = s.res('R46', '10k', 86.36 + X, p[1] + 10.16, tol='0.1%'); s.wire((86.36 + X, p[1]), r2.pin('1')); s.rail('AGND', 86.36 + X, r2.pin('2')[1])
    r3 = s.res('R47', '470k', 99.06 + X, p[1] + 10.16, tol='1%')
    s.wire((99.06 + X, p[1]), top(r3)); s.rail('+5V_ISO', bot(r3)[0], bot(r3)[1], rot=180)
    s.hier('SENSE_N', 60.96 + X, m[1] - 22.86, shape='input', color=C_MEAS)
    r4 = s.res('R48', '200k', 78.74 + X, m[1] - 22.86, h=True, tol='0.1%', fp=R1206)
    s.wire((60.96 + X, m[1] - 22.86), lft(r4), color=C_MEAS)
    s.wire(rgt(r4), (106.68 + X, m[1] - 22.86), (106.68 + X, m[1]), m)
    r5 = s.res('R49', '10k', 124.46 + X, m[1] - 22.86, h=True, tol='0.1%')
    s.wire((106.68 + X, m[1] - 22.86), lft(r5))
    s.wire(rgt(r5), (ox, m[1] - 22.86), (ox, o[1])); s.wire(o, (ox, o[1]))
    s.hier('VSEN_OA', ox, o[1] + 12.7, ang=180, shape='output', color=C_MEAS)
    s.wire((ox, o[1]), (ox, o[1] + 12.7), color=C_MEAS)
    adc(ox, o[1], 'R50', 'C42', 'D42', 'VSEN_ADC', 'TP22')
    s.note('VSEN = 0.049 x (SENSE_P - SENSE_N) + 0.10 V: 2.5 mV of DUT per LSB, clips at 65 V. R45 and R48 see 60 V: 1206.\n'
           'R49 feeds back to -IN (the Rev B board had it on +IN and latched). VSEN_OA also feeds the CV loop and the OVP comparator.', 18, 168)
    return s


# ======================================================================= protection
def protection():
    s = S('Protection: over-temperature, dropout / KILL, NTC-open, over-voltage, hardware OFF', 'A3',
          'LM339 open-collector comparators on +12V_ISO. Thresholds are ratios of +5V_ISO, the same rail that feeds the NTC divider.')
    # ------ NTC divider
    s.block('A   Heatsink NTC and TEMP_MON', 15, 30, 110, 156, FILL_A)
    nx = 42
    rn = s.res('R51', '10.0k', nx, 60, tol='0.1%')
    s.rail('+5V_ISO', nx, top(rn)[1])
    jn = s.part('Connector_Generic:Conn_01x02', 'J6', 'NTC 10k B3950', nx + 24, 82, fp='Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical')
    jn.fpos = {'Reference': (nx + 24, 76, 'center'), 'Value': (nx + 24, 89, 'center')}
    s.wire(bot(rn), (nx, jn.pin('1')[1]), jn.pin('1'), color=C_MEAS)
    s.wire(jn.pin('2'), (nx + 14, jn.pin('2')[1]), (nx + 14, 96)); s.rail('AGND', nx + 14, 96)
    cn = s.cap('C51', '100nF X7R', nx, 92)
    s.wire((nx, jn.pin('1')[1]), top(cn)); s.rail('AGND', nx, bot(cn)[1])
    s.wire((nx, 68), (nx + 14, 68), color=C_MEAS); s.lab('V_NTC', nx + 14, 68, color=C_MEAS)
    rm = s.res('R52', '10k', 40, 122, h=True)
    cm = s.cap('C52', '100nF X7R', 56, 130)
    s.lab('V_NTC', lft(rm)[0], lft(rm)[1], ang=180, color=C_MEAS); s.wire(rgt(rm), (56, 122), (80, 122), color=C_MEAS)
    s.wire((56, 122), top(cm)); s.rail('AGND', 56, bot(cm)[1])
    s.hier('TEMP_MON', 80, 122, ang=0, shape='output', color=C_MEAS)
    s.note('V_NTC (10k B3950 lug thermistor on the heatsink next to FET 2):\n2.50 V at 25 C, 1.52 V at 45 C, 0.75 V at 70 C, 0.49 V at 85 C.\n'
           'TEMP_MON goes to the ADC: the MCU runs the fan from it\n(on above 45 C, full above 65 C) and shows the temperature.', 18, 153)

    def comparator(x, y, unit, pplus, pminus, pout, top_val, bot_val, hyst_val, refs):
        """threshold network on In+ from +5V_ISO, hysteresis from the output, V_in on In-."""
        u = s.amp('Comparator:LM339', 'U14', 'LM339', x, y, unit=unit, f={'Footprint': 'Package_SO:SOIC-14_3.9x8.7mm_P1.27mm'})
        plus, minus, out = u.pin(pplus), u.pin(pminus), u.pin(pout)
        rt = s.res(refs[0], top_val, x - 17.78, plus[1] - 10.16, tol='1%')
        rb = s.res(refs[1], bot_val, x - 17.78, plus[1] + 12.7, tol='1%')
        s.wire(bot(rt), (x - 17.78, plus[1]), plus); s.wire((x - 17.78, plus[1]), top(rb))
        s.rail('+5V_ISO', x - 17.78, top(rt)[1]); s.rail('AGND', x - 17.78, bot(rb)[1])
        rh = s.res(refs[2], hyst_val, x, plus[1] - 15.24, h=True, tol='1%')
        s.wire(lft(rh), (x - 10.16, lft(rh)[1]), (x - 10.16, plus[1]))
        s.wire(rgt(rh), (x + 12.7, rgt(rh)[1]), (x + 12.7, out[1])); s.wire(out, (x + 12.7, out[1]))
        return plus, minus, out

    # ------ #1 OTP (unit 1: pins 5, 4, 2)
    s.block('B   Over-temperature: 85 C trip, 70 C release', 120, 30, 260, 110, FILL_A)
    x, y = 165, 72
    pl, mi, ou = comparator(x, y, 1, '5', '4', '2', '90.9k', '10.0k', '402k', ('R53', 'R54', 'R55'))
    s.lab('V_NTC', mi[0], mi[1], ang=180, color=C_MEAS)
    pux = x + 12.7
    pu = s.res('R56', '10k', pux + 7.62, y - 15.24)
    s.rail('+12V_ISO', pux + 7.62, top(pu)[1]); s.wire(bot(pu), (pux + 7.62, y), (pux, y))
    s.hier('OTP_GATE', pux + 24, y, ang=0, shape='output', color=C_PROT); s.wire((pux + 7.62, y), (pux + 24, y), color=C_PROT)
    s.note('In+ = 0.099 x rail (0.49 V = 85 C). Output high -> Q11 shorts V_SET.\nHysteresis via R55 from the 12 V output: releases at 0.75 V = 70 C.', 123, 106)
    # ------ #2 dropout / KILL (unit 2: pins 7, 6, 1)
    s.block('C   Dropout / anti-wind-up KILL: DRAIN below 0.45 V', 270, 30, 405, 110, FILL_A)
    x, y = 340, 72
    pl, mi, ou = comparator(x, y, 2, '7', '6', '1', '100k', '10.0k', '165k', ('R57', 'R58', 'R59'))
    rdr = s.res('R60', '47k', x - 45.72, mi[1], h=True, tol='1%', fp=R1206)
    s.hier('DRAIN', x - 58.42, mi[1], shape='input', color=C_HI); s.wire((x - 58.42, mi[1]), lft(rdr), color=C_HI)
    s.wire(rgt(rdr), (x - 33.02, mi[1]), mi)
    dz = s.dio(ZENER, 'D43', 'BZX84C12', x - 33.02, mi[1] + 10.16, rot=270, fp=SOT23)
    s.wire((x - 33.02, mi[1]), dz.pin('3')); s.rail('AGND', x - 33.02, dz.pin('1')[1])
    pux = x + 12.7
    pu = s.res('R61', '10k', pux + 7.62, y - 15.24)
    s.rail('+12V_ISO', pux + 7.62, top(pu)[1]); s.wire(bot(pu), (pux + 7.62, y), (pux, y))
    s.hier('KILL', pux + 24, y, ang=0, shape='output', color=C_PROT); s.wire((pux + 7.62, y), (pux + 24, y), color=C_PROT)
    s.tp('TP41', 'KILL', pux + 18, y)
    s.note('KILL pulls every channel In- high through 4.7k + 1N4148 when the DUT is\nabsent or below 0.45 V; releases above 0.54 V. Stops the 115 - 170 A\nrecovery spikes of deck 04. R60 sees 60 V: 1206.', 273, 100)
    # ------ #3 NTC open (unit 3: pins 11, 10, 13): In+ = V_NTC, In- = 0.73 x rail
    s.block('D   NTC open and hardware OFF: all roads to OFF_GATE', 120, 118, 260, 215, FILL_A)
    x, y = 165, 160
    u = s.amp('Comparator:LM339', 'U14', 'LM339', x, y, unit=3, f={'Footprint': 'Package_SO:SOIC-14_3.9x8.7mm_P1.27mm'})
    pl, mi, ou = u.pin('11'), u.pin('10'), u.pin('13')
    s.wire(pl, (x - 30, pl[1]), color=C_MEAS); s.lab('V_NTC', x - 30, pl[1], ang=180, color=C_MEAS)
    r1 = s.res('R62', '10.0k', x - 17.78, mi[1] - 8, tol='1%')
    r2 = s.res('R63', '27.4k', x - 17.78, mi[1] + 8, tol='1%')
    s.rail('+5V_ISO', x - 17.78, top(r1)[1]); s.wire(bot(r1), (x - 17.78, mi[1]), mi); s.wire((x - 17.78, mi[1]), top(r2)); s.rail('AGND', x - 17.78, bot(r2)[1])
    pux = x + 12.7
    pu = s.res('R64', '10k', pux, y - 12.7)
    s.rail('+12V_ISO', pux, top(pu)[1]); s.wire(ou, (pux, y)); s.wire(bot(pu), (pux, y))
    dc = s.dio(BAT54C, 'D44', 'BAT54C', pux + 17.78, y + 2.54, fp=SOT23)
    dc.fpos = {'Reference': (pux + 17.78, y - 3, 'center'), 'Value': (pux + 7.62, y + 7.9, 'center')}
    s.wire((pux, y), (pux, dc.pin('1')[1]), dc.pin('1'))
    s.hier('LOAD_OFF_ISO', pux + 36, dc.pin('2')[1], ang=0, shape='input', color=C_PROT); s.wire(dc.pin('2'), (pux + 36, dc.pin('2')[1]), color=C_PROT)
    k = dc.pin('3')
    s.hier('OFF_GATE', k[0] + 16, k[1] + 5.08, ang=0, shape='output', color=C_PROT)
    rd = s.res('R65', '100k', k[0], k[1] + 12.7)
    s.wire(k, (k[0], k[1] + 5.08), top(rd)); s.wire((k[0], k[1] + 5.08), (k[0] + 16, k[1] + 5.08), color=C_PROT)
    s.rail('AGND', k[0], bot(rd)[1])
    d45 = s.dio(D1N, 'D45', '1N4148WS', k[0] + 10, k[1] + 11, rot=270)
    s.wire(d45.pin('1'), (k[0] + 10, k[1] + 5.08)); s.wire(d45.pin('2'), (k[0] + 10, k[1] + 18)); s.lab('OVP_OUT', k[0] + 10, k[1] + 18, ang=270, color=C_PROT)
    s.note('NTC open or unplugged: V_NTC above 0.73 x rail (= 3.66 V, NTC > 27 k) forces 0 A; an open NTC would\n'
           'otherwise read as cold. False trip only below about 3 C. LOAD_OFF_ISO: the MCU-side OFF, 5 V logic through the\n'
           'isolator, asserted whenever the USB side is dead. OVP_OUT (block E) joins through D45. R65 defines the node\n'
           'when nothing drives it.', 123, 211)
    # ------ #4 OVP (unit 4: pins 9, 8, 14): In+ = VSEN_OA via 10k, In- = 0.629 x rail (3.145 V = 62 V)
    s.block('E   Over-voltage: DUT above 62 V', 270, 118, 405, 215, FILL_A)
    x, y = 340, 160
    u = s.amp('Comparator:LM339', 'U14', 'LM339', x, y, unit=4, f={'Footprint': 'Package_SO:SOIC-14_3.9x8.7mm_P1.27mm'})
    pl, mi, ou = u.pin('9'), u.pin('8'), u.pin('14')
    rin = s.res('R66', '10k', x - 22, pl[1], h=True, tol='1%')
    s.hier('VSEN_OA', x - 40, pl[1], shape='input', color=C_MEAS); s.wire((x - 40, pl[1]), lft(rin), color=C_MEAS); s.wire(rgt(rin), pl)
    rh = s.res('R67', '1M', x, pl[1] - 12, h=True, tol='1%')
    s.wire(lft(rh), (x - 10.16, lft(rh)[1]), (x - 10.16, pl[1])); s.wire(rgt(rh), (x + 12.7, rgt(rh)[1]), (x + 12.7, ou[1]))
    r1 = s.res('R68', '5.90k', x - 17.78, mi[1] - 8, tol='1%')
    r2 = s.res('R69', '10.0k', x - 17.78, mi[1] + 8, tol='1%')
    s.rail('+5V_ISO', x - 17.78, top(r1)[1]); s.wire(bot(r1), (x - 17.78, mi[1]), mi); s.wire((x - 17.78, mi[1]), top(r2)); s.rail('AGND', x - 17.78, bot(r2)[1])
    pux = x + 12.7
    pu = s.res('R70', '10k', pux + 7.62, y - 15.24)
    s.rail('+12V_ISO', pux + 7.62, top(pu)[1]); s.wire(bot(pu), (pux + 7.62, y), (pux, y)); s.wire(ou, (pux, y))
    s.wire((pux + 7.62, y), (pux + 24, y), color=C_PROT); s.lab('OVP_OUT', pux + 24, y, color=C_PROT)
    s.note('VSEN_OA above 0.629 x rail (3.15 V = 62 V at the terminals) forces 0 A through OFF_GATE.\n'
           'Protects the 58 V fuse rating and the 70 V TVS. R67 gives about 1.8 V of hysteresis.\nFirmware latches the trip; the comparator alone would re-arm when the DUT sags.', 273, 211)
    # LM339 supply
    u = s.amp('Comparator:LM339', 'U14', 'LM339', 60, 190, unit=5, f={'Footprint': 'Package_SO:SOIC-14_3.9x8.7mm_P1.27mm'})
    vp, vm = u.pin('3'), u.pin('12')
    s.wire(vp, (vp[0], vp[1] - 4), color=C_PWR); s.rail('+12V_ISO', vp[0], vp[1] - 4); s.rail('AGND', vm[0], vm[1])
    c = s.cap('C53', '100nF X7R 50V', 76, 190); s.rail('+12V_ISO', 76, top(c)[1]); s.rail('AGND', 76, bot(c)[1])
    s.block('F   Supplies of the analog ICs', 15, 158, 110, 250, FILL_A)
    for i, (lib, ref, val, unit, vpn, vmn) in enumerate([('dcload:LT1014', 'U11', 'LT1014', 5, '4', '13'), ('dcload:LT1013_S8', 'U13', 'LT1013', 3, '6', '2'),
                                                         ('dcload:LT1013_S8', 'U12', 'LT1013', 3, '6', '2')]):
        x0 = 28 + i * 26
        p = s.amp(lib, ref, val, x0, 228, unit=unit)
        vpp, vmm = p.pin(vpn), p.pin(vmn)
        s.wire(vpp, (vpp[0], vpp[1] - 6), color=C_PWR); s.rail('+12V_ISO', vpp[0], vpp[1] - 6)
        s.wire(vmm, (vmm[0], vmm[1] + 3)); s.rail('AGND', vmm[0], vmm[1] + 3)
        c = s.cap('C%d' % (54 + i), '100nF 50V', x0 + 11, 222)
        s.rail('+12V_ISO', x0 + 11, top(c)[1]); s.rail('AGND', x0 + 11, bot(c)[1])
    c = s.cap('C57', '10uF 25V X7R', 102, 228, fp=C0805); s.rail('+12V_ISO', 102, top(c)[1]); s.rail('AGND', 102, bot(c)[1])
    s.note('One 100 nF at every V+ pin, 10 uF bulk\nnear the LT1014.', 18, 248)
    return s


# ======================================================================= power path
def power_path():
    s = S('Power path: DUT terminals, 58 V fuse, TVS, snubber, 4-wire sense', 'A4',
          'DUT+ -> fuse -> DRAIN bus -> four drains. The source resistors return to PGND, which meets AGND only at NT1.')
    s.block('A   Terminals and DRAIN bus', 15, 30, 285, 110, FILL_A)
    W = 'Connector_Wire:SolderWire-2.5sqmm_1x01_D2.4mm_OD3.6mm'
    y = 58
    jp = s.part('Connector_Generic:Conn_01x01', 'J7', 'DUT+', 40, y, mirror='y', fp=W, f={'Note': 'Wire to a >= 15 A panel binding post'})
    jp.fpos = {'Reference': (34, y - 4.2), 'Value': (34, y + 4.6)}
    f = s.res('F1', '15A 58VDC mini blade', 90, y, h=True, part='Device:Fuse', fp='Fuse:Fuseholder_Blade_Mini_Keystone_3568', f={'MPN': 'Littelfuse 0997015.WXN'})
    s.wire(jp.pin('1'), lft(f), width=0.6, color=C_HI); s.tp('TP51', 'DUT+', 66, y)
    s.lab('DUT_P', 52, y, color=C_HI)
    tvs = s.dio('Device:D_Zener', 'D51', 'SMCJ70A TVS', 124, y + 16, rot=270, fp='Diode_SMD:D_SMC')
    rsn = s.res('R71', '2.2R 1W', 144, y + 9, fp=R2512, tol='1%')
    csn = s.cap('C58', '2.2uF 100V X7S', 144, y + 23, fp=C1206)
    s.hier('DRAIN', 200, y, ang=0, color=C_HI)
    s.wire(rgt(f), (124, y), (144, y), (200, y), width=0.6, color=C_HI)
    s.tp('TP52', 'DRAIN', 176, y)
    t1, t2 = tvs.pin('1'), tvs.pin('2')
    tu, td = (t1, t2) if t1[1] < t2[1] else (t2, t1)
    s.wire((124, y), tu); s.wire((144, y), top(rsn)); s.wire(bot(rsn), top(csn))
    pg = y + 38
    s.wire(td, (124, pg)); s.wire(bot(csn), (144, pg))
    jn = s.part('Connector_Generic:Conn_01x01', 'J8', 'DUT-', 40, pg, mirror='y', fp=W, f={'Note': 'Wire to a >= 15 A panel binding post'})
    jn.fpos = {'Reference': (34, pg - 4.2), 'Value': (34, pg + 4.6)}
    s.wire(jn.pin('1'), (124, pg), (144, pg), (160, pg), width=0.6, color=C_HI)
    s.rail('PGND', 160, pg)
    s.note('Fuse: the 58 V DC MINI part named. Ordinary blade fuses are rated 32 V, so 58 V is the DUT limit of this board (OVP trips at 62 V).\n'
           'No series diode, so the load works down to 0.6 V. Reverse polarity conducts through the FET body diodes and the TVS and clears the fuse.', 18, 108.5)
    s.block('B   4-wire sense with local fallback', 15, 116, 285, 172, FILL_A)
    js = s.part('Connector_Generic:Conn_01x02', 'J9', 'SENSE', 40, 136, mirror='y', fp='Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical',
                f={'Note': 'Panel S+ / S- terminals, wired to the DUT'})
    js.fpos = {'Reference': (34, 130), 'Value': (34, 142.5)}
    sp, sn = js.pin('1'), js.pin('2')
    s.hier('SENSE_P', 200, sp[1], ang=0, shape='output', color=C_MEAS); s.wire(sp, (200, sp[1]), color=C_MEAS)
    s.hier('SENSE_N', 200, sn[1] + 12.7, ang=0, shape='output', color=C_MEAS)
    s.wire(sn, (50, sn[1]), (50, sn[1] + 12.7), (200, sn[1] + 12.7), color=C_MEAS)
    rsp = s.res('R72', '100R', 80, 125, fp=R1206); s.lab('DUT_P', 80, top(rsp)[1], ang=90, color=C_HI); s.wire(bot(rsp), (80, sp[1]))
    rsnn = s.res('R73', '100R', 100, sn[1] + 12.7 + 7.62, fp=R1206)
    s.wire((100, sn[1] + 12.7), top(rsnn)); s.rail('PGND', 100, bot(rsnn)[1])
    s.note('J9 open: R72 / R73 connect the sense amplifier to the terminals. J9 wired to the DUT: they carry only microamps and the lead drop\n'
           'leaves the reading. A miswired sense lead burns a 100 R 1206 open and nothing else.\n'
           'Copper: >= 5 mm of 2 oz for DUT+ / DRAIN / PGND, or a soldered wire. C58 and D51 directly across DRAIN / PGND at the terminals.', 120, 168)
    return s


# ======================================================================= root
SHEETS = [
    ('USB & Power', 'sheets/usb_power.kicad_sch', usb_power,
     [('USB_DM', 'bidirectional', 'R'), ('USB_DP', 'bidirectional', 'R'), ('CC1_SENSE', 'output', 'R'), ('CC2_SENSE', 'output', 'R'),
      ('FAN_EN', 'input', 'R'), ('FAN_PWM', 'input', 'R'), ('FAN_TACH', 'output', 'R')]),
    ('MCU', 'sheets/mcu.kicad_sch', mcu,
     [('USB_DM', 'bidirectional', 'L'), ('USB_DP', 'bidirectional', 'L'), ('CC1_SENSE', 'input', 'L'), ('CC2_SENSE', 'input', 'L'),
      ('FAN_EN', 'output', 'L'), ('FAN_PWM', 'output', 'L'), ('FAN_TACH', 'input', 'L'),
      ('SPI2_SCK', 'output', 'L'), ('SPI2_MOSI', 'output', 'L'), ('~{DISP_CS}', 'output', 'L'),
      ('ENC_A', 'input', 'L'), ('ENC_B', 'input', 'L'), ('ENC_SW', 'input', 'L'), ('BTN_ON', 'input', 'L'), ('BTN_MODE', 'input', 'L'), ('BTN_MENU', 'input', 'L'),
      ('SPI1_SCK', 'output', 'R'), ('SPI1_MOSI', 'output', 'R'), ('SPI1_MISO', 'input', 'R'), ('~{CS_DAC}', 'output', 'R'), ('~{CS_ADC}', 'output', 'R'), ('LOAD_OFF', 'output', 'R')]),
    ('Front Panel UI', 'sheets/ui.kicad_sch', ui,
     [('SPI2_SCK', 'input', 'R'), ('SPI2_MOSI', 'input', 'R'), ('~{DISP_CS}', 'input', 'R'),
      ('ENC_A', 'output', 'R'), ('ENC_B', 'output', 'R'), ('ENC_SW', 'output', 'R'), ('BTN_ON', 'output', 'R'), ('BTN_MODE', 'output', 'R'), ('BTN_MENU', 'output', 'R')]),
    ('Isolated Interface', 'sheets/iso_interface.kicad_sch', iso_interface,
     [('SPI1_SCK', 'input', 'L'), ('SPI1_MOSI', 'input', 'L'), ('SPI1_MISO', 'output', 'L'), ('~{CS_DAC}', 'input', 'L'), ('~{CS_ADC}', 'input', 'L'), ('LOAD_OFF', 'input', 'L'),
      ('LOAD_CTRL', 'output', 'R'), ('CV_SET', 'output', 'R'), ('LOAD_OFF_ISO', 'output', 'R'), ('ISEN_ADC', 'input', 'R'), ('VSEN_ADC', 'input', 'R'), ('TEMP_MON', 'input', 'R'), ('VSET', 'input', 'R')]),
    ('Setpoint & CV', 'sheets/setpoint_cv.kicad_sch', setpoint_cv,
     [('LOAD_CTRL', 'input', 'L'), ('CV_SET', 'input', 'L'), ('VSEN_OA', 'input', 'L'), ('OTP_GATE', 'input', 'L'), ('OFF_GATE', 'input', 'L'), ('VSET', 'bidirectional', 'R')]),
    ('Sense', 'sheets/sense.kicad_sch', sense,
     [('AVG', 'input', 'L'), ('SENSE_P', 'input', 'L'), ('SENSE_N', 'input', 'L'), ('ISEN_ADC', 'output', 'R'), ('VSEN_ADC', 'output', 'R'), ('VSEN_OA', 'output', 'R')]),
    ('Protection', 'sheets/protection.kicad_sch', protection,
     [('DRAIN', 'input', 'L'), ('VSEN_OA', 'input', 'L'), ('LOAD_OFF_ISO', 'input', 'L'), ('TEMP_MON', 'output', 'R'), ('KILL', 'output', 'R'), ('OTP_GATE', 'output', 'R'), ('OFF_GATE', 'output', 'R')]),
    ('Power Path', 'sheets/power_path.kicad_sch', power_path,
     [('DRAIN', 'passive', 'R'), ('SENSE_P', 'output', 'R'), ('SENSE_N', 'output', 'R')]),
]
CH_PINS = [('VSET', 'input', 'L'), ('KILL', 'input', 'L'), ('DRAIN', 'passive', 'R'), ('AVG', 'output', 'R')]
NETCOL = {'USB_DM': C_USB, 'USB_DP': C_USB, 'SPI1_SCK': C_SPI, 'SPI1_MOSI': C_SPI, 'SPI1_MISO': C_SPI, '~{CS_DAC}': C_SPI, '~{CS_ADC}': C_SPI,
          'LOAD_OFF': C_PROT, 'LOAD_OFF_ISO': C_PROT, 'KILL': C_PROT, 'OTP_GATE': C_PROT, 'OFF_GATE': C_PROT,
          'LOAD_CTRL': C_SET, 'CV_SET': C_SET, 'VSET': C_SET, 'ISEN_ADC': C_MEAS, 'VSEN_ADC': C_MEAS, 'VSEN_OA': C_MEAS, 'TEMP_MON': C_MEAS,
          'AVG': C_MEAS, 'SENSE_P': C_MEAS, 'SENSE_N': C_MEAS, 'DRAIN': C_HI}


def main():
    root = S('DC Electronic Load Rev D: one board, isolated, USB-C powered', 'A3',
             '150 W, 0.6 - 58 V, 0 - 10.2 A. Hardware CC and CV, firmware CR / CP / battery. Local 7-segment UI, USB CDC / DFU, SCPI over USB.')
    root.root = ROOT_UUID
    os.makedirs(os.path.join(PDIR, 'sheets'), exist_ok=True)
    page = [2]

    def place(name, fname, pins, x, y, w=50):
        x, y, w = root.g(x), root.g(y), root.g(w)
        ls = [p for p in pins if p[2] == 'L']; rs = [p for p in pins if p[2] == 'R']
        h = max(len(ls), len(rs), 1) * 5.08 + 5.08
        lst = []
        for i, (n, sh, side) in enumerate(ls + rs):
            k = i if side == 'L' else i - len(ls)
            py = y + 5.08 + k * 5.08
            lst.append((n, sh, side, py))
            px = x if side == 'L' else x + w
            ex = px - 9 if side == 'L' else px + 9
            col = NETCOL.get(n)
            root.wire((px, py), (ex, py), color=col)
            root.label(n, ex, py, angle=180 if side == 'L' else 0, color=col)
        u = root.add_sheet(name, fname, x, y, w, h, lst, page[0])
        page[0] += 1
        return u

    root.rect(14, 28, 150, 276, dash=False, width=0.25, color=C_FRAME, fill=FILL_D)
    root.text('USB SIDE  (DGND: earth-referenced through the PC)', 16, 32, size=FS_BLOCK, bold=True, color=(0, 50, 120))
    root.rect(232, 28, 408, 276, dash=False, width=0.25, color=C_FRAME, fill=FILL_A)
    root.text('ISOLATED ANALOG SIDE  (AGND = DUT minus, floats with the DUT)', 234, 32, size=FS_BLOCK, bold=True, color=(0, 90, 40))
    root.barrier(191, 28, 276, label=True)
    layout = {'USB & Power': (30, 44), 'MCU': (62, 100), 'Front Panel UI': (30, 222), 'Isolated Interface': (172, 160),
              'Setpoint & CV': (248, 44), 'Sense': (248, 96), 'Protection': (248, 145), 'Power Path': (248, 200)}
    built = []
    for name, fname, fn, pins in SHEETS:
        x, y = layout[name]
        u = place(name, fname, pins, x, y, w=46 if x > 200 else 50)
        built.append((fname, fn, u))
    ch_uuids = []
    for n, (x, y) in enumerate([(350, 44), (350, 84), (350, 124), (350, 164)], 1):
        ch_uuids.append((n, place('Channel %d' % n, 'sheets/channel.kicad_sch', CH_PINS, x, y, w=36)))
    root.note('Reading order: USB & Power (2), MCU (3), Front Panel (4), Isolated Interface (5), Setpoint & CV (6), Channels (10-13), Sense (7), Protection (8), Power Path (9). Nets on this page join by name.\n'
              'Power symbols are global: VBUS, +3V3, +12V_FAN, DGND on the USB side; +12V_ISO, +5V_ISO, AGND, PGND on the analog side. The analog stage is the Rev C design verified in LTspice decks 01-06.', 16, 286)
    # legend
    lx, ly = 336, 206
    root.rect(lx - 4, ly - 6, 408, 258, dash=False, width=0.25, color=C_FRAME, fill=FILL_N)
    root.text('NET COLOUR KEY', lx, ly - 1.5, size=FS_BLOCK, bold=True, color=(0, 50, 120))
    for i, (col, txt, wd) in enumerate([(C_HI, 'DUT current path (fuse, DRAIN, Rs, PGND)', 0.6), (C_SET, 'set-point: LOAD_CTRL, V_SET, CV_SET', 0),
                                        (C_MEAS, 'measurement: AVG, ISEN, VSEN, V_NTC', 0), (C_PROT, 'protection: KILL, OTP, OFF, LOAD_OFF', 0),
                                        (C_SPI, 'isolated SPI', 0), (C_USB, 'USB data', 0), (C_PWR, 'supply rails', 0)]):
        y = ly + 5 + i * 6
        root.polyline([(lx, y), (lx + 12, y)], width=wd or 0.3, dash=False, color=col)
        root.text(txt, lx + 15, y + 1, size=FS_NOTE)
    root.polyline([(lx, ly + 48), (lx + 12, ly + 48)], width=0.7, dash=True, color=C_BAR)
    root.text('isolation barrier', lx + 15, ly + 49, size=FS_NOTE)
    for fname, fn, u in built:
        sh = fn(); sh.instances = [('/%s/%s' % (ROOT_UUID, u), {'n': ''})]
        open(os.path.join(PDIR, fname), 'w').write(sh.render())
    sh = channel()
    sh.instances = [('/%s/%s' % (ROOT_UUID, u), {'n': n}) for n, u in ch_uuids]
    open(os.path.join(PDIR, 'sheets/channel.kicad_sch'), 'w').write(sh.render())
    open(os.path.join(PDIR, PROJ + '.kicad_sch'), 'w').write(root.render())
    # project library table and symbol library (shared with Rev C: append-only)
    open(os.path.join(PDIR, 'fp-lib-table'), 'w').write('(fp_lib_table\n\t(version 7)\n\t(lib (name "dcload")(type "KiCad")(uri "${KIPRJMOD}/../libraries/footprints/dcload.pretty")(options "")(descr "DC Load project footprints"))\n)\n')
    open(os.path.join(PDIR, 'sym-lib-table'), 'w').write('(sym_lib_table\n\t(version 7)\n\t(lib (name "dcload")(type "KiCad")(uri "${KIPRJMOD}/../libraries/symbols/dcload.kicad_sym")(options "")(descr "DC Load project symbols"))\n)\n')
    syms = []
    for k, v in CUSTOM.items():
        c = copy.deepcopy(v); c[1] = Str(k.split(':')[1]); syms.append(c)
    # keep the Rev C symbols (+4V096) in the shared library
    rc = power_sym('+4V096'); rc[1] = Str('+4V096'); syms.append(rc)
    open(os.path.join(HERE, '..', 'libraries', 'symbols', 'dcload.kicad_sym'), 'w').write(
        dump(['kicad_symbol_lib', ['version', 20251024], ['generator', Str('kgen')], ['generator_version', Str('10.0')]] + syms) + '\n')
    pro = os.path.join(PDIR, PROJ + '.kicad_pro')
    d = json.load(open(pro))
    d['sheets'] = [[ROOT_UUID, 'Root']]
    d.setdefault('meta', {})['filename'] = PROJ + '.kicad_pro'
    json.dump(d, open(pro, 'w'), indent=2)
    print('ok')


if __name__ == '__main__':
    main()
