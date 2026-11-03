"""KiCad schematic writer with layout rules built in.

Places library symbols, computes pin positions, draws wires (auto-split + junctions), labels, notes, filled block
frames, free polylines, and then CHECKS the drawing:
  lint()   text never overlaps text, symbols or wires; symbols never overlap each other or foreign wires;
           no 4-way wire junctions (max 3 wires per node); wire crossings are listed (hop-overs are enabled in the project);
           every block frame is clear of the others; nothing within the sheet margin.
  blocks   begin_block()/end_block() fit a titled frame to the content with a fixed margin (content is centred in it).
  centre   centre_on_sheet() moves the whole drawing to the middle of the drawable area, on the grid.
Text widths are estimated for a monospace outline font (JetBrains Mono, 0.6 em advance)."""
import copy, math, uuid as _uuid
from sexp import parse, dump, find, find1, Str

KLIB = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/'
_libcache = {}
_uid_n = [0]
_uid_ns = ['dcload-%d']
CHAR_W = 0.82          # text width per character, in units of the text size (JetBrains Mono as KiCad renders it: measured 0.80)
LINE_H = 1.45          # line pitch of multi-line text, in units of the text size


def uid():
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
    p = ['property', Str(key), Str(val), ['at', 0, 0, 0], ['effects', ['font', ['size', 1.27, 1.27]], ['hide', 'yes']]]
    idx = max(i for i, x in enumerate(sym) if isinstance(x, list) and x[0] == 'property')
    sym.insert(idx + 1, p)
    return p


def set_pin_text_size(sym, size):
    for u in find(sym, 'symbol'):
        for p in find(u, 'pin'):
            for k in ('name', 'number'):
                e = find1(find1(p, k), 'effects')
                f = find1(e, 'font') if e else None
                if f:
                    sz = find1(f, 'size')
                    if sz:
                        sz[1] = sz[2] = size


def sym_pins(sym):
    pins = {}
    for sub in find(sym, 'symbol'):
        nm = str(sub[1])
        unit = int(nm.split('_')[-2])
        for p in find(sub, 'pin'):
            at = find1(p, 'at')
            num = str(find1(p, 'number')[1])
            pins[(unit, num)] = (float(at[1]), float(at[2]), float(at[3]), float(find1(p, 'length')[1]))
    return pins


def sym_body(sym, unit):
    """bbox of the drawn body (graphics + pins) of one unit in library coordinates (Y up)."""
    xs, ys = [], []
    for sub in find(sym, 'symbol'):
        u = int(str(sub[1]).split('_')[-2])
        if u not in (unit, 0):
            continue
        for it in sub:
            if not isinstance(it, list):
                continue
            k = it[0]
            if k in ('rectangle',):
                for key in ('start', 'end'):
                    a = find1(it, key); xs.append(float(a[1])); ys.append(float(a[2]))
            elif k == 'polyline':
                for xy in find(find1(it, 'pts'), 'xy'):
                    xs.append(float(xy[1])); ys.append(float(xy[2]))
            elif k == 'circle':
                c, r = find1(it, 'center'), float(find1(it, 'radius')[1])
                xs += [float(c[1]) - r, float(c[1]) + r]; ys += [float(c[2]) - r, float(c[2]) + r]
            elif k == 'arc':
                for key in ('start', 'mid', 'end'):
                    a = find1(it, key); xs.append(float(a[1])); ys.append(float(a[2]))
            elif k == 'pin':
                at = find1(it, 'at'); L = float(find1(it, 'length')[1]); ang = float(at[3])
                x, y = float(at[1]), float(at[2])
                xs += [x, x + L * round(math.cos(math.radians(ang)))]; ys += [y, y + L * round(math.sin(math.radians(ang)))]
    if not xs:
        return (0, 0, 0, 0)
    return (min(xs), min(ys), max(xs), max(ys))


def xform(px, py, rot, mirror):
    x, y = px, -py
    a = math.radians(rot)
    c, s = round(math.cos(a)), round(math.sin(a))
    x, y = x * c + y * s, -x * s + y * c
    if mirror == 'x':
        y = -y
    elif mirror == 'y':
        x = -x
    return x, y


def r2(v):
    return round(v * 100) / 100.0


def tw(s, size):
    return CHAR_W * size * max(len(s), 1)


def _box_text(s, x, y, size, just, angle=0):
    """bbox of a (possibly multi-line) text item"""
    lines = s.split('\n')
    w = max(tw(l, size) for l in lines)
    h = size * (1 + (len(lines) - 1) * LINE_H)
    hj, vj = (just.split() + ['bottom'])[:2] if ' ' in just else (just, 'bottom')
    if angle in (90, 270):
        # rotated: text runs along y
        if angle == 90:
            x1, x2 = (x - h, x) if hj == 'left' else (x, x + h)
            y1, y2 = y - w, y
        else:
            x1, x2 = x, x + h
            y1, y2 = y, y + w
        return (x1, y1, x2, y2)
    if hj == 'left':
        x1, x2 = x, x + w
    elif hj == 'right':
        x1, x2 = x - w, x
    else:
        x1, x2 = x - w / 2, x + w / 2
    if vj == 'bottom':
        y1, y2 = y - h, y
    elif vj == 'top':
        y1, y2 = y, y + h
    else:
        y1, y2 = y - h / 2, y + h / 2
    return (x1, y1, x2, y2)


def _overlap(a, b, tol=0.0):
    return a[0] + tol < b[2] and b[0] + tol < a[2] and a[1] + tol < b[3] and b[1] + tol < a[3]


def _seg_hits_box(p, q, box, tol=0.0):
    """does segment p-q pass through the interior of box (shrunk by tol)?"""
    x1, y1, x2, y2 = box[0] + tol, box[1] + tol, box[2] - tol, box[3] - tol
    if x1 >= x2 or y1 >= y2:
        return False
    if p[0] == q[0]:
        return x1 < p[0] < x2 and min(p[1], q[1]) < y2 and max(p[1], q[1]) > y1
    if p[1] == q[1]:
        return y1 < p[1] < y2 and min(p[0], q[0]) < x2 and max(p[0], q[0]) > x1
    return False


def _fmt(b):
    return '(%.1f,%.1f)-(%.1f,%.1f)' % tuple(b)


def _union(boxes):
    boxes = [b for b in boxes if b]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


class Part:
    def __init__(self, sch, lib_id, sym, ref, x, y, rot, mirror, unit):
        self.sch, self.lib_id, self.sym = sch, lib_id, sym
        self.ref, self.x, self.y, self.rot, self.mirror, self.unit = ref, x, y, rot, mirror, unit
        self.pins = sym_pins(sym)
        self.fields = {}
        self.is_power = False
        self.block = None

    def pin(self, num):
        key = (self.unit, str(num))
        if key not in self.pins:
            key = (0, str(num))
        px, py = self.pins[key][:2]
        dx, dy = xform(px, py, self.rot, self.mirror)
        return (r2(self.x + dx), r2(self.y + dy))

    def unit_pins(self):
        return [n for (u, n) in self.pins if u in (self.unit, 0)]

    def pin_points(self):
        return set(self.pin(n) for n in self.unit_pins())

    def body(self):
        x1, y1, x2, y2 = sym_body(self.sym, self.unit)
        pts = [xform(px, py, self.rot, self.mirror) for px in (x1, x2) for py in (y1, y2)]
        return (self.x + min(p[0] for p in pts), self.y + min(p[1] for p in pts), self.x + max(p[0] for p in pts), self.y + max(p[1] for p in pts))

    def field_boxes(self):
        out = []
        for k, pos in self.fpos.items():
            if k == 'Reference' and self.hide_ref or k == 'Value' and self.hide_value:
                continue
            txt = self.ref.format(n='1') if k == 'Reference' else (self.value if k == 'Value' else self.fields_in.get(k, ''))
            just = pos[2] if len(pos) > 2 else 'left'
            out.append((_box_text(txt, pos[0], pos[1], self.sch.fs_field, just + ' middle'), '%s.%s "%s"' % (self.ref, k, txt)))
        return out


class Sch:
    def __init__(self, project, paper='A3'):
        self.project, self.paper = project, paper
        self.root = uid()
        self.libsyms = {}
        self.parts, self.wires, self.labels, self.texts, self.ncs = [], [], [], [], []
        self.rects, self.polylines = [], []
        self.pwr_n = 0
        self.title = {}
        self.sheets = []
        self.instances = None
        self.face = None
        self.fs_field, self.fs_label, self.fs_pin, self.fs_block = 1.27, 1.27, 1.27, 2.5
        self.grid = None
        self.block_margin = 6.0
        self._blocks = []            # (title, start_counts, fill)
        self.blocks = []             # finished: (title, bbox)
        self.fixed_texts = 0         # leading texts that never move (sheet header)
        self.W, self.H = {'A4': (297, 210), 'A3': (420, 297), 'A2': (594, 420)}[paper]
        # drawable area: inside the frame, clear of the title block in the bottom-right corner
        self.area = (18, 30, self.W - 18, self.H - 42)
        self.title_block = (self.W - 122, self.H - 42)   # x, y where the title block starts

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
        p = self.add(lib_id, ref, val, x, y, rot=rot, hide_ref=True, hide_value=not show, in_bom=False, on_board=True)
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
        self.labels.append([kind, name, self.g(x), self.g(y), angle, shape, size, color])

    def nc(self, x, y):
        self.ncs.append((self.g(x), self.g(y)))

    def text(self, s, x, y, size=1.27, bold=False, italic=False, justify='left bottom', angle=0, color=None):
        self.texts.append([s, x, y, size, bold, italic, justify, angle, color])

    def rect(self, x1, y1, x2, y2, dash=True, width=0.254, color=None, fill=None):
        self.rects.append([x1, y1, x2, y2, dash, width, color, fill])

    def polyline(self, pts, width=0.5, dash=True, color=None):
        self.polylines.append([list(pts), width, dash, color])

    # ---------- blocks ----------
    def begin_block(self, title, fill=None):
        self._blocks.append((title, self._counts(), fill))

    def _counts(self):
        return dict(parts=len(self.parts), wires=len(self.wires), labels=len(self.labels), texts=len(self.texts),
                    ncs=len(self.ncs), polylines=len(self.polylines), sheets=len(self.sheets), rects=len(self.rects))

    def end_block(self, color=(120, 120, 120, 1)):
        title, c, fill = self._blocks.pop()
        boxes = self._item_boxes(c)
        if not boxes:
            return None
        m = self.block_margin
        x1, y1, x2, y2 = _union([b for b, _ in boxes])
        th = self.fs_block * 1.6
        x2 = max(x2, x1 - m + 2.0 + tw(title, self.fs_block) + 2.0)      # the frame is at least as wide as its title
        fr = (self.g(x1 - m) , self.g(y1 - m - th), self.g(x2 + m), self.g(y2 + m))
        self.rects.append([fr[0], fr[1], fr[2], fr[3], False, 0.25, color, fill])
        self.texts.append([title, fr[0] + 2.0, fr[1] + th - 0.4, self.fs_block, True, False, 'left bottom', 0, (0, 50, 120)])
        self.blocks.append((title, fr))
        for p in self.parts[c['parts']:]:
            p.block = title
        return fr

    # ---------- geometry of everything ----------
    def label_box(self, l):
        kind, name, x, y, ang, shape, size, col = l
        s = size or self.fs_label
        w = tw(name.replace('~{', '').replace('}', ''), s)
        if kind == 'hier' or kind == 'global':
            w += 1.4 * s; h = 0.9 * s
            if ang == 0:
                return (x, y - h, x + w, y + h)
            if ang == 180:
                return (x - w, y - h, x, y + h)
            if ang == 90:
                return (x - h, y - w, x + h, y)
            return (x - h, y, x + h, y + w)
        h = 1.25 * s
        if ang == 0:
            return (x, y - h, x + w, y)
        if ang == 180:
            return (x - w, y - h, x, y)
        if ang == 90:
            return (x - h, y - w, x, y)
        return (x, y, x + h, y + w)

    def text_box(self, t):
        s, x, y, size, bold, italic, just, ang, col = t
        return _box_text(s, x, y, size, just, ang)

    def sheet_box(self, sh):
        return (sh['x'], sh['y'] - self.fs_label * 1.6, sh['x'] + sh['w'], sh['y'] + sh['h'] + self.fs_label * 1.6)

    def _item_boxes(self, c=None):
        """[(box, desc)] of every drawn item added after counts c (all if None)"""
        c = c or dict(parts=0, wires=0, labels=0, texts=0, ncs=0, polylines=0, sheets=0, rects=0)
        out = []
        for p in self.parts[c['parts']:]:
            out.append((p.body(), 'symbol ' + p.ref.format(n='1')))
            out += p.field_boxes()
        for a, b, wd, col in self.wires[c['wires']:]:
            out.append(((min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])), 'wire'))
        for l in self.labels[c['labels']:]:
            out.append((self.label_box(l), 'label ' + l[1]))
        for t in self.texts[c['texts']:]:
            out.append((self.text_box(t), 'text "%s"' % t[0][:30]))
        for x, y in self.ncs[c['ncs']:]:
            out.append(((x - 0.6, y - 0.6, x + 0.6, y + 0.6), 'nc'))
        for pts, wd, dash, col in self.polylines[c['polylines']:]:
            out.append(((min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)), 'polyline'))
        for sh in self.sheets[c['sheets']:]:
            out.append((self.sheet_box(sh), 'sheet ' + sh['name']))
        for r in self.rects[c['rects']:]:
            out.append(((r[0], r[1], r[2], r[3]), 'frame'))
        return out

    def content_box(self):
        c = dict(parts=0, wires=0, labels=0, texts=self.fixed_texts, ncs=0, polylines=0, sheets=0, rects=0)
        boxes = self._item_boxes(c)
        return _union([b for b, _ in boxes]) if boxes else None

    def translate(self, dx, dy):
        dx, dy = self.g(dx), self.g(dy)
        for p in self.parts:
            p.x, p.y = r2(p.x + dx), r2(p.y + dy)
            p.fpos = {k: (r2(v[0] + dx), r2(v[1] + dy)) + tuple(v[2:]) for k, v in p.fpos.items()}
        for w in self.wires:
            w[0] = (r2(w[0][0] + dx), r2(w[0][1] + dy)); w[1] = (r2(w[1][0] + dx), r2(w[1][1] + dy))
        for l in self.labels:
            l[2], l[3] = r2(l[2] + dx), r2(l[3] + dy)
        for t in self.texts[self.fixed_texts:]:
            t[1], t[2] = r2(t[1] + dx), r2(t[2] + dy)
        self.ncs = [(r2(x + dx), r2(y + dy)) for x, y in self.ncs]
        for r in self.rects:
            r[0], r[1], r[2], r[3] = r2(r[0] + dx), r2(r[1] + dy), r2(r[2] + dx), r2(r[3] + dy)
        for pl in self.polylines:
            pl[0] = [(r2(x + dx), r2(y + dy)) for x, y in pl[0]]
        for sh in self.sheets:
            sh['x'], sh['y'] = r2(sh['x'] + dx), r2(sh['y'] + dy)
            sh['pins'] = [(n, s, side, r2(pos + (dx if side in ('T', 'B') else dy))) for n, s, side, pos in sh['pins']]
        self.blocks = [(t, (r2(b[0] + dx), r2(b[1] + dy), r2(b[2] + dx), r2(b[3] + dy))) for t, b in self.blocks]

    def centre_on_sheet(self):
        box = self.content_box()
        if not box:
            return
        ax1, ay1, ax2, ay2 = self.area
        cw, ch = box[2] - box[0], box[3] - box[1]
        dx = (ax1 + ax2) / 2 - (box[0] + box[2]) / 2
        dy = (ay1 + ay2) / 2 - (box[1] + box[3]) / 2
        if ch > ay2 - ay1:          # too tall: align to the top (snapping upward keeps the top inside the area)
            dy = ay1 - box[1]
            dy = math.ceil(dy / self.grid) * self.grid if self.grid else dy
        if cw > ax2 - ax1:
            dx = ax1 - box[0]
            dx = math.ceil(dx / self.grid) * self.grid if self.grid else dx
        self.translate(dx, dy)

    # ---------- lint ----------
    def lint(self):
        errs = []
        texts = []     # (box, desc, anchor)
        for p in self.parts:
            for b, d in p.field_boxes():
                texts.append((b, d, None))
        for l in self.labels:
            texts.append((self.label_box(l), 'label %s' % l[1], (l[2], l[3])))
        for i, t in enumerate(self.texts):
            texts.append((self.text_box(t), 'text "%s"' % t[0].split('\n')[0][:40], None))
        bodies = [(p.body(), 'symbol ' + p.ref.format(n='1'), p) for p in self.parts]
        sheets = [(self.sheet_box(sh), 'sheet ' + sh['name']) for sh in self.sheets]
        segs = [(a, b) for a, b, _, _ in self.wires]
        # text vs text
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                if _overlap(texts[i][0], texts[j][0], 0.15):
                    errs.append('text/text: %s %s overlaps %s %s' % (texts[i][1], _fmt(texts[i][0]), texts[j][1], _fmt(texts[j][0])))
        # text vs symbol body / sheet symbol
        for b, d, anc in texts:
            for bb, dd, p in bodies:
                if _overlap(b, bb, 0.15):
                    errs.append('text/symbol: %s %s overlaps %s %s' % (d, _fmt(b), dd, _fmt(bb)))
            for bb, dd in sheets:
                if _overlap(b, bb, 0.15) and not (anc and (abs(anc[0] - bb[0]) < 0.01 or abs(anc[0] - bb[2]) < 0.01)):
                    errs.append('text/sheet: %s overlaps %s' % (d, dd))
        # text vs wire
        for b, d, anc in texts:
            for p, q in segs:
                if anc and (p == anc or q == anc or (p[0] == q[0] == anc[0] and min(p[1], q[1]) <= anc[1] <= max(p[1], q[1]))
                            or (p[1] == q[1] == anc[1] and min(p[0], q[0]) <= anc[0] <= max(p[0], q[0]))):
                    continue
                if _seg_hits_box(p, q, b, 0.1):
                    errs.append('text/wire: %s %s crossed by wire %s-%s' % (d, _fmt(b), p, q))
        # symbol vs symbol, symbol vs foreign wire
        for i in range(len(bodies)):
            for j in range(i + 1, len(bodies)):
                if _overlap(bodies[i][0], bodies[j][0], 0.2):
                    errs.append('symbol/symbol: %s %s overlaps %s %s' % (bodies[i][1], _fmt(bodies[i][0]), bodies[j][1], _fmt(bodies[j][0])))
        for bb, dd, p in bodies:
            pp = p.pin_points()
            for a, b in segs:
                if a in pp or b in pp:
                    continue
                if _seg_hits_box(a, b, bb, 0.3):
                    errs.append('symbol/wire: %s %s crossed by wire %s-%s' % (dd, _fmt(bb), a, b))
        # junction degree and crossings
        deg = {}
        for a, b in segs:
            deg[a] = deg.get(a, 0) + 1; deg[b] = deg.get(b, 0) + 1
        for p in self.parts:
            for q in p.pin_points():
                deg[q] = deg.get(q, 0) + 1
        for q, n in deg.items():
            if n >= 4:
                errs.append('junction: %d connections at %s (max 3; stagger the joints)' % (n, q))
        self.crossings = []
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                (a, b), (c, d) = segs[i], segs[j]
                if a[0] == b[0] and c[1] == d[1]:
                    v, h = (a, b), (c, d)
                elif a[1] == b[1] and c[0] == d[0]:
                    v, h = (c, d), (a, b)
                else:
                    continue
                x, y = v[0][0], h[0][1]
                if min(h[0][0], h[1][0]) < x < max(h[0][0], h[1][0]) and min(v[0][1], v[1][1]) < y < max(v[0][1], v[1][1]):
                    self.crossings.append((x, y))
        # frames
        for i in range(len(self.blocks)):
            for j in range(i + 1, len(self.blocks)):
                if _overlap(self.blocks[i][1], self.blocks[j][1], 0.1):
                    errs.append('frame/frame: "%s" %s overlaps "%s" %s' % (self.blocks[i][0][:14], _fmt(self.blocks[i][1]), self.blocks[j][0][:14], _fmt(self.blocks[j][1])))
        # margins
        box = self.content_box()
        if box:
            ax1, ay1, ax2, ay2 = self.area
            if box[0] < ax1 - 0.01 or box[1] < ay1 - 0.01 or box[2] > ax2 + 0.01 or box[3] > self.H - 18 + 0.01:
                errs.append('margin: content box %s outside the drawable area x %s..%s, y %s..%s' % (_fmt(box), ax1, ax2, ay1, self.H - 18))
            tx, ty = self.title_block
            for b, d in self._item_boxes(dict(parts=0, wires=0, labels=0, texts=self.fixed_texts, ncs=0, polylines=0, sheets=0, rects=0)):
                if b[2] > tx and b[3] > ty:
                    errs.append('margin: %s intrudes into the title block corner' % d)
        return errs

    # ---------- output ----------
    def _connection_points(self):
        pts = []
        for p in self.parts:
            pts += list(p.pin_points())
        for l in self.labels:
            pts.append((l[2], l[3]))
        return pts

    def finalize_wires(self):
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
        seen, ws = set(), []
        for u, v, wd, col in out:
            k = tuple(sorted([u, v]))
            if k not in seen:
                seen.add(k); ws.append([u, v, wd, col])
        self.wires = ws
        cnt = {}
        for u, v, _, _ in ws:
            cnt[u] = cnt.get(u, 0) + 1; cnt[v] = cnt.get(v, 0) + 1
        pinpts = {}
        for p in self.parts:
            for q in p.pin_points():
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
            out.append(['junction', ['at', j[0], j[1]], ['diameter', 0], ['color', 0, 0, 0, 0], ['uuid', Str(uid())]])
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
            out.append(['text', Str(s), ['exclude_from_sim', 'no'], ['at', r2(x), r2(y), ang],
                        ['effects', F(size, bold, italic, col), ['justify'] + just.split()], ['uuid', Str(uid())]])
        for kind, name, x, y, ang, shape, size, col in self.labels:
            fs = size or self.fs_label
            if kind == 'label':
                just = {0: 'left bottom', 180: 'right bottom', 90: 'left bottom', 270: 'right bottom'}[ang]
                out.append(['label', Str(name), ['at', x, y, ang], ['effects', F(fs, color=col), ['justify'] + just.split()], ['uuid', Str(uid())]])
            elif kind == 'hier':
                just = {0: 'left', 180: 'right', 90: 'left', 270: 'right'}[ang]
                out.append(['hierarchical_label', Str(name), ['shape', shape], ['at', x, y, ang],
                            ['effects', F(fs, color=col), ['justify', just]], ['uuid', Str(uid())]])
            else:
                just = {0: 'left', 180: 'right', 90: 'left', 270: 'right'}[ang]
                out.append(['global_label', Str(name), ['shape', shape], ['at', x, y, ang],
                            ['effects', F(fs, color=col), ['justify', just]], ['uuid', Str(uid())],
                            ['property', Str('Intersheetrefs'), Str('${INTERSHEET_REFS}'), ['at', x, y, 0], ['effects', F(fs), ['hide', 'yes']]]])
        for p in self.parts:
            out.append(self._sym_inst(p))
        for sh in self.sheets:
            out.append(self._sheet(sh))
        if self.instances is None:
            out.append(['sheet_instances', ['path', Str('/'), ['page', Str('1')]]])
        out.append(['embedded_fonts', 'no'])
        return dump(out) + '\n'

    def add_sheet(self, name, fname, x, y, w, h, pins, page, show_file=True):
        u = uid()
        x, y, w, h = self.g(x), self.g(y), self.g(w), self.g(h)
        pins = [(n, sh, side, self.g(pos)) for n, sh, side, pos in pins]
        self.sheets.append(dict(name=name, fname=fname, x=x, y=y, w=w, h=h, pins=pins, page=page, uuid=u, show_file=show_file))
        return u

    def _sheet(self, s):
        out = ['sheet', ['at', s['x'], s['y']], ['size', s['w'], s['h']], ['exclude_from_sim', 'no'],
               ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'],
               ['stroke', ['width', 0.1524], ['type', 'solid']], ['fill', ['color', 0, 0, 0, 0.0]],
               ['uuid', Str(s['uuid'])],
               ['property', Str('Sheetname'), Str(s['name']), ['at', s['x'], r2(s['y'] - 0.7), 0],
                ['effects', self.F(max(1.5, self.fs_label), bold=True), ['justify', 'left', 'bottom']]],
               ['property', Str('Sheetfile'), Str(s['fname']), ['at', s['x'], r2(s['y'] + s['h'] + 0.6), 0],
                ['effects', self.F(self.fs_label * 0.8), ['justify', 'left', 'top']] + ([] if s.get('show_file', True) else [['hide', 'yes']])]]
        for name, shape, side, pos in s['pins']:
            # L / R: pos is the pin's y; T / B: pos is the pin's x. KiCad sheet-pin angles: 180 left, 0 right, 90 top, 270 bottom
            if side == 'L':
                px, py, ang, just = s['x'], pos, 180, 'left'
            elif side == 'R':
                px, py, ang, just = r2(s['x'] + s['w']), pos, 0, 'right'
            elif side == 'T':
                px, py, ang, just = pos, s['y'], 90, 'right'
            else:
                px, py, ang, just = pos, r2(s['y'] + s['h']), 270, 'left'
            out.append(['pin', Str(name), shape, ['at', px, py, ang], ['uuid', Str(uid())], ['effects', self.F(self.fs_pin), ['justify', just]]])
        out.append(['instances', ['project', Str(self.project), ['path', Str('/' + self.root), ['page', Str(str(s['page']))]]]])
        return out

    def _sym_inst(self, p):
        s = ['symbol', ['lib_id', Str(p.lib_id)], ['at', p.x, p.y, p.rot]]
        if p.mirror:
            s.append(['mirror', p.mirror])
        s += [['unit', p.unit], ['exclude_from_sim', 'no'], ['in_bom', 'yes' if p.in_bom else 'no'],
              ['on_board', 'yes' if p.on_board else 'no'], ['dnp', 'yes' if p.dnp else 'no'], ['uuid', Str(uid())]]
        libprops = {str(q[1]): str(q[2]) for q in find(p.sym, 'property')}
        props = dict(libprops)
        props['Reference'] = p.ref.format(n='')
        props['Value'] = p.value
        props.update(p.fields_in)
        order = ['Reference', 'Value', 'Footprint', 'Datasheet', 'Description'] + [k for k in props if k not in ('Reference', 'Value', 'Footprint', 'Datasheet', 'Description')]
        for k in order:
            if k not in props or k in ('ki_keywords', 'ki_fp_filters', 'ki_locked'):
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
