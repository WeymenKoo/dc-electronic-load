"""Reproduces results/fig04_faults.png from 04_faults.raw.
Run 04_faults.asc in LTspice first (same folder), then:  python3 plot_04_faults.py   (needs numpy + matplotlib)
"""
import os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'common'))
from ltspice_raw import read_raw, FETS, COL

plt.rcParams.update({'font.size': 9, 'axes.grid': True, 'grid.alpha': 0.3, 'figure.dpi': 130})
st = read_raw(os.path.join(HERE, '04_faults.raw'))
OUT = os.path.join(HERE, 'results', 'fig04_faults.png')


def isum(s):
    return sum(s['i(rs%d)' % k] for k in range(1, 5))


# steps: fet 1..4
s = st[0]
t = s['time'] * 1e3
fig, ax = plt.subplots(3, 1, figsize=(9, 6.5), sharex=True)
ax[0].plot(t, s['v(dut+)'], label='V(DUT+)'); ax[0].plot(t, s['v(drain)'], lw=0.8, label='V(DRAIN)')
ax[0].set_ylabel('V'); ax[0].legend(fontsize=8); ax[0].set_ylim(-2, 30)
for k in range(4):
    ax[1].plot(st[k]['time'] * 1e3, isum(st[k]), color=COL[k], label=FETS[k], lw=1)
ax[1].axhline(8.09, color='k', ls=':', lw=0.8); ax[1].set_ylabel('I total (A)'); ax[1].legend(fontsize=7)
ax[2].plot(t, s['v(kill)'], label='KILL (dropout detector)'); ax[2].plot(t, s['v(otp)'], label='OTP')
ax[2].plot(t, s['v(g1)'], label='gate CH1', lw=0.8); ax[2].set_ylabel('V'); ax[2].legend(fontsize=8)
ax[2].set_xlabel('time (ms)')
for a in ax:
    for x in (0.2, 1.0, 1.5, 2.5):
        a.axvline(x, color='grey', lw=0.6, ls='--')
for x, lab in ((0.2, 'hot-plug'), (1.0, 'collapse'), (1.5, 'recover'), (2.5, 'OTP')):
    ax[0].text(x + 0.02, 26, lab, fontsize=7)
ax[0].set_title('Fig 04 (Rev E, TLV9154) - faults at 8 A: planar FETs no overshoot, IXTH proxy peaks at 13.2 A')
fig.tight_layout(); fig.savefig(OUT); print('wrote', OUT)
