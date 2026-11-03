"""Writes, for every sim folder in pkg2/: <deck>.plt (LTspice waveform-viewer layout) and plot_<deck>.py (matplotlib)."""
import os

import sys
SIMROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the simulation folder
ROOT, COMMON_REL, REV = SIMROOT, "'..', 'common'", 'C'
if sys.argv[1:2] == ['--rev-e']:                  # python3 write_plots.py --rev-e  -> ../rev_e/<deck>/ (TLV9154 decks 01-04, 06)
    ROOT, COMMON_REL, REV = os.path.join(SIMROOT, 'rev_e'), "'..', '..', 'common'", 'E'
V, A = 524290, 34603010            # LTspice trace codes: volts / amps; + n selects colour n
ISUM = 'I(Rs1)+I(Rs2)+I(Rs3)+I(Rs4)'


def pane(traces, x, y, unit='V', log=None, y1=None):
    """traces: list of (expr, unit); x/y: (prefix, decimals, min, tick, max)."""
    tr = ' '.join('{%d,0,"%s"}' % ((V if u == 'V' else A) + i, e) for i, (e, u) in enumerate(traces))
    L = ['   {', '      traces: %d %s' % (len(traces), tr),
         "      X: ('%s',%d,%g,%g,%g)" % x,
         "      Y[0]: ('%s',%d,%g,%g,%g)" % y]
    if log:                                         # AC: magnitude (dB) + phase
        L += ["      Y[1]: ('%s',%d,%g,%g,%g)" % y1, '      Log: 1 2 0', '      GridStyle: 1',
              '      PltMag: 1', '      PltPhi: 1 0', '   }']
    else:
        L += ["      Y[1]: ('_',0,1e+308,0,-1e+308)",
              "      %s: ('%s',0,0,%d,%g,%g,%g)" % ('Volts' if unit == 'V' else 'Amps', y[0], y[1], y[2], y[3], y[4]),
              '      Log: 0 0 0', '      GridStyle: 1', '   }']
    return '\n'.join(L)


def plt_file(kind, panes):
    body = ',\n'.join(panes)
    return '[%s]\n{\n   Npanes: %d\n   Active Pane: 1\n%s\n}\n' % (kind, len(panes), body)


PLT = {
    '00_baseline_rev_b': plt_file('DC transfer characteristic', [
        pane([('Id(Q1)', 'A')], (' ', 1, 0, 0.4, 4.096), (' ', 0, 0, 1, 7), 'A'),
        pane([('V(gate)', 'V'), ('V(VSEN)', 'V')], (' ', 1, 0, 0.4, 4.096), (' ', 1, 0, 0.5, 5))]),
    '01_dc_transfer': plt_file('DC transfer characteristic', [
        pane([('Id(M1)+Id(M2)+Id(M3)+Id(M4)', 'A'), ('Id(M1)', 'A')], (' ', 1, 0, 0.4, 4.096), (' ', 0, 0, 1, 11), 'A'),
        pane([('V(ISEN_ADC)', 'V'), ('V(VSEN_ADC)', 'V')], (' ', 1, 0, 0.4, 4.096), (' ', 1, 0, 0.5, 3.5))]),
    '02_step_response': plt_file('Transient Analysis', [
        pane([(ISUM, 'A')], ('m', 1, 0, 0.0001, 0.0013), (' ', 0, 0, 1, 10), 'A'),
        pane([('V(G1)', 'V'), ('V(G4)', 'V')], ('m', 1, 0, 0.0001, 0.0013), (' ', 0, 0, 1, 8)),
        pane([('V(LOAD_CTRL)', 'V'), ('V(VSET)', 'V')], ('m', 1, 0, 0.0001, 0.0013), (' ', 1, 0, 0.5, 4))]),
    '03_loop_gain': plt_file('AC Analysis', [
        pane([('-V(src)/V(inj)', 'V')], ('K', 0, 10, 0, 1e7), (' ', 0, 0.001, 20, 1e4), log=True, y1=(' ', 0, -270, 30, 0))]),
    '04_faults': plt_file('Transient Analysis', [
        pane([('V(DUT+)', 'V'), ('V(DRAIN)', 'V')], ('m', 1, 0, 0.0005, 0.0035), (' ', 0, -2, 4, 30)),
        pane([(ISUM, 'A')], ('m', 1, 0, 0.0005, 0.0035), (' ', 0, -3, 1, 10), 'A'),
        pane([('V(KILL)', 'V'), ('V(OTP)', 'V'), ('V(G1)', 'V')], ('m', 1, 0, 0.0005, 0.0035), (' ', 0, 0, 1, 6))]),
    '05_thermal': plt_file('Transient Analysis', [
        pane([('V(J1)', 'V'), ('V(SINK)', 'V')], (' ', 0, 0, 600, 3600), (' ', 0, 20, 25, 270))]),
}

COMMON = r'''"""Minimal LTspice binary .raw reader (real/complex, double/float, .step aware).

steps = read_raw('deck.raw')  ->  list with one dict per .step run; keys are lower-case
trace names exactly as LTspice writes them, e.g. 'time', 'v(isen_adc)', 'i(rs1)', 'id(m1)'.
"""
import numpy as np


def read_raw(path):
    b = open(path, 'rb').read()
    key = 'Binary:\n'.encode('utf-16-le')
    i = b.find(key)
    if i < 0:
        raise ValueError('not a binary LTspice .raw file: %s' % path)
    hdr, data = b[:i].decode('utf-16-le'), b[i + len(key):]
    names, h, invars = [], {}, False
    for ln in hdr.splitlines():
        if invars:
            p = ln.split()
            if len(p) >= 3:
                names.append(p[1].lower())
                continue
        if ln.startswith('Variables:'):
            invars = True
            continue
        if ':' in ln:
            k, v = ln.split(':', 1)
            h[k.strip()] = v.strip()
    nv, npnt, flags = int(h['No. Variables']), int(h['No. Points']), h.get('Flags', '')
    if 'complex' in flags:
        a = np.frombuffer(data, np.complex128, nv * npnt).reshape(npnt, nv)
        x = a[:, 0].real
    elif 'double' in flags:
        a = np.frombuffer(data, np.float64, nv * npnt).reshape(npnt, nv)
        x = a[:, 0]
    else:                                   # .tran: time is double, the rest float32
        dt = np.dtype([('t', '<f8')] + [('v%d' % k, '<f4') for k in range(1, nv)])
        r = np.frombuffer(data, dt, npnt)
        a = np.column_stack([np.abs(r['t'])] + [r['v%d' % k].astype(float) for k in range(1, nv)])
        x = a[:, 0]
    cuts = [0] + [k for k in range(1, len(x)) if x[k] < x[k - 1]] + [len(x)]   # sweep restarts = new step
    return [{n: a[s:e, j] for j, n in enumerate(names)} for s, e in zip(cuts, cuts[1:]) if e > s]


FETS = ['IRFP250N', 'IRFP240', 'IRF530', 'IXTH88N30P (big-die proxy)']
COL = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
'''

HEAD = r'''"""Reproduces results/%(fig)s from %(deck)s.raw.
Run %(deck)s.asc in LTspice first (same folder), then:  python3 plot_%(deck)s.py   (needs numpy + matplotlib)
"""
import os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, %(common)s))
from ltspice_raw import read_raw, FETS, COL

plt.rcParams.update({'font.size': 9, 'axes.grid': True, 'grid.alpha': 0.3, 'figure.dpi': 130})
st = read_raw(os.path.join(HERE, '%(deck)s.raw'))
OUT = os.path.join(HERE, 'results', '%(fig)s')


def isum(s):
    return sum(s['i(rs%%d)' %% k] for k in range(1, 5))

'''

BODY = {
'00_baseline_rev_b': ('fig00_baseline_rev_b.png', r'''
# steps: VGS(th) = 2, 3, 4 V
fig, ax = plt.subplots(figsize=(6.5, 3.6))
for s, vth, c in zip(st, (2, 3, 4), COL):
    ax.plot(s['v(load_ctrl)'], s['id(q1)'], color=c, label='IRF530, VGS(th) = %d V' % vth)
v = st[0]['v(load_ctrl)']
ax.plot(v, v * 12 / 80 / 0.1, 'k--', lw=1, label='what the design intends')
ax.set_xlabel('LOAD_CTRL (V)'); ax.set_ylabel('current per channel (A)')
ax.set_title('Fig 00 - Rev B as built: LMV358 on 4.096 V caps the gate at 4.1 V')
ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(OUT); print('wrote', OUT)
'''),
'01_dc_transfer': ('fig01_dc_transfer.png', r'''
# steps: DUT = 1, 2, 12, 48 V
fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
for s, vd, c in zip(st, (1, 2, 12, 48), COL):
    x = s['v(load_ctrl)']
    ax[0].plot(x, sum(s['id(m%d)' % k] for k in range(1, 5)), color=c, label='DUT = %g V' % vd)
    ax[1].plot(x, s['v(isen_adc)'], color=c)
ax[0].set_xlabel('LOAD_CTRL (V)'); ax[0].set_ylabel('I total (A)'); ax[0].legend(fontsize=8)
ax[0].set_title('Fig 01a - 2.50 A/V, 4 equal channels')
ax[1].set_xlabel('LOAD_CTRL (V)'); ax[1].set_ylabel('V(ISEN_ADC) (V)')
ax[1].axhline(3.3, color='k', ls=':', lw=1); ax[1].text(0.1, 3.2, 'ADC full scale 3.3 V', fontsize=7, va='top')
ax[1].set_title('Fig 01b - ISEN: 0.30 V/A + 0.12 V offset')
fig.tight_layout(); fig.savefig(OUT); print('wrote', OUT)
'''),
'02_step_response': ('fig02_step_response.png', r'''
# steps: fet 1..4 (fastest) x Llead 1u, 10u  ->  index k = Llead 1u, k+4 = Llead 10u
fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
for k in range(4):
    s, s10 = st[k], st[k + 4]
    ax[0].plot(s['time'] * 1e6 - 100, isum(s), color=COL[k], label=FETS[k])
    ax[0].plot(s10['time'] * 1e6 - 100, isum(s10), color=COL[k], ls='--', lw=0.8)
    ax[1].plot(s['time'] * 1e6 - 700, isum(s), color=COL[k])
ax[0].set_xlim(-10, 120); ax[0].set_xlabel('time after step (us)'); ax[0].set_ylabel('I total (A)')
ax[0].set_title('Fig 02a - 1 A -> 9 A (solid 1 uH, dashed 10 uH leads)'); ax[0].legend(fontsize=7)
ax[1].set_xlim(-10, 150); ax[1].set_ylim(0.8, 2.1); ax[1].set_xlabel('time after step (us)')
ax[1].set_title('Fig 02b - small step 1 A -> 2 A')
fig.tight_layout(); fig.savefig(OUT); print('wrote', OUT)
'''),
'03_loop_gain': ('fig03_loop_gain.png', r'''
# steps: fet (fastest) x Ich (0.025, 0.25, 2.5) x Llead (1u, 10u)  ->  index = fet + 4*ich + 12*llead
fig, ax = plt.subplots(2, 1, figsize=(7, 6), sharex=True)
for k in range(4):
    for idx, ls, lab in ((k + 8 + 12, '-', '2.5 A, 10 uH'), (k, ':', '25 mA, 1 uH')):
        s = st[idx]
        f = s['frequency'].real
        T = -s['v(src)'] / s['v(inj)']                       # loop gain
        ax[0].semilogx(f, 20 * np.log10(np.abs(T)), color=COL[k], ls=ls, label='%s, %s' % (FETS[k].split()[0], lab))
        ax[1].semilogx(f, np.unwrap(np.angle(T)) * 180 / np.pi, color=COL[k], ls=ls)
ax[0].axhline(0, color='k', lw=0.8); ax[1].axhline(-180, color='k', lw=0.8)
ax[0].set_ylabel('|T| (dB)'); ax[0].set_ylim(-60, 80); ax[0].legend(fontsize=6, ncol=2)
ax[1].set_ylabel('phase T (deg)'); ax[1].set_xlabel('frequency (Hz)'); ax[1].set_ylim(-270, 0)
ax[0].set_title('Fig 03 - loop gain per channel (Rf 3.3k, Cc 1n, Rg 47R): PM >= 80 deg, GM >= 13 dB')
fig.tight_layout(); fig.savefig(OUT); print('wrote', OUT)
'''),
'04_faults': ('fig04_faults.png', r'''
# steps: fet 1..4
s = st[0]
t = s['time'] * 1e3
fig, ax = plt.subplots(3, 1, figsize=(9, 6.5), sharex=True)
ax[0].plot(t, s['v(dut+)'], label='V(DUT+)'); ax[0].plot(t, s['v(drain)'], lw=0.8, label='V(DRAIN)')
ax[0].set_ylabel('V'); ax[0].legend(fontsize=8); ax[0].set_ylim(-2, 30)
for k in range(4):
    ax[1].plot(st[k]['time'] * 1e3, isum(st[k]), color=COL[k], label=FETS[k], lw=1)
ax[1].axhline(8.12, color='k', ls=':', lw=0.8); ax[1].set_ylabel('I total (A)'); ax[1].legend(fontsize=7)
ax[2].plot(t, s['v(kill)'], label='KILL (dropout detector)'); ax[2].plot(t, s['v(otp)'], label='OTP')
ax[2].plot(t, s['v(g1)'], label='gate CH1', lw=0.8); ax[2].set_ylabel('V'); ax[2].legend(fontsize=8)
ax[2].set_xlabel('time (ms)')
for a in ax:
    for x in (0.2, 1.0, 1.5, 2.5):
        a.axvline(x, color='grey', lw=0.6, ls='--')
for x, lab in ((0.2, 'hot-plug'), (1.0, 'collapse'), (1.5, 'recover'), (2.5, 'OTP')):
    ax[0].text(x + 0.02, 26, lab, fontsize=7)
ax[0].set_title('Fig 04 - faults at 8 A set point: no current overshoot on hot-plug or recovery')
fig.tight_layout(); fig.savefig(OUT); print('wrote', OUT)
'''),
'05_thermal': ('fig05_thermal.png', r'''
# steps: N = 2, 3, 4 (fastest) x Rsa = 0.25, 0.35, 0.5, 0.9 K/W   (1 V = 1 degC)
fig, ax = plt.subplots(figsize=(7, 4))
for j, rsa in enumerate((0.25, 0.35, 0.5, 0.9)):
    if rsa not in (0.35, 0.9):
        continue
    for i, n in enumerate((2, 3, 4)):
        s = st[j * 3 + i]
        ax.plot(s['time'] / 60, s['v(j1)'], color=COL[i], ls='-' if rsa == 0.35 else ':',
                label='%d FETs, Rsa %.2f K/W' % (n, rsa))
ax.axhline(125, color='k', lw=0.8, ls='--'); ax.text(1, 127, 'design limit 125 degC', fontsize=7)
ax.axhline(175, color='r', lw=0.8); ax.text(1, 177, 'IRFP250N absolute max 175 degC', fontsize=7, color='r')
ax.set_xlabel('minutes at 150 W'); ax.set_ylabel('junction temperature (degC)'); ax.set_ylim(20, 270)
ax.set_title('Fig 05 - 150 W, Ta 30 degC: 4 x TO-247 + fan is the configuration that works')
ax.legend(fontsize=7, ncol=2); fig.tight_layout(); fig.savefig(OUT); print('wrote', OUT)
'''),
}

# figure-title text that differs between revisions (Rev C text is in BODY; Rev E replacements are filled from its run)
TITLES = {'E': {
    '02_step_response': [("ax[0].set_title('Fig 02a - 1 A -> 9 A (solid 1 uH, dashed 10 uH leads)')",
                          "ax[0].set_title('Fig 02a (Rev E, TLV9154) - 1 A -> 9 A (solid 1 uH, dashed 10 uH); IXTH proxy overshoots at 1 uH')")],
    '03_loop_gain': [("(k, ':', '25 mA, 1 uH')", "(k, ':', '50 mA, 1 uH')"),
                     ("ax[0].set_title('Fig 03 - loop gain per channel (Rf 3.3k, Cc 1n, Rg 47R): PM >= 80 deg, GM >= 13 dB')",
                      "ax[0].set_title('Fig 03 (Rev E, TLV9154) - loop gain (Rf 3.3k, Cc 1n, Rg 47R): planar FETs PM >= 87 deg, GM >= 22 dB; IXTH proxy 80 deg / 9 dB')")],
    '04_faults': [("ax[1].axhline(8.12, color='k', ls=':', lw=0.8)", "ax[1].axhline(8.09, color='k', ls=':', lw=0.8)"),
                  ("ax[0].set_title('Fig 04 - faults at 8 A set point: no current overshoot on hot-plug or recovery')",
                   "ax[0].set_title('Fig 04 (Rev E, TLV9154) - faults at 8 A: planar FETs no overshoot, IXTH proxy peaks at 13.2 A')")],
    '01_dc_transfer': [("ax[0].set_title('Fig 01a - 2.50 A/V, 4 equal channels')", "ax[0].set_title('Fig 01a (Rev E, TLV9154) - 2.50 A/V, 4 equal channels, 10.14 A full scale')")],
}}

if __name__ == '__main__':
    if REV == 'C':
        open(os.path.join(ROOT, 'common', 'ltspice_raw.py'), 'w').write(COMMON)
    for deck, txt in PLT.items():
        if REV == 'E' and deck in ('00_baseline_rev_b', '05_thermal'):
            continue
        with open(os.path.join(ROOT, deck, deck + '.plt'), 'w', newline='\r\n') as f:
            f.write(txt)
        fig, body = BODY[deck]
        for a, b in TITLES.get(REV, {}).get(deck, ()):
            assert a in body, (deck, a)
            body = body.replace(a, b)
        open(os.path.join(ROOT, deck, 'plot_%s.py' % deck), 'w').write(HEAD % dict(deck=deck, fig=fig, common=COMMON_REL) + body)
    print('ok')
