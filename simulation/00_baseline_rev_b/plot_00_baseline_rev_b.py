"""Reproduces results/fig00_baseline_rev_b.png from 00_baseline_rev_b.raw.
Run 00_baseline_rev_b.asc in LTspice first (same folder), then:  python3 plot_00_baseline_rev_b.py   (needs numpy + matplotlib)
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
st = read_raw(os.path.join(HERE, '00_baseline_rev_b.raw'))
OUT = os.path.join(HERE, 'results', 'fig00_baseline_rev_b.png')


def isum(s):
    return sum(s['i(rs%d)' % k] for k in range(1, 5))


# steps: VGS(th) = 2, 3, 4 V
fig, ax = plt.subplots(figsize=(6.5, 3.6))
for s, vth, c in zip(st, (2, 3, 4), COL):
    ax.plot(s['v(load_ctrl)'], s['id(q1)'], color=c, label='IRF530, VGS(th) = %d V' % vth)
v = st[0]['v(load_ctrl)']
ax.plot(v, v * 12 / 80 / 0.1, 'k--', lw=1, label='what the design intends')
ax.set_xlabel('LOAD_CTRL (V)'); ax.set_ylabel('current per channel (A)')
ax.set_title('Fig 00 - Rev B as built: LMV358 on 4.096 V caps the gate at 4.1 V')
ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(OUT); print('wrote', OUT)
