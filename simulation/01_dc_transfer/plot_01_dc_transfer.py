"""Reproduces results/fig01_dc_transfer.png from 01_dc_transfer.raw.
Run 01_dc_transfer.asc in LTspice first (same folder), then:  python3 plot_01_dc_transfer.py   (needs numpy + matplotlib)
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
st = read_raw(os.path.join(HERE, '01_dc_transfer.raw'))
OUT = os.path.join(HERE, 'results', 'fig01_dc_transfer.png')


def isum(s):
    return sum(s['i(rs%d)' % k] for k in range(1, 5))


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
