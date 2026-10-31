"""Minimal LTspice binary .raw reader (real/complex, double/float, .step aware).

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
