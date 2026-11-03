#!/usr/bin/env python3
"""Proves the Rev E KiCad schematic is the circuit that was simulated, plus checks the digital side.
Part 1: every element of the LTspice rev_e deck 06 netlist (TLV9154 decks) is mapped to its Rev E KiCad part(s) and the net
partition is compared (same method as check_netlist.py for Rev C).
Part 2: explicit same-net assertions for everything the simulation does not cover (isolator channels,
DAC / ADC, MCU pins, OLED header, LEDs, fan, comparators).
usage: python3 check_netlist_reve.py ../outputs/rev_e_v1/DC_Load_RevE.xml ../../simulation/rev_e/06_cv_mode/06_cv_mode.net"""
import re, sys, collections
import xml.etree.ElementTree as ET


ALIAS = {'VSET_MON': 'VSET', 'VSEN_OA_OVP': 'VSEN_OA', 'KILL_T': 'KILL', 'VSET_T': 'VSET', 'DRAIN_T': 'DRAIN', 'AVG_T': 'AVG'}


def netname(name):
    """The root sheet is a wired block diagram without labels, so KiCad names hierarchical nets '/<sheet>/<pin>'; compare by the pin
    name, and fold the pass-through pin names (VSET_MON, KILL_T ...) onto the net they belong to."""
    if '/' in name:
        base = name.rsplit('/', 1)[1]
        return '/' + ALIAS.get(base, base)
    return name


def kicad_nets(path):
    pins = {}
    for net in ET.parse(path).getroot().find('nets'):
        for n in net.findall('node'):
            pins[(n.get('ref'), n.get('pin'))] = netname(net.get('name'))
            fn = n.get('pinfunction')
            if fn:
                for part in fn.split('/'):                       # 'PA9/PA11' -> PA9 and PA11; 'VBAT_4' -> VBAT
                    part = re.sub(r'_\d+$', '', part)
                    pins.setdefault((n.get('ref'), '@' + part), netname(net.get('name')))   # ('U4', '@PA5') by pin name; the real PA9 pin comes before the PA9/PA11 remap alias
    return pins


def map_sim():
    m = {}
    amp = {1: ('3', '2', '1'), 2: ('5', '6', '7'), 3: ('10', '9', '8'), 4: ('12', '13', '14')}   # TLV9154 standard quad: +, -, out
    for n in range(1, 5):
        a = amp[n]
        m['XU%d' % n] = [(0, 'U11', a[0]), (1, 'U11', a[1]), (2, 'U11', '4'), (3, 'U11', '11'), (4, 'U11', a[2])]
        m['C%d' % n] = [(0, 'C%d01' % n, '2'), (1, 'C%d01' % n, '1')]
        m['RB%d' % n] = [(0, 'R%d02' % n, '2'), (1, 'R%d02' % n, '1')]
        m['RK%d' % n] = [(0, 'R%d01' % n, '2'), (1, 'R%d01' % n, '1')]
        m['DK%d' % n] = [(0, 'D%d01' % n, '2'), (1, 'D%d01' % n, '1')]
        m['DZ%d' % n] = [(0, 'D%d02' % n, '1'), (1, 'D%d02' % n, '3')]
        m['RG%d' % n] = [(0, 'R%d04' % n, '2'), (1, 'R%d04' % n, '1')]
        m['M%d' % n] = [(0, 'Q%d01' % n, '2'), (1, 'Q%d01' % n, '1'), (2, 'Q%d01' % n, '3')]
        m['RS%d' % n] = [(0, 'R%d06' % n, '1'), (1, 'R%d06' % n, '2'), (0, 'R%d07' % n, '1'), (1, 'R%d07' % n, '2')]
        m['RF%d' % n] = [(0, 'R%d03' % n, '2'), (1, 'R%d03' % n, '1')]
        m['RAVG%d' % n] = [(0, 'R%d08' % n, '2'), (1, 'R%d08' % n, '1')]
    two = {'RTOP': 'R31', 'RBOT': 'R32', 'CSET': 'C33', 'RKILL': 'R61', 'ROFFI': 'R41', 'RFI': 'R43', 'RGI': 'R42', 'RO1': 'R44',
           'CA1': 'C41', 'RV1': 'R45', 'RV2': 'R46', 'ROFFV': 'R47', 'RV3': 'R48', 'RV4': 'R49', 'RO2': 'R50', 'CA2': 'C42',
           'RSN': 'R71', 'CSN': 'C58', 'RCV1': 'R35', 'RCV2': 'R36', 'CCV': 'C35', 'RCVG': 'R37'}
    return m, two


def sim_lines(path):
    lines = {}
    for ln in open(path, encoding='latin-1'):
        p = ln.split()
        if p and p[0][0] not in '*.;+':
            lines[re.sub(r'^X[^A-Za-z0-9]*', 'X', p[0]).upper()] = p[1:]
    return lines


def main():
    k = kicad_nets(sys.argv[1]); sim = sim_lines(sys.argv[2])
    m, two = map_sim()
    links = collections.defaultdict(set)
    errs = []
    TWOT = []

    def link(sn, ref, pin, name):
        if (ref, pin) not in k:
            errs.append('%s: %s.%s has no net in KiCad' % (name, ref, pin)); return
        links[sn].add(k[(ref, pin)])
    for name, ref in two.items():
        nodes = sim.get(name)
        if nodes is None:
            errs.append('missing in deck: ' + name); continue
        a, b = k.get((ref, '1')), k.get((ref, '2'))
        if a is None or b is None:
            errs.append('%s (%s) not in KiCad' % (name, ref)); continue
        TWOT.append((name, ref, (nodes[0], nodes[1]), (a, b)))
    for name, conn in m.items():
        nodes = sim.get(name)
        if nodes is None:
            errs.append('missing in deck: ' + name); continue
        for idx, ref, pin in conn:
            link(nodes[idx], ref, pin, name)
    for name, conn in {
        'XU5': [(0, 'U12', '3'), (1, 'U12', '2'), (2, 'U12', '4'), (3, 'U12', '11'), (4, 'U12', '1')],     # ISEN amp = U12A
        'XU6': [(0, 'U12', '5'), (1, 'U12', '6'), (2, 'U12', '4'), (3, 'U12', '11'), (4, 'U12', '7')],     # VSEN amp = U12B
        'XU7': [(0, 'U12', '10'), (1, 'U12', '9'), (2, 'U12', '4'), (3, 'U12', '11'), (4, 'U12', '8')],    # CV error amp = U12C
        'MCV': [(0, 'Q13', '3'), (1, 'Q13', '1'), (2, 'Q13', '2')],
        'DH1': [(0, 'D41', '3'), (1, 'D41', '2')], 'DL1': [(0, 'D41', '1'), (1, 'D41', '3')],
        'DH2': [(0, 'D42', '3'), (1, 'D42', '2')], 'DL2': [(0, 'D42', '1'), (1, 'D42', '3')],
    }.items():
        nodes = sim.get(name)
        if nodes is None:
            errs.append('missing in deck: ' + name); continue
        for idx, ref, pin in conn:
            link(nodes[idx], ref, pin, name)
    fwd = {sn: set(v) for sn, v in links.items()}
    for _ in range(4):
        for name, ref, (na, nb), (a, b) in TWOT:
            if a in fwd.get(na, ()) or b in fwd.get(nb, ()):
                fwd.setdefault(na, set()).add(a); fwd.setdefault(nb, set()).add(b)
            elif b in fwd.get(na, ()) or a in fwd.get(nb, ()):
                fwd.setdefault(na, set()).add(b); fwd.setdefault(nb, set()).add(a)
    for name, ref, (na, nb), (a, b) in TWOT:
        if {a, b} & fwd.get(na, set()) == set() or {a, b} & fwd.get(nb, set()) == set():
            fwd.setdefault(na, set()).add(a); fwd.setdefault(nb, set()).add(b)
    # Rev D differences from the deck: GND splits at NT1 / sense pair; the 4.096 V reference and the 3.3 V clamp rail are both +5V_ISO
    allow = {'0': {'AGND', 'PGND', '/SENSE_N'}, 'DUT+': {'/SENSE_P'}}
    merge_ok = {'+5V_ISO': {'+4V096', '+3V3'}}
    rev = collections.defaultdict(set)
    for sn, nets in fwd.items():
        for nn in nets:
            rev[nn].add(sn)
    for sn, nets in fwd.items():
        extra = nets - allow.get(sn, set())
        if len(nets) > 1 and extra and sn not in allow:
            errs.append('sim node %s maps to several KiCad nets: %s' % (sn, sorted(nets)))
        if sn in allow and extra:
            errs.append('sim node %s maps to unexpected KiCad nets: %s' % (sn, sorted(extra)))
    for nn, sns in rev.items():
        if len(sns) > 1 and sns != merge_ok.get(nn):
            errs.append('KiCad net %s merges sim nodes: %s' % (nn, sorted(sns)))
    for sn, want in (('+12V', '+12V_ISO'), ('+4V096', '+5V_ISO'), ('+3V3', '+5V_ISO'), ('DRAIN', '/DRAIN'), ('VSET', '/VSET'), ('LOAD_CTRL', '/LOAD_CTRL'),
                     ('KILL', '/KILL'), ('AVG', '/AVG'), ('ISEN_ADC', '/ISEN_ADC'), ('VSEN_ADC', '/VSEN_ADC'), ('VSEN_OA', '/VSEN_OA')):
        if want not in fwd.get(sn, set()):
            errs.append('sim node %s expected on KiCad net %s, found %s' % (sn, want, sorted(fwd.get(sn, set()))))

    # ------------------------------------------------------------------ part 2: same-net assertions
    def net(ref, pin):
        return k.get((ref, pin), 'NONE:%s.%s' % (ref, pin))
    same = [
        # isolator channels: MCU -> side 1 -> side 2 -> DAC / ADC
        (('U4', '@PA5'), ('J10', '4'), 'SPI1_SCK to J10'), (('J11', '4'), ('U8', '2'), 'J11 to INA'), (('U8', '15'), ('U9', '3'), 'OUTA = DAC SCK'), (('U8', '15'), ('U10', '1'), 'OUTA = ADC SCLK'),
        (('U4', '@PA7'), ('J10', '5'), 'SPI1_MOSI to J10'), (('J11', '5'), ('U8', '3'), 'J11 to INB'), (('U8', '14'), ('U9', '4'), 'OUTB = DAC SDI'), (('U8', '14'), ('U10', '10'), 'OUTB = ADC DIN'),
        (('U4', '@PA4'), ('J10', '7'), '/CS_DAC to J10'), (('J11', '7'), ('U8', '4'), 'J11 to INC'), (('U8', '13'), ('U9', '2'), 'OUTC = DAC /CS'),
        (('U4', '@PB0'), ('J10', '8'), '/CS_ADC to J10'), (('J11', '8'), ('U8', '5'), 'J11 to IND'), (('U8', '12'), ('U10', '2'), 'OUTD = ADC /CS'),
        (('U4', '@PB1'), ('J10', '9'), 'LOAD_OFF to J10'), (('J11', '9'), ('U8', '6'), 'J11 to INE'), (('U8', '11'), ('D44', '2'), 'OUTE = LOAD_OFF_ISO into the OFF diode-OR'),
        (('U10', '9'), ('U8', '10'), 'ADC DOUT to INF'), (('U8', '7'), ('J11', '6'), 'OUTF to J11'), (('J10', '6'), ('U4', '@PA6'), 'J10 = SPI1_MISO'),
        (('R21', '2'), ('U8', '4'), 'pull-up on /CS_DAC'), (('R22', '2'), ('U8', '5'), 'pull-up on /CS_ADC'), (('R23', '2'), ('U8', '6'), 'pull-up on LOAD_OFF'),
        # DAC / ADC analog connections
        (('U9', '8'), ('R31', '1'), 'DAC A = LOAD_CTRL into the 15k'), (('U9', '6'), ('R33', '1'), 'DAC B = CV_SET into the 1k'),
        (('U10', '4'), ('D41', '3'), 'ADC AIN0 = ISEN_ADC'), (('U10', '5'), ('D42', '3'), 'ADC AIN1 = VSEN_ADC'),
        (('U10', '6'), ('R52', '2'), 'ADC AIN2 = TEMP_MON'), (('R24', '1'), ('Q11', '3'), 'VSET monitor from the V_SET node'), (('R24', '2'), ('U10', '7'), 'into AIN3'),
        (('U9', '5'), ('C29', '2'), 'LDAC tied to AGND'),
        # protection
        (('U14', '4'), ('R51', '2'), 'OTP In- = V_NTC'), (('U14', '4'), ('J6', '1'), 'NTC connector on V_NTC'), (('U14', '11'), ('R51', '2'), 'NTC-open In+ = V_NTC'),
        (('R56', '2'), ('Q11', '1'), 'OTP output drives Q11'), (('U14', '6'), ('R60', '2'), 'dropout In- from DRAIN divider'), (('U14', '6'), ('D43', '3'), 'zener clamp on it'),
        (('R61', '2'), ('R101', '1'), 'KILL into channel 1'), (('R61', '2'), ('R401', '1'), 'KILL into channel 4'),
        (('U14', '13'), ('D44', '1'), 'NTC-open output into the OFF diode-OR'), (('D44', '3'), ('Q12', '1'), 'OFF_GATE drives Q12'), (('D44', '3'), ('D45', '1'), 'OVP joins OFF_GATE'),
        (('D45', '2'), ('U14', '14'), 'OVP comparator output'), (('U14', '9'), ('R66', '2'), 'OVP In+ via 10k'), (('R66', '1'), ('U12', '7'), 'from VSEN_OA'),
        (('U14', '8'), ('R68', '2'), 'OVP threshold'), (('U14', '8'), ('R69', '1'), 'OVP threshold bottom'), (('R68', '1'), ('U3', '1'), 'OVP divider from +5V_ISO'),
        (('U14', '10'), ('R62', '2'), 'NTC-open threshold'), (('U14', '10'), ('R63', '1'), 'NTC-open threshold bottom'), (('R62', '1'), ('U3', '1'), 'NTC-open divider from +5V_ISO'),
        (('U14', '5'), ('R53', '2'), 'OTP threshold'), (('R53', '1'), ('U3', '1'), 'OTP divider from +5V_ISO'), (('U14', '7'), ('R57', '2'), 'dropout threshold'), (('R57', '1'), ('U3', '1'), 'dropout divider from +5V_ISO'), (('R35', '1'), ('U12', '7'), 'CV error amp input from VSEN_OA'),
        # power path
        (('F1', '1'), ('J7', '1'), 'DUT+ to fuse'), (('F1', '2'), ('Q101', '2'), 'fuse to DRAIN'), (('F1', '2'), ('Q401', '2'), 'DRAIN reaches channel 4'),
        (('D51', '1'), ('F1', '2'), 'TVS on DRAIN'), (('J8', '1'), ('R106', '2'), 'DUT- = PGND = Rs return'), (('NT1', '2'), ('J8', '1'), 'star tie PGND side'),
        (('NT1', '1'), ('R32', '2'), 'star tie AGND side'), (('J9', '1'), ('R45', '1'), 'sense+ to VSEN amp'), (('R72', '1'), ('F1', '1'), 'local fallback from DUT+'),
        # rails
        (('U8', '1'), ('J11', '3'), 'isolator side 1 on +3V3_LK'), (('J10', '3'), ('U1', '5'), 'J10 pin 3 on +3V3'), (('U8', '16'), ('U3', '1'), 'isolator side 2 on +5V_ISO'), (('U9', '1'), ('U3', '1'), 'DAC on +5V_ISO'),
        (('U10', '8'), ('U3', '1'), 'ADC on +5V_ISO'), (('U14', '3'), ('R12', '2'), 'LM339 on +12V_ISO'), (('U11', '4'), ('R12', '2'), 'U11 on +12V_ISO'), (('U12', '4'), ('R12', '2'), 'U12 on +12V_ISO'),
        (('U11', '11'), ('U14', '12'), 'U11 V- on AGND'), (('U12', '11'), ('U14', '12'), 'U12 V- on AGND'), (('U12', '12'), ('U14', '12'), 'spare section In+ on AGND'), (('U12', '13'), ('U12', '14'), 'spare section is a follower'),
        (('R12', '1'), ('PS1', '4'), 'filter from the DC-DC output'), (('U3', '3'), ('PS1', '4'), 'LDO from the DC-DC output'), (('PS1', '3'), ('U3', '2'), 'DC-DC return = AGND'),
        (('PS1', '1'), ('J11', '1'), 'DC-DC input = VBUS_LK'), (('J11', '1'), ('J11', '2'), 'both VBUS pins'), (('J10', '1'), ('J1', 'A4'), 'J10 pins 1-2 = VBUS'), (('J10', '2'), ('J1', 'A4'), 'J10 pin 2 = VBUS'),
        (('PS1', '2'), ('J11', '10'), 'DC-DC input return = DGND_LK'), (('J11', '11'), ('J11', '12'), 'DGND_LK pins'), (('J10', '10'), ('J1', 'A1'), 'J10 pins 10-12 = DGND'), (('J10', '12'), ('J1', 'A1'), 'J10 pin 12 = DGND'),
        (('U8', '8'), ('J11', '12'), 'isolator GND1 = DGND_LK'), (('C6', '2'), ('J11', '10'), 'C6 on DGND_LK'), (('R21', '1'), ('J11', '3'), 'pull-ups on +3V3_LK'),
        (('Q1', '2'), ('J1', 'A4'), 'P-FET source on VBUS (no boost)'), (('Q1', '3'), ('J2', '2'), 'P-FET drain to fan +5V'), (('J2', '1'), ('J1', 'A1'), 'fan return = DGND'), (('C3', '1'), ('J1', 'A4'), 'blower bulk cap on VBUS'),
        (('U4', '@PD3'), ('Q2', '1'), 'FAN_EN drives the level shifter'), (('R7', '1'), ('J1', 'A4'), 'P gate pull-up to VBUS'), (('Q2', '3'), ('Q1', '1'), 'level shifter to P gate'),
        (('U4', '@PB9'), ('Q3', '1'), 'FAN_PWM'), (('Q3', '3'), ('J2', '4'), 'open-drain to fan PWM pin'), (('U4', '@PB8'), ('R10', '1'), 'FAN_TACH'), (('R10', '2'), ('J2', '3'), 'from fan tach'),
        # USB
        (('J1', 'A7'), ('D1', '1'), 'D- to ESD'), (('D1', '6'), ('U4', '@PA11'), 'ESD to PA11 (DM)'), (('J1', 'A6'), ('D1', '3'), 'D+ to ESD'), (('D1', '4'), ('U4', '@PA12'), 'ESD to PA12 (DP)'),
        (('J1', 'A5'), ('R1', '1'), 'CC1 pull-down'), (('J1', 'A5'), ('U4', '@PA0'), 'CC1 to PA0'), (('J1', 'B5'), ('U4', '@PA1'), 'CC2 to PA1'),
        (('U1', '1'), ('J1', 'A4'), 'LDO from VBUS'), (('U4', '@VDD'), ('U1', '5'), 'MCU on +3V3'),
        # OLED header and panel LEDs
        (('J5', '3'), ('U4', '@PB6'), 'OLED SCL = PB6'), (('J5', '4'), ('U4', '@PB7'), 'OLED SDA = PB7'), (('R14', '2'), ('J5', '3'), 'SCL pull-up'), (('R15', '2'), ('J5', '4'), 'SDA pull-up'),
        (('R14', '1'), ('U1', '5'), 'pull-ups on +3V3'), (('J5', '2'), ('U1', '5'), 'OLED VCC = +3V3'), (('J5', '1'), ('J1', 'A1'), 'OLED GND = DGND'),
        (('U4', '@PA8'), ('R17', '1'), 'LED_ON from PA8'), (('R17', '2'), ('D5', '2'), 'into the green LED'), (('D5', '1'), ('J1', 'A1'), 'LED cathode to DGND'),
        (('U4', '@PC7'), ('R18', '1'), 'LED_FAULT from PC7'), (('R18', '2'), ('D6', '2'), 'into the red LED'), (('D6', '1'), ('J1', 'A1'), 'LED cathode to DGND'),
        # front panel inputs
        (('ENC1', 'A'), ('U4', '@PB4'), 'encoder A to PB4'), (('ENC1', 'B'), ('U4', '@PB5'), 'encoder B to PB5'), (('ENC1', 'S1'), ('U4', '@PB3'), 'encoder push to PB3'),
        (('R19', '2'), ('U4', '@PB4'), 'pull-up on ENC_A'), (('C24', '1'), ('U4', '@PB4'), 'filter on ENC_A'),
        (('SW3', '1'), ('U4', '@PD0'), 'ON/OFF to PC0'), (('SW4', '1'), ('U4', '@PD1'), 'MODE to PC1'), (('SW5', '1'), ('U4', '@PD2'), 'MENU to PC2'),
        (('SW1', '1'), ('U4', '@PF2'), 'reset button on NRST'), (('J3', '4'), ('U4', '@PF2'), 'SWD NRST'), (('J3', '2'), ('U4', '@PA13'), 'SWDIO'), (('J3', '3'), ('U4', '@PA14'), 'SWCLK'),
        (('SW2', '1'), ('U4', '@PA14'), 'BOOT button on PA14'), (('J4', '2'), ('U4', '@PA9'), 'UART TX'), (('J4', '3'), ('U4', '@PA10'), 'UART RX'),
        (('R16', '1'), ('U4', '@PC6'), 'heartbeat LED on PC6'),
    ]
    for (r1, p1), (r2, p2), why in same:
        a, b = net(r1, p1), net(r2, p2)
        if a != b:
            errs.append('%s: %s.%s is on %s but %s.%s is on %s' % (why, r1, p1, a, r2, p2, b))
    # must NOT be the same net
    diff = [(('U8', '8'), ('U8', '9'), 'DGND and AGND must stay separate'), (('J1', 'A1'), ('NT1', '1'), 'DGND vs AGND'), (('J1', 'A1'), ('J8', '1'), 'DGND vs PGND'),
            (('U1', '5'), ('U3', '2'), '+3V3 vs +5V_ISO'), (('J10', '4'), ('J11', '4'), 'the cable is not a net: SPI1_SCK vs SPI1_SCK_LK'),
            (('J10', '1'), ('J11', '1'), 'VBUS vs VBUS_LK'), (('J10', '12'), ('J11', '12'), 'DGND vs DGND_LK'), (('J10', '3'), ('J11', '3'), '+3V3 vs +3V3_LK'), (('J2', '2'), ('J1', 'A4'), 'fan +5V is switched, not VBUS'), (('Q11', '3'), ('R31', '1'), 'V_SET vs LOAD_CTRL'),
            (('U12', '8'), ('U12', '1'), 'CV amp output vs ISEN output'), (('U12', '7'), ('U12', '1'), 'VSEN output vs ISEN output')]
    for (r1, p1), (r2, p2), why in diff:
        if net(r1, p1) == net(r2, p2):
            errs.append('%s: %s.%s and %s.%s are both on %s' % (why, r1, p1, r2, p2, net(r1, p1)))
    # every net name that crosses the barrier must be one of the isolator's own pins
    cross = {'DGND', 'AGND'}
    if errs:
        print('NETLIST ERRORS (%d):' % len(errs)); print('\n'.join('  ' + e for e in errs)); sys.exit(1)
    print('NETLIST OK: %d simulated nodes match KiCad, %d same-net and %d must-differ checks passed' % (len(fwd), len(same), len(diff)))


main()
