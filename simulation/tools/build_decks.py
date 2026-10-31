"""Builds the LTspice decks for the DC Load Rev C power stage.
Every connection is a drawn wire; FLAGs are used only for ground, the +12 V /
+3V3 rails, and to *name* a wire so .meas statements can refer to it."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ascgen import Sheet, ltrun

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the 02_Simulation_LTspice folder
GND = '0'

# ----------------------------------------------------------------- design values
RF, CC, RG, RS = '3.3k', '1n', '47', '{Rs}'


def channel(sh, ox, oy, n, set_from_left=True, fet='FETSEL', inj=False, clamp=True, kill=True):
    """One current-sink channel. Op-amp origin at (ox, oy).
    Returns dict of key points: inp (op-amp In+), drain_top, src (source node), avg (Ravg pin)."""
    U, C, Rf, Rg, M, R = 'U%d' % n, 'C%d' % n, 'Rf%d' % n, 'Rg%d' % n, 'M%d' % n, 'Rs%d' % n
    s, fb, out, g, d = 'S%d' % n, 'FB%d' % n, 'OUT%d' % n, 'G%d' % n, 'DRAIN'
    vset = 'VSET'
    sh.sym('OpAmps\\LT1014', ox, oy, 'R0', U, 'LT1014', [vset, fb, '+12V', GND, out])
    sh.wire((ox, oy + 32), (ox, oy + 16)); sh.flag(ox, oy + 16, '+12V')
    sh.wire((ox, oy + 96), (ox, oy + 112)); sh.flag(ox, oy + 112, GND)
    # integrator capacitor across the op-amp (In- to OUT)
    sh.sym('cap', ox + 32, oy - 48, 'R90', C, CC, [out, fb])
    sh.wire((ox - 32, oy + 48), (ox - 32, oy - 32), (ox - 32, oy - 160))
    sh.wire((ox + 32, oy + 64), (ox + 80, oy + 64), (ox + 80, oy - 32), (ox + 32, oy - 32))
    # 22M from +12V into In-: +1.8 mV deliberate offset -> output sits at 0 V when V_SET = 0
    sh.sym('res', ox - 16, oy, 'R90', 'Rb%d' % n, '22Meg', [fb, '+12V']); sh.flag(ox - 112, oy + 16, '+12V')
    if kill:   # KILL line (dropout comparator) -> 4.7k + 1N4148 -> In-: forces OUT to 0 V fast
        sh.sym('res', ox - 80, oy - 64, 'R90', 'Rk%d' % n, '4.7k', ['K%d' % n, 'KILL'])
        sh.sym('diode', ox - 96, oy - 32, 'R270', 'Dk%d' % n, '1N4148', ['K%d' % n, fb])
        sh.flag(ox - 176, oy - 48, 'KILL')
    if clamp:
        sh.sym('zener', ox - 32, oy - 80, 'R270', 'Dz%d' % n, 'BZX84C6V8', [fb, out])
        sh.wire((ox + 80, oy - 32), (ox + 80, oy - 96), (ox + 32, oy - 96))
    # gate resistor and MOSFET
    sh.sym('res', ox + 224, oy + 48, 'R90', Rg, RG, [g, out])
    sh.wire((ox + 80, oy + 64), (ox + 128, oy + 64))
    sh.wire((ox + 208, oy + 64), (ox + 288, oy + 64))
    sh.sym('nmos', ox + 288, oy - 16, 'R0', M, fet, [d, g, s]); sh.flag(ox + 256, oy + 64, g)
    # source resistor to ground
    sh.sym('res', ox + 320, oy + 160, 'R0', R, RS, [s, GND])
    sh.wire((ox + 336, oy + 80), (ox + 336, oy + 128), (ox + 336, oy + 176))
    sh.flag(ox + 336, oy + 256, GND)
    # feedback resistor: source node -> In- (drawn over the top of the op-amp)
    rf_net = 'INJ%d' % n if inj else s
    sh.sym('res', ox + 64, oy - 176, 'R90', Rf, RF, [rf_net, fb])
    return dict(inp=(ox - 32, oy + 80), drain=(ox + 336, oy - 16), src=(ox + 336, oy + 128),
                rf=(ox + 48, oy - 160), names=(U, C, Rf, Rg, M, R))


def deck03():
    sh = Sheet(2000, 1100)
    ch = channel(sh, 0, 0, 1, inj=True, kill=False)
    # V_SET source (stands in for DAC + divider)
    sh.sym('voltage', -320, 64, 'R0', 'Vset', '{Ich*Rs}', ['VSET', GND])
    sh.wire((-320, 80), (-32, 80)); sh.flag(-320, 160, GND)
    sh.flag(-176, 80, 'VSET')
    # Middlebrook injection source between Rf and the source node
    sh.sym('voltage', 528, 0, 'R0', 'Vinj', 'AC 1', ['INJ1', 'S1'])
    sh.wire(ch['rf'], (528, -160), (528, 16))
    sh.wire((528, 96), (528, 128), ch['src'])
    sh.flag(528, -48, 'inj'); sh.flag(432, 128, 'src')
    # drain, snubber, DUT leads, DUT
    sh.wire(ch['drain'], (336, -352), (448, -352), (576, -352))
    sh.sym('res', 432, -352, 'R0', 'Rsn', '2.2', ['DRAIN', 'SN'])
    sh.sym('cap', 432, -256, 'R0', 'Csn', '2.2u', ['SN', GND])
    sh.wire((448, -352), (448, -336)); sh.flag(448, -192, GND)
    sh.sym('res', 672, -368, 'R90', 'Rlead', '20m', ['DL', 'DRAIN'])
    sh.sym('ind', 816, -368, 'R90', 'Llead', '{Llead}', ['DUT+', 'DL'])
    sh.wire((656, -352), (720, -352))
    sh.sym('voltage', 880, -352, 'R0', 'Vdut', '{Vdut}', ['DUT+', GND])
    sh.wire((800, -352), (880, -352), (880, -336)); sh.flag(880, -256, GND)
    sh.flag(336, -288, 'drain')
    # supply
    sh.sym('voltage', -320, -240, 'R0', 'V12', '12', ['+12V', GND])
    sh.flag(-320, -224, '+12V'); sh.flag(-320, -144, GND)
    # annotation
    sh.rect(-400, -448, 1040, 320)
    sh.text(-392, -440, 'DC LOAD Rev C - ONE CURRENT-SINK CHANNEL - LOOP GAIN (Middlebrook voltage injection)', size=3)
    sh.text(-392, -400, 'Vinj breaks the loop between the source node (low Z, 0.1 R) and Rf (3.3k): ideal injection point.\n'
                        'T(f) = -V(src)/V(inj).  In the log: PM = phase of V(src)/V(inj) at fc;  GM = -|V(src)/V(inj)| where its phase = 0.', size=1)
    sh.text(560, -200, 'DUT model: supply + 20 mR lead +\nlead inductance (1 uH ~ 1 m of\nloose lead pair, 10 uH = abuse)', size=1)
    sh.text(-392, 360, 'PASS criteria: PM >= 45 deg and GM >= 10 dB for every FET candidate, channel current\n'
                       '25 mA ... 2.5 A and 1 ... 10 uH leads.  Rf=3.3k, Cc=1n, Rg=47 chosen from this sweep.', size=2)
    sh.text(-392, 460, '.param fet=1 Ich=2.5 Llead=1u Vdut=24 Rs=0.1\n'
                       '.step param fet list 1 2 3 4   ; 1 IRFP250N  2 IRFP240  3 IRF530  4 IXTH88N30P (big-die proxy)\n'
                       '.step param Ich list 0.025 0.25 2.5\n'
                       '.step param Llead list 1u 10u\n'
                       '.ac dec 50 10 10Meg\n'
                       '.meas AC fc WHEN mag(V(src)/V(inj))=1\n'
                       '.meas AC PM FIND V(src)/V(inj) AT fc\n'
                       '.meas AC GM FIND V(src)/V(inj) WHEN ph(V(src)/V(inj))=0\n'
                       '.include ../lib/fet_models.lib\n.include ../lib/misc_models.lib', directive=True)
    return sh


def adc_out(sh, x, y, tag, n):
    """Op-amp output junction at (x,y) -> 1k -> ADC pin node with 10n and BAT54 clamps to +3V3/GND."""
    node = tag + '_ADC'
    sh.sym('res', x + 144, y - 16, 'R90', 'Ro%d' % n, '1k', [node, tag + '_OA'])
    sh.wire((x, y), (x + 48, y))
    sh.wire((x + 128, y), (x + 192, y), (x + 256, y), (x + 320, y), (x + 384, y))
    sh.sym('cap', x + 176, y, 'R0', 'Ca%d' % n, '10n', [node, GND]); sh.flag(x + 192, y + 64, GND)
    sh.sym('schottky', x + 272, y, 'R180', 'Dh%d' % n, 'BAT54', [node, '+3V3'])
    sh.flag(x + 256, y - 64, '+3V3')
    sh.sym('schottky', x + 336, y + 64, 'R180', 'Dl%d' % n, 'BAT54', [GND, node])
    sh.flag(x + 320, y + 64, GND)
    sh.flag(x + 384, y, node)
    sh.text(x + 216, y + 96, '%s to STM32 ADC\n(1k + 10n, clamped\n to 3V3 by BAT54S)' % tag, size=1)


def system(title, vctrl_value, vdut_value, votp_value='0', fet='FETSEL', dut_current=None):
    """Full Rev C analog stage: control divider, 4 channels, ISEN averaging amp,
    VSEN difference amp, drain snubber, fuse, DUT leads, DUT."""
    sh = Sheet(3000, 3000)
    oys = [0, 576, 1152, 1728]
    # ---------------- control input: DAC -> 15k/1k divider -> V_SET bus
    sh.sym('voltage', -1136, 64, 'R0', 'Vctrl', vctrl_value, ['LOAD_CTRL', GND]); sh.flag(-1136, 160, GND)
    sh.sym('res', -944, 64, 'R90', 'Rtop', '15k', ['VSET', 'LOAD_CTRL'])
    sh.wire((-1136, 80), (-1040, 80)); sh.flag(-1088, 80, 'LOAD_CTRL')
    sh.wire((-960, 80), (-880, 80), (-800, 80), (-640, 80), (-336, 80), (-192, 80), (-32, 80))
    sh.sym('res', -896, 80, 'R0', 'Rbot', '1k', ['VSET', GND]); sh.wire((-880, 80), (-880, 96)); sh.flag(-880, 176, GND)
    sh.sym('cap', -816, 96, 'R0', 'Cset', '10n', ['VSET', GND]); sh.wire((-800, 80), (-800, 96)); sh.flag(-800, 160, GND)
    # over-temperature pull-down (LM339 open collector, modelled as a switch)
    sh.sym('sw', -640, 80, 'R0', 'Sotp', 'SWOTP', ['VSET', GND, 'OTP', GND])
    sh.wire((-640, 80), (-640, 96)); sh.flag(-640, 176, GND)
    sh.wire((-688, 112), (-720, 112)); sh.flag(-720, 112, GND)
    sh.sym('voltage', -752, 240, 'R0', 'Votp', votp_value, ['OTP', GND]); sh.flag(-752, 336, GND)
    sh.wire((-688, 160), (-688, 256), (-752, 256)); sh.flag(-720, 256, 'OTP')
    # dropout detector -> KILL line.  Sdrop (LM339 #3 output) holds KILL low while V(DRAIN) > 0.5 V;
    # when the DUT is absent / collapses it lets go and Rkill pulls KILL to +12 V.
    sh.sym('res', -352, 400, 'R0', 'Rkill', '10k', ['+12V', 'KILL']); sh.flag(-336, 416, '+12V')
    sh.sym('sw', -336, 480, 'R0', 'Sdrop', 'SWDROP', ['KILL', GND, 'DRAIN', 'VDREF'])
    sh.flag(-336, 576, GND)
    sh.wire((-336, 496), (-272, 496)); sh.flag(-272, 496, 'KILL')
    sh.wire((-384, 560), (-384, 624)); sh.flag(-384, 624, 'DRAIN')
    sh.sym('voltage', -448, 496, 'R0', 'Vdref', '0.5', ['VDREF', GND]); sh.flag(-448, 592, GND)
    sh.wire((-384, 512), (-448, 512))
    sh.flag(-256, 80, 'VSET')
    sh.text(-1256, -40, 'LOAD_CTRL from MCP4725\n(control board, 0-4.096 V)', size=1)
    sh.text(-1000, 208, 'V_SET = LOAD_CTRL / 16\n(0 - 0.256 V per channel)\nCset: 9.4 us slew filter', size=1)
    sh.text(-840, 368, 'Sotp: LM339 #2 open-collector\nover-temp pull-down\n(Votp = 0 V: open)', size=1)
    sh.text(-560, 656, 'Sdrop = LM339 #3 (open collector): holds KILL low while\nV(DRAIN) > 0.5 V.  DUT absent / collapsed -> KILL = 12 V ->\nDk/Rk lift every In- -> all gates to 0 V (no wind-up).\nDRAIN and KILL reach here by net label.', size=1)
    # ---------------- 4 channels
    chans = [channel(sh, 0, oy, k + 1, fet=fet) for k, oy in enumerate(oys)]
    for k, (oy, ch) in enumerate(zip(oys, chans)):
        n = k + 1
        if k:
            sh.wire((-192, oys[k - 1] + 80), (-192, oy + 80), (-32, oy + 80))
        # feedback return: Rf right pin -> over the top -> down to the source node
        sh.wire(ch['rf'], (464, oy - 160), (464, oy + 128), ch['src'])
        # drain riser -> DRAIN bus (x=640)
        sh.wire(ch['drain'], (336, oy - 208), (640, oy - 208))
        if k:
            sh.wire((640, oys[k - 1] - 208), (640, oy - 208))
        # ISEN averaging resistor: source node -> AVG bus (x=560)
        sh.sym('res', 560, oy + 112, 'R90', 'Ravg%d' % n, '10k', ['AVG', 'S%d' % n])
        sh.wire((544, oy + 128), (560, oy + 128))
        if k:
            sh.wire((560, oys[k - 1] + 128), (560, oy + 128))
        sh.flag(400, oy + 128, 'S%d' % n)
        sh.text(-192, oy - 224, 'CH%d' % n, size=3)
    # ---------------- ISEN amplifier (non-inverting, G = 1 + 110k/10k = 12)
    ix, iy = 800, 2112
    sh.wire((560, oys[-1] + 128), (560, iy + 160), (736, iy + 160), (736, iy + 80), (ix - 32, iy + 80))
    sh.flag(560, iy, 'AVG')
    # 1M from +4.096 V: lifts AVG by ~10 mV (ISEN +123 mV) so the LT1013 never works into its ~35 mV output floor
    sh.sym('res', 576, 2000, 'R90', 'Roffi', '1Meg', ['AVG', '+4V096']); sh.flag(480, 2016, '+4V096')
    sh.sym('OpAmps\\LT1013', ix, iy, 'R0', 'U5', 'LT1013', ['AVG', 'FBI', '+12V', GND, 'ISEN_OA'])
    sh.wire((ix, iy + 32), (ix, iy + 16)); sh.flag(ix, iy + 16, '+12V')
    sh.wire((ix, iy + 96), (ix, iy + 112)); sh.flag(ix, iy + 112, GND)
    sh.sym('res', ix + 64, iy - 48, 'R90', 'Rfi', '110k', ['ISEN_OA', 'FBI'])
    sh.wire((ix - 32, iy + 48), (ix - 32, iy - 32), (ix - 112, iy - 32))
    sh.sym('res', ix - 128, iy - 48, 'R0', 'Rgi', '10k', ['FBI', GND]); sh.flag(ix - 112, iy + 48, GND)
    sh.wire((ix + 32, iy + 64), (ix + 80, iy + 64), (ix + 80, iy - 32), (ix + 48, iy - 32))
    adc_out(sh, ix + 80, iy + 64, 'ISEN', 1)
    sh.text(ix - 224, iy - 160, 'ISEN: AVG = mean of the 4 source voltages = I_total x Rs / 4\nV(ISEN) = 0.30 V/A + 0.12 V offset (3.19 V at 10.24 A)', size=1)
    # ---------------- drain snubber, fuse, leads, DUT
    sh.wire((640, -208), (640, -400), (752, -400), (832, -400))
    sh.sym('res', 736, -400, 'R0', 'Rsn', '2.2', ['DRAIN', 'SN'])
    sh.sym('cap', 736, -304, 'R0', 'Csn', '2.2u', ['SN', GND]); sh.flag(752, -240, GND)
    sh.wire((752, -400), (752, -384))
    sh.sym('res', 928, -416, 'R90', 'Rfuse', '5m', ['DUT+', 'DRAIN'])
    sh.wire((912, -400), (976, -400), (1040, -400))
    sh.sym('res', 1136, -416, 'R90', 'Rlead', '20m', ['DL', 'DUT+'])
    sh.sym('ind', 1264, -416, 'R90', 'Llead', '{Llead}', ['DUTV', 'DL'])
    sh.wire((1120, -400), (1168, -400))
    if dut_current:   # current-source DUT with a compliance clamp and optional output capacitance
        sh.sym('current', 1328, -304, 'R180', 'Idut', dut_current, [GND, 'DUTV'])
        sh.wire((1248, -400), (1328, -400), (1328, -384)); sh.flag(1328, -304, GND)
        sh.wire((1328, -400), (1392, -400), (1440, -400))
        sh.sym('cap', 1376, -400, 'R0', 'Cdut', '{Cx}', ['DUTV', GND]); sh.flag(1392, -336, GND)
        sh.sym('diode', 1440, -384, 'R270', 'Dcomp', 'DCL', ['DUTV', 'VCOMP'])
        sh.sym('voltage', 1504, -416, 'R0', 'Vcomp', vdut_value, ['VCOMP', GND]); sh.flag(1504, -320, GND)
    else:
        sh.sym('voltage', 1328, -400, 'R0', 'Vdut', vdut_value, ['DUTV', GND])
        sh.wire((1248, -400), (1328, -400), (1328, -384)); sh.flag(1328, -304, GND)
    sh.flag(976, -400, 'DUT+'); sh.flag(640, -320, 'DRAIN')
    sh.text(824, -488, 'F1 15 A fast\n(5 mR)', size=1)
    sh.text(1056, -488, 'DUT lead pair (+ side lumped)', size=1)
    sh.text(1392, -288, 'DUT (PSU / battery under test)', size=1)
    sh.text(712, -216, 'Snubber: damps\nlead L vs Coss', size=1)
    # ---------------- VSEN difference amplifier (G = 10k/200k = 0.05)
    vx, vy = 1232, -96
    sh.wire((976, -400), (976, -16), (1008, -16))
    sh.sym('res', 1104, -32, 'R90', 'Rv1', '200k', ['VP', 'DUT+'])
    sh.wire((1088, -16), (1136, -16), (vx - 32, -16))
    sh.sym('res', 1120, -16, 'R0', 'Rv2', '10k', ['VP', GND]); sh.flag(1136, 80, GND)
    sh.wire((1136, -16), (1136, 0))
    # 470k from +4.096 V: ~+85 mV output offset keeps U6 off its output floor (removed by zero calibration)
    sh.sym('res', 1152, -112, 'R0', 'Roffv', '470k', ['+4V096', 'VP']); sh.flag(1168, -96, '+4V096')
    sh.sym('OpAmps\\LT1013', vx, vy, 'R0', 'U6', 'LT1013', ['VP', 'VM', '+12V', GND, 'VSEN_OA'])
    sh.wire((vx, vy + 32), (vx, vy + 16)); sh.flag(vx, vy + 16, '+12V')
    sh.wire((vx, vy + 96), (vx, vy + 112)); sh.flag(vx, vy + 112, GND)
    sh.sym('res', 1104, -160, 'R90', 'Rv3', '200k', ['VM', GND])
    sh.wire((1008, -144), (1008, -112)); sh.flag(1008, -112, GND)
    sh.wire((1088, -144), (vx - 32, -144), (vx - 16, -144))
    sh.wire((vx - 32, vy + 48), (vx - 32, -144))
    sh.sym('res', 1312, -160, 'R90', 'Rv4', '10k', ['VSEN_OA', 'VM'])
    sh.wire((1296, -144), (1312, -144), (1312, vy + 64), (vx + 32, vy + 64))
    adc_out(sh, 1312, vy + 64, 'VSEN', 2)
    sh.text(1000, -208, 'DUT- sense\n(= board GND at\nthe DUT- terminal)', size=1)
    sh.text(1000, 160, 'VSEN = 0.049 x (V(DUT+) - V(DUT-)) + 0.085 V\n3.0 V at 59 V, ADC clips at 65 V', size=1)
    # ---------------- supplies
    sh.sym('voltage', -1136, 640, 'R0', 'V12', '12', ['+12V', GND]); sh.flag(-1136, 656, '+12V'); sh.flag(-1136, 736, GND)
    sh.sym('voltage', -1136, 896, 'R0', 'V33', '3.3', ['+3V3', GND]); sh.flag(-1136, 912, '+3V3'); sh.flag(-1136, 992, GND)
    sh.sym('voltage', -1136, 1152, 'R0', 'V4096', '4.096', ['+4V096', GND]); sh.flag(-1136, 1168, '+4V096'); sh.flag(-1136, 1248, GND)
    sh.text(-1256, 560, 'Rails from the control board\n(16-pin connector P1)', size=1)
    sh.text(-1256, -400, title, size=3)
    return sh


SYS_NOTE = ('Each channel: LT1014 (1/4) forces V(Sn) = V_SET, so I_ch = V_SET / Rs  (Rs = 2 x 0.2R 2512 in parallel).\n'
            'Dz (6.8 V) limits wind-up; Dk/Rk let the dropout detector force the op-amp low; Rb (22M) = +1.8 mV offset -> 0 A at V_SET = 0.\n'
            'Rf/Cc = 3.3k/1n integrator, Rg = 47R.  I_total = 4 x V_SET / 0.1 = 2.5 A per volt of LOAD_CTRL (10.24 A full scale).')
SWMODEL = ('.model SWOTP SW(Ron=2 Roff=1G Vt=1 Vh=0)    ; LM339 + 2N7002 pull-down\n'
           '.model SWDROP SW(Ron=50 Roff=1G Vt=0 Vh=50m) ; LM339 output, 50 mV hysteresis\n'
           '.include ../lib/misc_models.lib')


def deck01():
    sh = system('DC LOAD Rev C - ANALOG STAGE - 01 DC TRANSFER', '0', '{Vdut}')
    sh.text(-1256, -320, SYS_NOTE, size=1)
    sh.text(-1256, 2400, '.param fet=1 Rs=0.1 Vdut=12 Llead=1u\n'
                         '.step param Vdut list 1 2 12 48\n'
                         '.dc Vctrl 0 4.096 8m\n'
                         '.meas DC Itot_FS FIND -I(Vdut) AT 4.096\n'
                         '.meas DC Itot_1V FIND -I(Vdut) AT 1\n'
                         '.meas DC gain_A_per_V PARAM (Itot_FS-Itot_1V)/3.096\n'
                         '.meas DC Ich1_FS FIND Id(M1) AT 4.096\n'
                         '.meas DC Ich4_FS FIND Id(M4) AT 4.096\n'
                         '.meas DC ISEN_0 FIND V(ISEN_ADC) AT 0\n'
                         '.meas DC ISEN_FS FIND V(ISEN_ADC) AT 4.096\n'
                         '.meas DC ISEN_err_pct_FS PARAM 100*((ISEN_FS-ISEN_0)/(0.3*0.997506) - Itot_FS)/Itot_FS\n'
                         '.meas DC VSEN FIND V(VSEN_ADC) AT 2\n'
                         '.meas DC VDUTp FIND V(DUT+) AT 2\n'
                         '.meas DC VSEN_ideal PARAM 1.05*(VDUTp*9791.67/209791.67 + 4.096*9523.8/479523.8)\n'
                         '.meas DC VSEN_err_mV PARAM 1000*(VSEN-VSEN_ideal)\n'
                         '.meas DC VSEN_err_pct_of_reading PARAM 100*(VSEN-VSEN_ideal)/(VSEN_ideal-0.08548)\n'
                         '.meas DC Ploss_FS FIND V(DRAIN)*(-I(Vdut)) AT 4.096\n'
                         '.include ../lib/fet_models.lib\n' + SWMODEL, directive=True)
    sh.text(-1256, 2160, 'TEST: sweep LOAD_CTRL 0 -> 4.096 V at DUT = 1 / 2 / 12 / 48 V.\n'
                         'EXPECT: 2.50 A/V, ~10.2 A full scale, channels equal; ISEN/VSEN errors vs their ideal (offset-\n'
                         'corrected) transfer < 0.5 %.  Ideal formulas are written out in the .meas lines.', size=2)
    return sh


ISUM = '(I(Rs1)+I(Rs2)+I(Rs3)+I(Rs4))'


def deck02():
    pwl = 'PWL(0 0.4096 100u 0.4096 101u 3.6864 400u 3.6864 401u 0.4096 700u 0.4096 701u 0.8192 1m 0.8192 1.001m 0.4096)'
    sh = system('DC LOAD Rev C - ANALOG STAGE - 02 STEP RESPONSE', pwl, '{Vdut}')
    sh.text(-1256, -320, SYS_NOTE, size=1)
    sh.text(-1256, 2400, '.param fet=1 Rs=0.1 Vdut=24 Llead=1u\n'
                         '.step param fet list 1 2 3 4\n'
                         '.step param Llead list 1u 10u\n'
                         '.tran 0 1.3m 0 100n\n'
                         '.meas TRAN t_rise_us TRIG ' + ISUM + '=2.6 RISE=1 TARG ' + ISUM + '=8.4 RISE=1\n'
                         '.meas TRAN Ipk_up MAX ' + ISUM + ' FROM 100u TO 400u\n'
                         '.meas TRAN I_hi FIND ' + ISUM + ' AT 395u\n'
                         '.meas TRAN I_lo FIND ' + ISUM + ' AT 95u\n'
                         '.meas TRAN overshoot_pct PARAM 100*(Ipk_up-I_hi)/(I_hi-I_lo)\n'
                         '.meas TRAN I_at_20us FIND ' + ISUM + ' AT 121u\n'
                         '.meas TRAN I_at_50us FIND ' + ISUM + ' AT 151u\n'
                         '.meas TRAN t_fall_us TRIG ' + ISUM + '=8.4 FALL=1 TARG ' + ISUM + '=2.6 FALL=1\n'
                         '.meas TRAN Imin_dn MIN ' + ISUM + ' FROM 400u TO 700u\n'
                         '.meas TRAN undershoot_pct PARAM 100*(I_lo-Imin_dn)/(I_hi-I_lo)\n'
                         '.meas TRAN Ipk_small MAX ' + ISUM + ' FROM 700u TO 1m\n'
                         '.meas TRAN I_small FIND ' + ISUM + ' AT 995u\n'
                         '.meas TRAN small_overshoot_pct PARAM 100*(Ipk_small-I_small)/(I_small-I_lo)\n'
                         '.include ../lib/fet_models.lib\n' + SWMODEL, directive=True)
    sh.text(-1256, 2160, 'TEST: LOAD_CTRL steps 1 A -> 9 A -> 1 A (large signal) then 1 A -> 2 A (small signal),\n'
                         '1 us DAC edge, DUT = 24 V with 1 uH / 10 uH leads, all four MOSFET candidates.\n'
                         'EXPECT: no ringing, overshoot < 5 %, 10-90 % rise in tens of us (filter + loop).', size=2)
    return sh


def deck04():
    vd = 'PWL(0 0 200u 0 201u 24 1m 24 1.001m 0.4 1.5m 0.4 1.501m 24 3.5m 24)'
    vo = 'PWL(0 0 2.5m 0 2.501m 5 3m 5 3.001m 0)'
    sh = system('DC LOAD Rev C - ANALOG STAGE - 04 FAULT CASES', '3.2768', vd, vo)
    sh.text(-1256, -320, 'Set point fixed at 8 A (LOAD_CTRL = 3.2768 V).  Timeline:\n'
                         ' 0.2 ms  DUT hot-plugged with the load already enabled (0 -> 24 V in 1 us)\n'
                         ' 1.0 ms  DUT collapses to 0.4 V for 0.5 ms (op-amps rail high = integrator wind-up)\n'
                         ' 1.5 ms  DUT recovers to 24 V in 1 us  -> current overshoot from wind-up\n'
                         ' 2.5 ms  over-temperature trip pulls V_SET to 0 for 0.5 ms', size=1)
    sh.text(-1256, 2400, '.param fet=1 Rs=0.1 Llead=1u\n'
                         '.step param fet list 1 2 3 4\n'
                         '.tran 0 3.5m 0 100n\n'
                         '.meas TRAN Ipk_hotplug MAX ' + ISUM + ' FROM 200u TO 1m\n'
                         '.meas TRAN I_during_dropout FIND ' + ISUM + ' AT 1.4m\n'
                         '.meas TRAN Ipk_recovery MAX ' + ISUM + ' FROM 1.5m TO 2.4m\n'
                         '.meas TRAN I_rec_20us FIND ' + ISUM + ' AT 1.521m\n'
                         '.meas TRAN I_rec_100us FIND ' + ISUM + ' AT 1.601m\n'
                         '.meas TRAN Epk_recovery_mJ INTEG 1000*V(DRAIN)*' + ISUM + ' FROM 1.5m TO 1.7m\n'
                         '.meas TRAN t_otp_off TRIG V(OTP)=1 RISE=1 TARG ' + ISUM + '=0.8 TD=2.5m FALL=1\n'
                         '.meas TRAN I_otp FIND ' + ISUM + ' AT 2.9m\n'
                         '.include ../lib/fet_models.lib\n' + SWMODEL, directive=True)
    sh.text(-1256, 2160, 'EXPECT: hot-plug overshoot small; dropout recovery shows wind-up overshoot (quantified in log);\n'
                         'OTP pull-down turns all 4 channels off within ~tens of us.', size=2)
    return sh



def deck00():
    """Rev B power board AS BUILT (one of its two identical channels) + its VSEN amplifier."""
    sh = Sheet(2000, 1400)
    OA = 'OpAmps\\UniversalOpAmp2'
    LMV = dict(value2='Avol=100k GBW=1Meg Slew=1Meg', spiceline='Ilimit=40m Rail=0 Vos=0')
    # control input: LOAD_CTRL -> R16 68k / R17 12k -> Control_Voltage
    sh.sym('voltage', -560, 0, 'R0', 'Vctrl', '0', ['LOAD_CTRL', GND]); sh.flag(-560, 96, GND)
    sh.sym('res', -368, 0, 'R90', 'R16', '68k', ['CV', 'LOAD_CTRL'])
    sh.wire((-560, 16), (-464, 16)); sh.flag(-512, 16, 'LOAD_CTRL')
    sh.wire((-384, 16), (-304, 16), (-32, 16)); sh.flag(-176, 16, 'Control_Voltage')
    sh.sym('res', -320, 16, 'R0', 'R17', '12k', ['CV', GND]); sh.wire((-304, 16), (-304, 32)); sh.flag(-304, 112, GND)
    # U3A LMV358 on the +4.096 V reference rail
    sh.sym(OA, 0, 0, 'R0', 'U3A', None, ['CV', 'FB', '+4V096', GND, 'OUT'], **LMV)
    sh.wire((0, -32), (0, -48)); sh.flag(0, -48, '+4V096')
    sh.wire((0, 32), (0, 48)); sh.flag(0, 48, GND)
    sh.sym('cap', 32, -80, 'R90', 'C4', '220p', ['OUT', 'FB'])
    sh.wire((-32, -16), (-32, -64), (-32, -160))
    sh.wire((32, 0), (80, 0), (80, -64), (32, -64))
    sh.sym('res', 224, -16, 'R90', 'R6', '100', ['GATE', 'OUT'])
    sh.wire((80, 0), (128, 0)); sh.wire((208, 0), (288, 0)); sh.flag(256, 0, 'gate')
    sh.sym('nmos', 288, -80, 'R0', 'Q1', 'IRF530_VTH', ['DUT+', 'GATE', 'SRC'])
    sh.sym('res', 320, 96, 'R0', 'R12_13', '0.1', ['SRC', 'RSHUNT'])
    sh.wire((336, 16), (336, 64), (336, 112)); sh.flag(336, 64, 'Source1')
    sh.sym('res', 320, 224, 'R0', 'R5', '5m', ['RSHUNT', GND]); sh.flag(336, 320, GND)
    sh.wire((336, 192), (336, 240)); sh.flag(336, 224, 'Rshunt')
    sh.sym('res', 64, -176, 'R90', 'R9', '3.3k', ['SRC', 'FB'])
    sh.wire((48, -160), (432, -160), (432, 64), (336, 64))
    # DUT
    sh.wire((336, -80), (336, -256), (560, -256)); sh.flag(448, -256, 'DUT+')
    sh.sym('res', 656, -272, 'R90', 'Rlead', '25m', ['DUTV', 'DUT+'])
    sh.sym('voltage', 720, -256, 'R0', 'Vdut', '{Vdut}', ['DUTV', GND]); sh.flag(720, -160, GND)
    sh.wire((640, -256), (720, -256), (720, -240))
    # VSEN amplifier exactly as drawn on Power Monitor.SchDoc (U1B + U1A buffer folded into one)
    sh.sym(OA, 0, 512, 'R0', 'U1B', None, ['VPOS', 'VNEG', '+4V096', GND, 'VSEN'], **LMV)
    sh.wire((0, 480), (0, 464)); sh.flag(0, 464, '+4V096')
    sh.wire((0, 544), (0, 560)); sh.flag(0, 560, GND)
    sh.sym('res', -128, 512, 'R90', 'R2', '20k', ['VPOS', 'DUT+']); sh.flag(-224, 528, 'DUT+')
    sh.wire((-144, 528), (-80, 528), (-32, 528))
    sh.wire((-80, 528), (-80, 608), (0, 608))
    sh.sym('res', 96, 592, 'R90', 'R1', '2k', ['VSEN', 'VPOS'])
    sh.wire((80, 608), (112, 608), (112, 512), (32, 512)); sh.wire((112, 512), (176, 512)); sh.flag(176, 512, 'VSEN')
    sh.sym('res', -128, 416, 'R90', 'R3', '20k', ['VNEG', GND]); sh.flag(-224, 432, GND)
    sh.wire((-144, 432), (-32, 432), (-32, 496)); sh.wire((-32, 432), (16, 432))
    sh.sym('res', 112, 416, 'R90', 'R4', '2k', [GND, 'VNEG']); sh.wire((96, 432), (128, 432)); sh.flag(128, 432, GND)
    sh.sym('voltage', -560, -256, 'R0', 'V4096', '4.096', ['+4V096', GND]); sh.flag(-560, -240, '+4V096'); sh.flag(-560, -160, GND)
    sh.text(-640, -440, 'BASELINE - Rev B POWER BOARD AS BUILT (Nov 2024) - why it cannot reach its own full scale', size=3)
    sh.text(-640, -400, 'One of the two identical channels.  U3 = LMV358 powered from +4.096 V (REF5040) -> gate can never exceed ~4.1 V.\n'
                        'IRF530 VGS(th) is 2-4 V (datasheet) and the 0.1 R source resistor needs another 0.3-0.6 V, so the\n'
                        'reachable current depends on which IRF530 you got.  Op-amp = ideal rail-to-rail proxy (best case for LMV358).', size=1)
    sh.text(240, 400, 'VSEN amplifier as drawn: R1 (feedback) goes to the\nNON-inverting input and R4 to the inverting input.\n'
                      'Positive feedback -> output latches to a rail.\nCorrect: swap the R1 and R4 connections.', size=1)
    sh.text(-640, 720, '.param Vdut=12 vth=3\n'
                       '.model IRF530_VTH VDMOS(Rg=3 Vto={vth} Rd=50m Rs=12m Rb=60m Kp=5 lambda=.01 Cgdmax=1n Cgdmin=.26n Cgs=.2n Cjo=.4n Is=52p ksubthres=.1 Vds=100)\n'
                       '.step param vth list 2 3 4   ; IRF530 VGS(th) min / mid / max\n'
                       '.dc Vctrl 0 4.096 8m\n'
                       '.meas DC I_FS FIND Id(Q1) AT 4.096\n'
                       '.meas DC I_target PARAM 4.096*12/80/0.1\n'
                       '.meas DC Vgate_FS FIND V(gate) AT 4.096\n'
                       '.meas DC VSEN_out FIND V(VSEN) AT 2\n'
                       '.meas DC VSEN_correct PARAM 0.1*12', directive=True)
    return sh


def deck05():
    """Thermal network: 1 V = 1 degC, 1 A = 1 W, 1 ohm = 1 K/W, 1 F = 1 J/K."""
    sh = Sheet(1600, 900)
    xs = [0, 192, 384, 576]
    for k, x in enumerate(xs):
        n = k + 1
        val = '{Ptot/N}' if n == 1 else '{if(N>=%d,Ptot/N,0)}' % n
        sh.sym('current', x, 400, 'R180', 'P%d' % n, val, [GND, 'J%d' % n]); sh.flag(x, 400, GND)
        sh.sym('res', x - 16, 224, 'R0', 'Rjc%d' % n, '{Rjc}', ['CASE%d' % n, 'J%d' % n])
        sh.sym('res', x - 16, 144, 'R0', 'Rcs%d' % n, '{Rcs}', ['SINK', 'CASE%d' % n])
        sh.wire((x, 240), (x - 48, 240)); sh.flag(x - 48, 240, 'CASE%d' % n)
        sh.wire((x, 320), (x, 304)); sh.flag(x, 304, 'J%d' % n)
        sh.wire((x, 160), (x, 96))
        if k:
            sh.wire((xs[k - 1], 96), (x, 96))
        sh.text(x + 24, 360, 'FET %d' % n, size=1)
    sh.wire((576, 96), (800, 96), (896, 96)); sh.flag(704, 96, 'SINK')
    sh.sym('res', 784, 96, 'R0', 'Rsa', '{Rsa}', ['SINK', 'TAMB'])
    sh.sym('cap', 880, 96, 'R0', 'Csa', '{Csa}', ['SINK', 'TAMB'])
    sh.wire((800, 112), (800, 96))
    sh.sym('voltage', 800, 192, 'R0', 'Vamb', '{Ta}', ['TAMB', GND]); sh.flag(800, 288, GND)
    sh.wire((800, 192), (800, 208)); sh.wire((896, 160), (896, 208), (800, 208)); sh.flag(848, 208, 'TAMB')
    sh.text(-120, -160, 'THERMAL MODEL - 150 W into N MOSFETs on the scrap heatsink', size=3)
    sh.text(-120, -120, 'Electrical analogue: 1 V = 1 degC, 1 A = 1 W, 1 ohm = 1 K/W, 1 F = 1 J/K.  V(Jn) = junction temperature.\n'
                        'Per-FET current loops force equal current, and all drains see the same Vds, so power splits equally.\n'
                        'Rjc = 0.70 K/W (IRFP250N max).  Rcs = 0.5 K/W (TO-247 on a silicone/Kapton insulator + paste; 0.24 bare + grease).\n'
                        'Rsa: heatsink ~ 17 x 9 x 7 cm extruded audio-amp sink: ~0.9 K/W natural convection, ~0.25-0.35 K/W with a\n'
                        '80-92 mm fan.  ESTIMATE ONLY - measure it (README, "heatsink characterisation").  Csa = 500 J/K ~ 0.55 kg Al.', size=1)
    sh.text(-120, 480, '.param Ptot=150 N=4 Ta=30 Rjc=0.7 Rcs=0.5 Rsa=0.35 Csa=500\n'
                       '.step param N list 2 3 4\n'
                       '.step param Rsa list 0.25 0.35 0.5 0.9\n'
                       '.tran 0 3600 0 2 startup\n'
                       '.ic V(SINK)={Ta}\n'
                       '.meas TRAN Tj_1h FIND V(J1) AT 3600\n'
                       '.meas TRAN Tsink_1h FIND V(SINK) AT 3600\n'
                       '.meas TRAN Tcase_1h FIND V(CASE1) AT 3600\n'
                       '.meas TRAN t_sink_90pct_s WHEN V(SINK)=Ta+0.9*Ptot*Rsa', directive=True)
    sh.text(-120, 760, 'PASS: Tj <= 125 degC (50 degC margin to the 175 degC rating, which also keeps the derated DC SOA healthy).', size=2)
    return sh


def deck06():
    """Hardware CV mode added to the unchanged Rev C stage: error amp pulls V_SET down through a 2N7002."""
    ramp = 'PWL(0 0 5m 0 25m 4.096)'
    sh = system('DC LOAD Rev C - ANALOG STAGE - 06 HARDWARE CV MODE (current-source DUT)', ramp, '30',
                dut_current='PWL(0 {Isrc} 60m {Isrc} 60.01m {1.1*Isrc})')
    sh.flag(1312, -32, 'VSEN_OA')
    # pull-down on V_SET: the LOAD_CTRL setting stays in charge as the current ceiling
    sh.sym('nmos', -592, 80, 'R0', 'Mcv', 'M2N7002', ['VSET', 'QG', GND]); sh.flag(-544, 176, GND)
    sh.flag(-592, 160, 'QG')
    # error amp: In+ = CV_SET, In- = VSEN amp output through R1
    ox, oy = -432, 192
    sh.sym('OpAmps\\LT1013', ox, oy, 'R0', 'U7', 'LT1013', ['CVSET', 'CVM', '+12V', GND, 'CVO'])
    sh.wire((ox, oy + 32), (ox, oy + 16)); sh.flag(ox, oy + 16, '+12V')
    sh.wire((ox, oy + 96), (ox, oy + 112)); sh.flag(ox, oy + 112, GND)
    sh.sym('res', -480, 224, 'R90', 'Rcv1', '100k', ['CVM', 'VSEN_OA'])
    sh.flag(-576, 240, 'VSEN_OA')
    sh.wire((-496, 240), (-464, 240), (-464, 160))
    sh.sym('res', -368, 144, 'R90', 'Rcv2', '10k', ['CVX', 'CVM'])
    sh.sym('cap', -320, 144, 'R90', 'Ccv', '47n', ['CVO', 'CVX'])
    sh.wire((-320, 160), (-320, 256), (-400, 256))
    sh.sym('res', -224, 240, 'R90', 'Rcvg', '1k', ['QG', 'CVO'])
    sh.flag(-240, 256, 'QG')
    # CV_SET source (firmware PWM + RC on the real board): 12 V, stepping to 10 V at 100 ms
    sh.sym('voltage', -528, 256, 'R0', 'Vcv', 'PWL(0 {12*0.049+0.0854} 100m {12*0.049+0.0854} 100.1m {10*0.049+0.0854})', ['CVSET', GND])
    sh.flag(-528, 352, GND)
    sh.wire((-528, 272), (-464, 272)); sh.flag(-496, 272, 'CVSET')
    sh.text(-1256, -320, SYS_NOTE + '\nCV: V_DUT below CV_SET -> U7 output rises -> Mcv pulls V_SET down -> load sinks less. CV_SET = 0: U7 low, Mcv off, plain CC.', size=1)
    sh.text(-1256, 2400, '.param fet=1 Rs=0.1 Llead=1u\n'
                         '.step param Cx list 1p 47u\n'
                         '.step param Isrc list 0.1 1 8\n'
                         '.tran 0 150m 0 10u\n'
                         '.meas TRAN v_12V FIND V(DUT+) AT 59m\n'
                         '.meas TRAN vpp_12V PP V(DUT+) FROM 50m TO 59m\n'
                         '.meas TRAN vpk_Istep MAX V(DUT+) FROM 60m TO 99m\n'
                         '.meas TRAN v_after_Istep FIND V(DUT+) AT 99m\n'
                         '.meas TRAN v_10V FIND V(DUT+) AT 149m\n'
                         '.meas TRAN vpp_10V PP V(DUT+) FROM 140m TO 149m\n'
                         '.meas TRAN Iload FIND ' + ISUM + ' AT 149m\n'
                         '.model M2N7002 VDMOS(Rg=3 Vto=1.6 Rd=0.2 Rs=0.5 Kp=0.16 Cgdmax=30p Cgdmin=5p Cgs=20p Cjo=10p Is=1p ksubthres=.1)\n'
                         '.model DCL D(Is=1n N=0.1 Rs=1)\n'
                         '.include ../lib/fet_models.lib\n' + SWMODEL, directive=True)
    sh.text(-1256, 2160, 'TEST: current-source DUT (30 V compliance) with CV set to 12 V, LOAD_CTRL ramped 0 -> full scale over 20 ms.\n'
                         'At 60 ms the source steps +10 %, at 100 ms CV_SET steps to 10 V.\n'
                         'EXPECT: V(DUT+) settles to the CV setting with no sustained oscillation for 0.1 - 8 A, with and without 47 uF across the DUT.', size=2)
    return sh


DECKS = {'06_cv_mode': deck06, '00_baseline_rev_b': deck00, '05_thermal': deck05, '01_dc_transfer': deck01, '02_step_response': deck02, '03_loop_gain': deck03, '04_faults': deck04}

if __name__ == '__main__':
    want = sys.argv[1:] or list(DECKS)
    for name in want:
        sh = DECKS[name]()
        d = os.path.join(OUT, name)
        os.makedirs(os.path.join(d, 'results'), exist_ok=True)
        asc = os.path.join(d, name + '.asc')
        sh.write(asc)
        ltrun(asc, netlist=True)
        net = asc[:-4] + '.net'
        errs = sh.check(net)
        os.remove(net)
        sh.render(os.path.join(d, 'results', 'schematic_preview.png'), name)
        print(name, 'NETLIST OK' if not errs else '\n  '.join(['NETLIST ERRORS:'] + errs))
