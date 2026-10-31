"""Reproduces results/fig02_step_response.png from 02_step_response.raw.
Run 02_step_response.asc in LTspice first (same folder), then:  python3 plot_02_step_response.py   (needs numpy + matplotlib)
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
st = read_raw(os.path.join(HERE, '02_step_response.raw'))
OUT = os.path.join(HERE, 'results', 'fig02_step_response.png')


def isum(s):
    return sum(s['i(rs%d)' % k] for k in range(1, 5))


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
