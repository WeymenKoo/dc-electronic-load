"""Tiny LTspice .asc writer with wire-level layout, T-junction splitting,
intended-netlist cross-check against LTspice's own netlister, and a PNG preview."""
import re, os, subprocess, collections

# pin positions (symbol coords) in SpiceOrder
PINS = {
    'res': [('A', 16, 16), ('B', 16, 96)],
    'cap': [('A', 16, 0), ('B', 16, 64)],
    'ind': [('A', 16, 16), ('B', 16, 96)],
    'voltage': [('+', 0, 16), ('-', 0, 96)],
    'current': [('+', 0, 0), ('-', 0, 80)],
    'nmos': [('D', 48, 0), ('G', 0, 80), ('S', 48, 96)],
    'schottky': [('+', 16, 0), ('-', 16, 64)],
    'diode': [('+', 16, 0), ('-', 16, 64)],
    'zener': [('+', 16, 0), ('-', 16, 64)],
    'sw': [('A', 0, 16), ('B', 0, 96), ('NC+', -48, 80), ('NC-', -48, 32)],
    'OpAmps\\LT1014': [('In+', -32, 80), ('In-', -32, 48), ('V+', 0, 32), ('V-', 0, 96), ('OUT', 32, 64)],
    'OpAmps\\LT1013': [('In+', -32, 80), ('In-', -32, 48), ('V+', 0, 32), ('V-', 0, 96), ('OUT', 32, 64)],
    'OpAmps\\opamp2': [('In+', -32, 80), ('In-', -32, 48), ('V+', 0, 32), ('V-', 0, 96), ('OUT', 32, 64)],
    'OpAmps\\UniversalOpAmp2': [('In+', -32, 16), ('In-', -32, -16), ('V+', 0, -32), ('V-', 0, 32), ('OUT', 32, 0)],
}
ROT = {'R0': lambda x, y: (x, y), 'R90': lambda x, y: (-y, x),
       'R180': lambda x, y: (-x, -y), 'R270': lambda x, y: (y, -x)}
# keep text horizontal on rotated 2-pin parts (what LTspice itself writes)
WIN = {('res', 'R90'): ['WINDOW 0 0 56 VBottom 2', 'WINDOW 3 32 56 VTop 2'],
       ('ind', 'R90'): ['WINDOW 0 0 56 VBottom 2', 'WINDOW 3 32 56 VTop 2'],
       ('cap', 'R90'): ['WINDOW 0 0 32 VBottom 2', 'WINDOW 3 32 32 VTop 2'],
       ('res', 'R270'): ['WINDOW 0 32 56 VTop 2', 'WINDOW 3 0 56 VBottom 2'],
       ('cap', 'R270'): ['WINDOW 0 32 32 VTop 2', 'WINDOW 3 0 32 VBottom 2'],
       ('schottky', 'R90'): ['WINDOW 0 0 32 VBottom 2', 'WINDOW 3 32 32 VTop 2'],
       ('schottky', 'R270'): ['WINDOW 0 32 32 VTop 2', 'WINDOW 3 0 32 VBottom 2'],
       ('diode', 'R270'): ['WINDOW 0 32 32 VTop 2', 'WINDOW 3 0 32 VBottom 2'],
       ('zener', 'R270'): ['WINDOW 0 32 32 VTop 2', 'WINDOW 3 0 32 VBottom 2']}


class Sheet:
    def __init__(self, w=3200, h=2400):
        self.w, self.h = w, h
        self.syms, self.wires, self.flags, self.texts, self.rects = [], [], [], [], []
        self.pinpos = {}       # (inst,pin) -> (x,y)
        self.intended = {}     # (inst,pin) -> netname

    def sym(self, kind, x, y, rot, name, value, nodes, value2=None, spiceline=None, windows=None):
        pins = {}
        for (pn, px, py), node in zip(PINS[kind], nodes):
            X, Y = ROT[rot](px, py)
            pins[pn] = (x + X, y + Y)
            self.pinpos[(name, pn)] = (x + X, y + Y)
            if node is not None:
                self.intended[(name, pn)] = node
        self.syms.append(dict(kind=kind, x=x, y=y, rot=rot, name=name, value=value, value2=value2,
                              spiceline=spiceline, windows=windows if windows is not None else WIN.get((kind, rot), [])))
        return pins

    def wire(self, *pts):
        for a, b in zip(pts, pts[1:]):
            if a[0] != b[0] and a[1] != b[1]:
                raise ValueError('non-orthogonal wire %s %s' % (a, b))
            if a != b:
                self.wires.append((tuple(a), tuple(b)))

    def flag(self, x, y, name):
        self.flags.append((x, y, name))

    def text(self, x, y, s, directive=False, size=2, align='Left'):
        self.texts.append((x, y, s, directive, size, align))

    def rect(self, x1, y1, x2, y2):
        self.rects.append((x1, y1, x2, y2))

    # --- split wires so every connection is an endpoint-to-endpoint join
    def _split(self):
        pts = set()
        for a, b in self.wires:
            pts.add(a); pts.add(b)
        pts |= set(self.pinpos.values())
        pts |= {(x, y) for x, y, _ in self.flags}
        out = []
        for a, b in self.wires:
            inner = [p for p in pts if p != a and p != b and _on(p, a, b)]
            seq = sorted([a, b] + inner, key=lambda p: (p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2)
            out += list(zip(seq, seq[1:]))
        self.wires = out

    def write(self, path):
        self._split()
        L = ['Version 4', 'SHEET 1 %d %d' % (self.w, self.h)]
        for a, b in self.wires:
            L.append('WIRE %d %d %d %d' % (a[0], a[1], b[0], b[1]))
        for x, y, n in self.flags:
            L.append('FLAG %d %d %s' % (x, y, n))
        for s in self.syms:
            L.append('SYMBOL %s %d %d %s' % (s['kind'], s['x'], s['y'], s['rot']))
            L += s['windows']
            L.append('SYMATTR InstName %s' % s['name'])
            if s['value'] is not None:
                L.append('SYMATTR Value %s' % s['value'])
            if s['value2']:
                L.append('SYMATTR Value2 %s' % s['value2'])
            if s['spiceline']:
                L.append('SYMATTR SpiceLine %s' % s['spiceline'])
        for x1, y1, x2, y2 in self.rects:
            L.append('RECTANGLE Normal %d %d %d %d 2' % (x1, y1, x2, y2))
        for x, y, s, d, size, al in self.texts:
            L.append('TEXT %d %d %s %d %s%s' % (x, y, al, size, '!' if d else ';', s.replace('\n', '\\n')))
        open(path, 'w', encoding='latin-1').write('\n'.join(L) + '\n')

    # --- connectivity check against LTspice netlist
    def check(self, netpath):
        txt = open(netpath, encoding='latin-1').read()
        ltnodes = {}
        for ln in txt.splitlines():
            p = ln.split()
            if not p or p[0][0] in '*.;+':
                continue
            ltnodes[p[0].upper()] = p[1:]
        errs = []
        groups = collections.defaultdict(set)
        rev = collections.defaultdict(set)
        for s in self.syms:
            pref = s['name']
            key = None
            for k in ltnodes:
                if k == pref.upper() or k.endswith('§' + pref.upper()):
                    key = k
            if key is None:
                errs.append('missing in netlist: ' + pref); continue
            for i, (pn, _, _) in enumerate(PINS[s['kind']]):
                want = self.intended.get((pref, pn))
                if want is None:
                    continue
                got = ltnodes[key][i]
                groups[want].add(got)
                rev[got].add(want)
        for w, g in groups.items():
            if len(g) > 1:
                errs.append('intended net %s split into LTspice nodes %s' % (w, sorted(g)))
        for g, w in rev.items():
            if len(w) > 1:
                errs.append('LTspice node %s merges intended nets %s' % (g, sorted(w)))
        return errs

    # --- quick preview render (approximate symbol graphics)
    def render(self, png, title=''):
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        xs = [p[0] for w in self.wires for p in w] + [p[0] for p in self.pinpos.values()] + [t[0] for t in self.texts]
        ys = [p[1] for w in self.wires for p in w] + [p[1] for p in self.pinpos.values()] + [t[1] for t in self.texts]
        x0, x1, y0, y1 = min(xs) - 120, max(xs) + 360, min(ys) - 120, max(ys) + 160
        fig = plt.figure(figsize=((x1 - x0) / 110, (y1 - y0) / 110))
        ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.axis('off')
        for a, b in self.wires:
            ax.plot([a[0], b[0]], [a[1], b[1]], color='#1f3fbf', lw=1.4)
        cnt = collections.Counter()
        for a, b in self.wires:
            cnt[a] += 1; cnt[b] += 1
        for (n, pn), p in self.pinpos.items():
            cnt[p] += 1
        for p, c in cnt.items():
            if c >= 3:
                ax.plot(*p, 'o', color='#1f3fbf', ms=4)
        for x, y, n in self.flags:
            if n == '0':
                ax.plot([x - 16, x + 16, x, x - 16], [y, y, y + 16, y], color='k', lw=1)
            else:
                ax.text(x, y - 6, n, fontsize=7, color='#a0522d', ha='center', va='bottom')
        for s in self.syms:
            pp = [self.pinpos[(s['name'], pn)] for pn, _, _ in PINS[s['kind']]]
            cx = sum(p[0] for p in pp) / len(pp); cy = sum(p[1] for p in pp) / len(pp)
            k = s['kind']
            if k in ('res', 'ind', 'cap', 'schottky', 'diode', 'zener'):
                (ax_, ay), (bx, by) = pp[0], pp[1]
                if ax_ == bx:
                    h = 8; ax.add_patch(plt.Rectangle((cx - h, min(ay, by) + 10), 2 * h, abs(by - ay) - 20, fill=False, color='k'))
                else:
                    h = 8; ax.add_patch(plt.Rectangle((min(ax_, bx) + 10, cy - h), abs(bx - ax_) - 20, 2 * h, fill=False, color='k'))
                tag = {'res': '', 'ind': 'L', 'cap': '||', 'schottky': '|>', 'diode': '|>', 'zener': 'Z'}[k]
                ax.text(cx + 14, cy, '%s %s\n%s' % (tag, s['name'], s['value'] or ''), fontsize=6, va='center')
            elif k in ('voltage', 'current'):
                ax.add_patch(plt.Circle((cx, cy), 28, fill=False, color='k'))
                ax.text(cx + 34, cy, '%s\n%s' % (s['name'], (s['value'] or '')[:40]), fontsize=6, va='center')
            elif k == 'nmos':
                ax.add_patch(plt.Rectangle((s['x'] + 16, s['y'] + 16), 32, 64, fill=False, color='k'))
                ax.text(s['x'] + 56, s['y'] + 48, '%s\n%s' % (s['name'], s['value']), fontsize=6, va='center')
            elif k == 'sw':
                ax.add_patch(plt.Rectangle((s['x'] - 40, s['y'] + 24), 48, 64, fill=False, color='k'))
                ax.text(s['x'] + 12, s['y'] + 56, s['name'], fontsize=6)
            else:
                inp = self.pinpos[(s['name'], 'In+')]; inm = self.pinpos[(s['name'], 'In-')]; o = self.pinpos[(s['name'], 'OUT')]
                top = min(inp[1], inm[1]) - 16; bot = max(inp[1], inm[1]) + 16
                ax.add_patch(plt.Polygon([(inp[0], top), (inp[0], bot), (o[0], o[1])], fill=False, color='k'))
                ax.text(inp[0] + 4, inp[1], '+', fontsize=7, va='center'); ax.text(inm[0] + 4, inm[1], '−', fontsize=7, va='center')
                ax.text(o[0] + 4, top - 4, '%s %s' % (s['name'], s['value']), fontsize=6)
            for pn, _, _ in PINS[k]:
                p = self.pinpos[(s['name'], pn)]
                ax.plot(*p, 's', color='#c00', ms=2)
        for x1_, y1_, x2_, y2_ in self.rects:
            ax.add_patch(plt.Rectangle((x1_, y1_), x2_ - x1_, y2_ - y1_, fill=False, ls='--', color='#888'))
        for x, y, s, d, size, al in self.texts:
            ax.text(x, y, s, fontsize=5.5 if size <= 1 else 6.5 if size == 2 else 9, va='top' if True else 'center',
                    color='#000080' if d else '#006400', family='monospace')
        if title:
            ax.text(x0 + 20, y0 + 10, title, fontsize=10, va='top')
        fig.savefig(png, dpi=110); plt.close(fig)


def _on(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    if x1 == x2 == x and min(y1, y2) < y < max(y1, y2):
        return True
    if y1 == y2 == y and min(x1, x2) < x < max(x1, x2):
        return True
    return False


def ltrun(path, netlist=False):
    here = os.path.dirname(os.path.abspath(__file__))
    args = [os.path.join(here, 'ltrun.sh')] + (['-netlist'] if netlist else []) + [path]
    subprocess.run(args, check=True)
