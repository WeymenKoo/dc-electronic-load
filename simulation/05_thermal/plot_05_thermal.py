"""Reproduces results/fig05_thermal.png from 05_thermal.raw.
Run 05_thermal.asc in LTspice first (same folder), then:  python3 plot_05_thermal.py   (needs numpy + matplotlib)
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
st = read_raw(os.path.join(HERE, '05_thermal.raw'))
OUT = os.path.join(HERE, 'results', 'fig05_thermal.png')


def isum(s):
    return sum(s['i(rs%d)' % k] for k in range(1, 5))


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
