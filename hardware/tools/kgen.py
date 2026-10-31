"""Minimal KiCad schematic writer: loads library symbols, places them, computes pin
positions, draws wires (auto-split + junctions), labels, text, rectangles.

Rev D additions (all optional, defaults reproduce the Rev C output byte for byte):
  Sch.face        outline font face for every text item (None = KiCad stroke font)
  Sch.fs_field    Reference / Value text size      Sch.fs_label  label text size
  wire(color=)    per-wire stroke colour (r, g, b)  label(size=, color=)
  rect(fill=)     filled block frames               polyline()    free-form dashed lines (isolation barrier)
"""
import copy, math, uuid as _uuid
from sexp import parse, dump, find, find1, Str

KLIB = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/'
_libcache = {}
_uid_n = [0]
_uid_ns = ['dcload-revc-%d']


def uid():
    # deterministic UUIDs so regenerating gives a stable diff
    _uid_n[0] += 1
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, _uid_ns[0] % _uid_n[0]))


def set_uid_namespace(fmt):
    _uid_ns[0] = fmt


def _lib(path):
    if path not in _libcache:
        _libcache[path] = parse(open(path).read())[0]
    return _libcache[path]


def _raw(path, name):
    for s in find(_lib(path), 'symbol'):
        if s[1] == name:
            return s
    raise KeyError(name)


def flatten(path, name, newname=None):
    """Return a self-contained symbol (extends resolved) named newname."""
    s = copy.deepcopy(_raw(path, name))
    e = find1(s, 'extends')
    newname = newname or name
    if e:
        base = flatten(path, e[1])
        props = {p[1]: p for p in find(s, 'property')}
        out = [x for x in base if not (isinstance(x, list) and x[0] == 'property')]
        bprops = find(base, 'property')
        merged = []
        for p in bprops:
            merged.append(props.pop(p[1], p))
        merged += list(props.values())
        # keep child's own non-property, non-extends attributes over base ones
        out = [out[0], Str(newname)] + [x for x in out[2:] if not (isinstance(x, list) and x[0] == 'symbol')] \
            + merged + [x for x in out[2:] if isinstance(x, list) and x[0] == 'symbol']
        s = out
        oldbase = base[1]
    else:
        oldbase = name
    s[1] = Str(newname)
    for sub in find(s, 'symbol'):
        sub[1] = Str(str(sub[1]).replace(oldbase, newname.split(':')[-1], 1))
    return s


def set_prop(sym, key, val, hide=None):
    for p in find(sym, 'property'):
        if p[1] == key:
            p[2] = Str(val)
            return p
    p = [ 'property', Str(key), Str(val), ['at', 0, 0, 0],
          ['effects', ['font', ['size', 1.27, 1.27]], ['hide', 'yes']]]
    # insert after last property
    idx = max(i for i, x in enumerate(sym) if isinstance(x, list) and x[0] == 'property')
    sym.insert(idx + 1, p)
    return p


def sym_pins(sym):
    """{(unit, number): (x, y)} in library coordinates (Y up), plus pin length/angle."""
    pins = {}
    for sub in find(sym, 'symbol'):
        nm = str(sub[1])
        unit = int(nm.split('_')[-2])
        for p in find(sub, 'pin'):
            at = find1(p, 'at')
            num = str(find1(p, 'number')[1])
            pins[(unit, num)] = (float(at[1]), float(at[2]))
    return pins


def xform(px, py, rot, mirror):
    """library (Y up) -> schematic offset (Y down). KiCad rotates first, then mirrors."""
    x, y = px, -py
    a = math.radians(rot)
    c, s = round(math.cos(a)), round(math.sin(a))
    # positive rot = counter-clockwise on screen (screen Y is down)
    x, y = x * c + y * s, -x * s + y * c
    if mirror == 'x':
        y = -y
    elif mirror == 'y':
        x = -x
    return x, y


def r2(v):
    return round(v * 100) / 100.0


class Part:
    def __init__(self, sch, lib_id, sym, ref, x, y, rot, mirror, unit):
        self.sch, self.lib_id, self.sym = sch, lib_id, sym
        self.ref, self.x, self.y, self.rot, self.mirror, self.unit = ref, x, y, rot, mirror, unit
        self.pins = sym_pins(sym)
        self.fields = {}

    def pin(self, num):
        key = (self.unit, str(num))
        if key not in self.pins:
            key = (0, str(num))
        px, py = self.pins[key]
        dx, dy = xform(px, py, self.rot, self.mirror)
        return (r2(self.x + dx), r2(self.y + dy))

    def unit_pins(self):
        return [n for (u, n) in self.pins if u in (self.unit, 0)]


class Sch:
    def __init__(self, project, paper='A2'):
        self.project, self.paper = project, paper
        self.root = uid()
        self.libsyms = {}
        self.parts, self.wires, self.labels, self.texts, self.ncs = [], [], [], [], []
        self.rects, self.extra_junctions, self.polylines = [], [], []
        self.pwr_n = 0
        self.title = {}
        self.sheets = []               # child sheet symbols (root only)
        self.instances = None          # [(path, {'n': 1}), ...] when this file is used as a sub-sheet
        self.face = None               # outline font face, e.g. 'Arial'
        self.fs_field = 1.27           # Reference / Value size
        self.fs_label = 1.27           # label / hierarchical / global label size
        self.fs_pin = 1.27             # sheet-pin size
        self.grid = None               # e.g. 1.27: snap every connection point to the grid

    def g(self, v):
        return r2(round(v / self.grid) * self.grid) if self.grid else v

    # ---------- fonts ----------
    def F(self, s=None, bold=False, italic=False, color=None):
        f = ['font']
        if self.face:
            f.append(['face', Str(self.face)])
        f.append(['size', s or 1.27, s or 1.27])
        if bold:
            f.append(['bold', 'yes'])
        if italic:
            f.append(['italic', 'yes'])
        if color:
            f.append(['color', color[0], color[1], color[2], 1])
        return f

    # ---------- symbols ----------
    def libsym(self, lib_id, path, name, overrides=None, newname=None):
        if lib_id not in self.libsyms:
            s = flatten(path, name, newname or name)
            s[1] = Str(lib_id)
            for k, v in (overrides or {}).items():
                set_prop(s, k, v)
            self.libsyms[lib_id] = s
        return self.libsyms[lib_id]

    def add(self, lib_id, ref, value, x, y, rot=0, mirror=None, unit=1, fields=None,
            fpos=None, hide_ref=False, hide_value=False, in_bom=True, on_board=True, dnp=False):
        sym = self.libsyms[lib_id]
        x, y = self.g(x), self.g(y)
        p = Part(self, lib_id, sym, ref, x, y, rot, mirror, unit)
        p.value, p.fields_in = value, fields or {}
        p.fpos = fpos or {}
        p.hide_ref, p.hide_value = hide_ref, hide_value
        p.in_bom, p.on_board, p.dnp = in_bom, on_board, dnp
        self.parts.append(p)
        return p

    def power(self, lib_id, x, y, rot=0, show=True):
        self.pwr_n += 1
        sym = self.libsyms[lib_id]
        ref = ('#FLG{n}%02d' if 'PWR_FLAG' in lib_id else '#PWR{n}%03d') % self.pwr_n
        val = str([q for q in find(sym, 'property') if q[1] == 'Value'][0][2])
        p = self.add(lib_id, ref, val, x, y, rot=rot, hide_ref=True, hide_value=not show,
                     in_bom=False, on_board=True)
        p.is_power = True
        return p

    # ---------- wiring ----------
    def wire(self, *pts, width=0, color=None):
        pts = [(self.g(a), self.g(b)) for a, b in pts]
        for a, b in zip(pts, pts[1:]):
            if a != b:
                assert a[0] == b[0] or a[1] == b[1], ('non-orthogonal wire', a, b)
                self.wires.append([a, b, width, color])

    def label(self, name, x, y, angle=0, kind='label', shape='passive', size=None, color=None):
        self.labels.append((kind, name, self.g(x), self.g(y), angle, shape, size, color))

    def nc(self, x, y):
        self.ncs.append((self.g(x), self.g(y)))

    def text(self, s, x, y, size=1.27, bold=False, italic=False, justify='left bottom', angle=0, color=None):
        self.texts.append((s, x, y, size, bold, italic, justify, angle, color))

    def rect(self, x1, y1, x2, y2, dash=True, width=0.254, color=None, fill=None):
        self.rects.append((x1, y1, x2, y2, dash, width, color, fill))

    def polyline(self, pts, width=0.5, dash=True, color=None):
        self.polylines.append((pts, width, dash, color))

    # ---------- output ----------
    def _connection_points(self):
        pts = []
        for p in self.parts:
            for n in p.unit_pins():
                pts.append(p.pin(n))
        for l in self.labels:
            pts.append((l[2], l[3]))
        return pts

    def finalize_wires(self):
        """Split wires at every pin/label/wire endpoint lying on their interior, then
        compute junctions where >= 3 connection items meet."""
        cps = set(self._connection_points())
        for w in self.wires:
            cps.add(w[0]); cps.add(w[1])
        out = []
        for a, b, wd, col in self.wires:
            inner = []
            for c in cps:
                if c in (a, b):
                    continue
                if a[0] == b[0] == c[0] and min(a[1], b[1]) < c[1] < max(a[1], b[1]):
                    inner.append(c)
                elif a[1] == b[1] == c[1] and min(a[0], b[0]) < c[0] < max(a[0], b[0]):
                    inner.append(c)
            seq = sorted([a, b] + inner, key=lambda c: (c[0] - a[0]) ** 2 + (c[1] - a[1]) ** 2)
            for u, v in zip(seq, seq[1:]):
                out.append([u, v, wd, col])
        # dedupe
        seen, ws = set(), []
        for u, v, wd, col in out:
            k = tuple(sorted([u, v]))
            if k not in seen:
                seen.add(k); ws.append([u, v, wd, col])
        self.wires = ws
        cnt = {}
        for u, v, _, _ in ws:
            cnt[u] = cnt.get(u, 0) + 1
            cnt[v] = cnt.get(v, 0) + 1
        pinpts = {}
        for p in self.parts:
            for n in p.unit_pins():
                q = p.pin(n)
                pinpts[q] = pinpts.get(q, 0) + 1
        self.junctions = sorted(q for q, c in cnt.items() if c + pinpts.get(q, 0) >= 3)

    def render(self):
        self.finalize_wires()
        F = self.F
        out = ['kicad_sch', ['version', 20260306], ['generator', Str('eeschema')],
               ['generator_version', Str('10.0')], ['uuid', Str(self.root)], ['paper', Str(self.paper)]]
        tb = ['title_block']
        for k in ('title', 'date', 'rev', 'company'):
            if k in self.title:
                tb.append([k, Str(self.title[k])])
        for i, c in enumerate(self.title.get('comments', []), 1):
            tb.append(['comment', i, Str(c)])
        out.append(tb)
        out.append(['lib_symbols'] + list(self.libsyms.values()))
        for j in self.junctions:
            out.append(['junction', ['at', j[0], j[1]], ['diameter', 0], ['color', 0, 0, 0, 0],
                        ['uuid', Str(uid())]])
        for x, y in self.ncs:
            out.append(['no_connect', ['at', x, y], ['uuid', Str(uid())]])
        for a, b, wd, col in self.wires:
            st = ['stroke', ['width', wd], ['type', 'default']]
            if col:
                st.append(['color', col[0], col[1], col[2], 1])
            out.append(['wire', ['pts', ['xy', a[0], a[1]], ['xy', b[0], b[1]]], st, ['uuid', Str(uid())]])
        for pts, wd, dash, col in self.polylines:
            st = ['stroke', ['width', wd], ['type', 'dash' if dash else 'solid']]
            if col:
                st.append(['color', col[0], col[1], col[2], 1])
            out.append(['polyline', ['pts'] + [['xy', r2(x), r2(y)] for x, y in pts], st, ['uuid', Str(uid())]])
        for x1, y1, x2, y2, dash, wd, col, fill in self.rects:
            st = ['stroke', ['width', wd], ['type', 'dash' if dash else 'solid']]
            if col:
                st.append(['color'] + list(col))
            fl = ['fill', ['type', 'color'], ['color', fill[0], fill[1], fill[2], fill[3]]] if fill else ['fill', ['type', 'none']]
            out.append(['rectangle', ['start', x1, y1], ['end', x2, y2], st, fl, ['uuid', Str(uid())]])
        for s, x, y, size, bold, italic, just, ang, col in self.texts:
            out.append(['text', Str(s), ['exclude_from_sim', 'no'], ['at', x, y, ang],
                        ['effects', F(size, bold, italic, col), ['justify'] + just.split()], ['uuid', Str(uid())]])
        for kind, name, x, y, ang, shape, size, col in self.labels:
            fs = size or self.fs_label
            if kind == 'label':
                just = {0: 'left bottom', 180: 'right bottom', 90: 'left bottom', 270: 'right bottom'}[ang]
                out.append(['label', Str(name), ['at', x, y, ang],
                            ['effects', F(fs, color=col), ['justify'] + just.split()], ['uuid', Str(uid())]])
            elif kind == 'hier':
                just = {0: 'left', 180: 'right', 90: 'left', 270: 'right'}[ang]
                out.append(['hierarchical_label', Str(name), ['shape', shape], ['at', x, y, ang],
                            ['effects', F(fs, color=col), ['justify', just]], ['uuid', Str(uid())]])
            else:
                just = {0: 'left', 180: 'right', 90: 'left', 270: 'right'}[ang]
                out.append(['global_label', Str(name), ['shape', shape], ['at', x, y, ang],
                            ['effects', F(fs, color=col), ['justify', just]], ['uuid', Str(uid())],
                            ['property', Str('Intersheetrefs'), Str('${INTERSHEET_REFS}'),
                             ['at', x, y, 0], ['effects', F(fs), ['hide', 'yes']]]])
        for p in self.parts:
            out.append(self._sym_inst(p))
        for sh in self.sheets:
            out.append(self._sheet(sh))
        if self.instances is None:     # root only
            out.append(['sheet_instances', ['path', Str('/'), ['page', Str('1')]]])
        out.append(['embedded_fonts', 'no'])
        return dump(out) + '\n'

    def add_sheet(self, name, fname, x, y, w, h, pins, page):
        """pins: [(name, shape, side 'L'/'R', y)]. Returns the sheet's uuid."""
        u = uid()
        x, y, w, h = self.g(x), self.g(y), self.g(w), self.g(h)
        pins = [(n, sh, side, self.g(py)) for n, sh, side, py in pins]
        self.sheets.append(dict(name=name, fname=fname, x=x, y=y, w=w, h=h, pins=pins, page=page, uuid=u))
        return u

    def _sheet(self, s):
        out = ['sheet', ['at', s['x'], s['y']], ['size', s['w'], s['h']], ['exclude_from_sim', 'no'],
               ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'],
               ['stroke', ['width', 0.1524], ['type', 'solid']], ['fill', ['color', 0, 0, 0, 0.0]],
               ['uuid', Str(s['uuid'])],
               ['property', Str('Sheetname'), Str(s['name']), ['at', s['x'], r2(s['y'] - 0.7), 0],
                ['effects', self.F(max(1.5, self.fs_label), bold=True), ['justify', 'left', 'bottom']]],
               ['property', Str('Sheetfile'), Str(s['fname']), ['at', s['x'], r2(s['y'] + s['h'] + 0.6), 0],
                ['effects', self.F(), ['justify', 'left', 'top']]]]
        for name, shape, side, py in s['pins']:
            px, ang, just = (s['x'], 180, 'left') if side == 'L' else (r2(s['x'] + s['w']), 0, 'right')
            out.append(['pin', Str(name), shape, ['at', px, py, ang], ['uuid', Str(uid())],
                        ['effects', self.F(self.fs_pin), ['justify', just]]])
        out.append(['instances', ['project', Str(self.project),
                                  ['path', Str('/' + self.root), ['page', Str(str(s['page']))]]]])
        return out

    def _sym_inst(self, p):
        s = ['symbol', ['lib_id', Str(p.lib_id)], ['at', p.x, p.y, p.rot]]
        if p.mirror:
            s.append(['mirror', p.mirror])
        s += [['unit', p.unit], ['exclude_from_sim', 'no'], ['in_bom', 'yes' if p.in_bom else 'no'],
              ['on_board', 'yes' if p.on_board else 'no'], ['dnp', 'yes' if p.dnp else 'no'],
              ['uuid', Str(uid())]]
        libprops = {str(q[1]): str(q[2]) for q in find(p.sym, 'property')}
        props = dict(libprops)
        props['Reference'] = p.ref.format(n='')
        props['Value'] = p.value
        props.update(p.fields_in)
        order = ['Reference', 'Value', 'Footprint', 'Datasheet', 'Description'] + \
                [k for k in props if k not in ('Reference', 'Value', 'Footprint', 'Datasheet', 'Description')]
        for k in order:
            if k not in props:
                continue
            if k in ('ki_keywords', 'ki_fp_filters', 'ki_locked'):
                continue
            pos = p.fpos.get(k)
            hidden = True
            if k == 'Reference':
                hidden = p.hide_ref
            elif k == 'Value':
                hidden = p.hide_value
            elif pos is not None:
                hidden = False
            eff = ['effects', self.F(self.fs_field if k in ('Reference', 'Value') or pos is not None else None)]
            if pos is None:
                pos = (p.x, p.y, 'left')
            x, y = pos[0], pos[1]
            just = pos[2] if len(pos) > 2 else 'left'
            if just != 'center':
                eff.append(['justify', just])
            if hidden:
                eff.append(['hide', 'yes'])
            # field angle is absolute text orientation; KiCad stores it relative to the
            # symbol, so a 90/270 symbol needs 90 to read horizontally
            fang = 90 if p.rot in (90, 270) else 0
            s.append(['property', Str(k), Str(props[k]), ['at', r2(x), r2(y), fang], eff])
        for n in sorted(set(n for (u, n) in p.pins)):
            s.append(['pin', Str(n), ['uuid', Str(uid())]])
        insts = self.instances or [('/' + self.root, {'n': ''})]
        paths = []
        for path, var in insts:
            unit = p.unit_fn(var) if getattr(p, 'unit_fn', None) else p.unit
            paths.append(['path', Str(path), ['reference', Str(p.ref.format(**var))], ['unit', unit]])
        s.append(['instances', ['project', Str(self.project)] + paths])
        return s
