"""Reproduces results/fig03_loop_gain.png from 03_loop_gain.raw.
Run 03_loop_gain.asc in LTspice first (same folder), then:  python3 plot_03_loop_gain.py   (needs numpy + matplotlib)
"""
import os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'common'))
from ltspice_raw import read_raw, FETS, COL

plt.rcParams.update({'font.size': 9, 'axes.grid': True, 'grid.alpha': 0.3, 'figure.dpi': 130})
st = read_raw(os.path.join(HERE, '03_loop_gain.raw'))
OUT = os.path.join(HERE, 'results', 'fig03_loop_gain.png')


def isum(s):
    return sum(s['i(rs%d)' % k] for k in range(1, 5))


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
