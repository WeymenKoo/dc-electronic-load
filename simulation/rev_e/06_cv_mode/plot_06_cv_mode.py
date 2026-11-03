"""Rebuilds results/fig06_cv_mode.png from 06_cv_mode.raw. Step order from the log: Isrc = 0.1, 1, 8 A,
each with Cx = 1p then 47u."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'common'))
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ltspice_raw import read_raw

LABELS = ['0.1 A, no C', '0.1 A, 47 uF', '1 A, no C', '1 A, 47 uF', '8 A, no C', '8 A, 47 uF']
fig, ax = plt.subplots(figsize=(9, 4.5))
for s, lab in zip(read_raw(os.path.join(HERE, '06_cv_mode.raw')), LABELS):
    ax.plot(s['time'][::40] * 1e3, s['v(dut+)'][::40], lw=1, label=lab)
ax.set(xlabel='time (ms)', ylabel='V(DUT+) (V)', title='Rev E (TLV9154): current-source DUT held by hardware CV: 12 V, +10 % source step at 60 ms, 10 V at 100 ms', ylim=(0, 32))
ax.grid(alpha=.3); ax.legend(ncol=3, fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(HERE, 'results', 'fig06_cv_mode.png'), dpi=130)
