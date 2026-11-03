#!/usr/bin/env python3
"""Builds ../rev_e/DC_Load_RevE.kicad_pcb from the exported netlist: PLACEMENT ONLY, no tracks, no zones.

One 2-LAYER fabrication panel, 170 x 100 mm (the heatsink length by the heatsink base width plus a 40 mm front panel), V-scored at y = 40:
  control board  y 0..40     vertical front panel, 170 x 40. F.Cu = the face the user sees: encoder, three buttons, two LEDs and the OLED
                             window (the module hangs on J5 and sits on the bezel over the left part of the board; keep that area low).
                             USB-C leaves the left edge. J10 (vertical IDC box header) is hand-soldered on the BACK face so the ribbon
                             leaves rearward.
  power board    y 40..100   lies on the heatsink base, F.Cu = top. The four TO-247 are hand-soldered UNDER the board (tab down on the 3 mm
                             base, leads bent up through the pad row 32 mm from the front edge); the heatsink wall is the rear edge (y 100).
                             USB-side island (J11, isolator side 1, DC-DC input) in the front-left corner behind a 4 mm L-shaped keep-out.
                             DUT+ and DUT- are plated M4 holes (ring lugs) at the right and the rear.
Coordinates below are panel millimetres, origin top-left, y down; the finished panel is moved to the centre of the A4 sheet and the aux /
grid origins are set to its top-left corner. Anchors are placed by the centre of their courtyard, small parts are packed into named bins
next to the part they serve, then every reference label is moved to a free spot around its part.

run:  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 place_reve.py
      (KiCad's own python, it has pcbnew). Re-running OVERWRITES the board file: once hand layout starts, stop running it."""
import os, sys
import xml.etree.ElementTree as ET
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
XML = os.path.join(HERE, '..', 'outputs', 'rev_e_v1', 'DC_Load_RevE.xml')
OUT = os.path.join(HERE, '..', 'rev_e', 'DC_Load_RevE.kicad_pcb')
KFP = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/'
PFP = os.path.join(HERE, '..', 'libraries', 'footprints')

mm = pcbnew.FromMM
KEEP = []                                       # python wrappers of everything handed to the board; never let them be collected
def keep(x):
    KEEP.append(x)
    try:
        x.thisown = 0
    except Exception:
        pass
    return x
def V(x, y): return pcbnew.VECTOR2I(mm(x), mm(y))
def log(*a): print(*a, flush=True)
F, B = pcbnew.F_Cu, pcbnew.B_Cu

# ------------------------------------------------------------------ geometry
W, HC, HP = 170.0, 40.0, 60.0                   # panel width (= heatsink length), control board height, power board height
Y0P = HC                                        # power board top edge = V-score line (40)
SCORE_KEEP = 1.5                                # no courtyard closer than this to the V-score
HS_X0, HS_X1 = 0.0, 170.0                       # heatsink base under the power board: the full width
FET_X = [31, 69, 107, 145]                      # TO-247 pad-row centres, 38 mm pitch (>= 25 required, 3 mm base spreads ~50 mm under forced air)
LAYERS = 2
py = lambda yb: Y0P + yb                        # power-board local y (from its front edge) -> panel y
FET_Y = py(32)                                  # pad row: bodies extend to the rear under the board
ISL_X, ISL_Y = 36.0, py(22)                     # island: x < 36, y < ISL_Y on the power board; 4 mm bands beyond
PAGE_W, PAGE_H = 297.0, 210.0                   # A4 landscape

# ------------------------------------------------------------------ netlist
def read_netlist(path):
    root = ET.parse(path).getroot()
    comps = {}
    for c in root.iter('comp'):
        fp = c.findtext('footprint') or ''
        if not fp:
            continue
        sp = c.find('sheetpath').get('tstamps')
        comps[c.get('ref')] = dict(fp=fp, value=c.findtext('value') or '', path=sp + c.findtext('tstamps'))
    nets = {}
    for n in root.iter('net'):
        nodes = [(nd.get('ref'), nd.get('pin')) for nd in n.findall('node')]
        if nodes:
            nets[n.get('name')] = nodes
    return comps, nets

# ------------------------------------------------------------------ footprints
def load_fp(fpid):
    lib, name = fpid.split(':')
    path = os.path.join(PFP, lib + '.pretty') if lib == 'dcload' else KFP + lib + '.pretty'
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit('footprint not found: ' + fpid)
    return fp

def crt_box(fp):
    """courtyard bbox in mm (x1, y1, x2, y2); falls back to the body bbox when the footprint has no courtyard"""
    layer = pcbnew.B_CrtYd if fp.GetLayer() == B else pcbnew.F_CrtYd
    poly = fp.GetCourtyard(layer)
    bb = poly.BBox() if poly.OutlineCount() else fp.GetBoundingBox(False)
    if bb.GetWidth() == 0:
        bb = fp.GetBoundingBox(False)
    return (bb.GetLeft() / 1e6, bb.GetTop() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6)

def place_centre(fp, cx, cy, rot):
    fp.SetOrientationDegrees(rot)
    x1, y1, x2, y2 = crt_box(fp)
    p = fp.GetPosition()
    fp.SetPosition(pcbnew.VECTOR2I(p.x + mm(cx - (x1 + x2) / 2), p.y + mm(cy - (y1 + y2) / 2)))

def place_pad(fp, pad_name, px, py_, rot):
    fp.SetOrientationDegrees(rot)
    pad = [p for p in fp.Pads() if p.GetNumber() == pad_name][0]
    pp = pad.GetPosition(); p = fp.GetPosition()
    fp.SetPosition(pcbnew.VECTOR2I(p.x + mm(px) - pp.x, p.y + mm(py_) - pp.y))

def pad_pos(fp, name):
    p = [q for q in fp.Pads() if q.GetNumber() == name][0].GetPosition()
    return p.x / 1e6, p.y / 1e6

def overlaps(a, b, m=0.0):
    return a[0] - m < b[2] and a[2] + m > b[0] and a[1] - m < b[3] and a[3] + m > b[1]

# ------------------------------------------------------------------ bin packer
class Packer:
    """scans a bin on a 0.5 mm grid for the first spot whose courtyard (plus margin) hits nothing already there"""
    def __init__(self):
        self.occ = []                         # placed rects (everything is on the top side)
        self.margin = 1.2                     # room for a 0.8 mm reference label in every gap between neighbours

    def block(self, rect):
        self.occ.append(rect)

    def register(self, fp, rect=None):
        self.occ.append(rect or crt_box(fp))

    def fits(self, r, bin_rect):
        m = self.margin
        if r[0] - m < bin_rect[0] or r[1] - m < bin_rect[1] or r[2] + m > bin_rect[2] or r[3] + m > bin_rect[3]:
            return False
        return not any(overlaps(r, a, m) for a in self.occ)

    def pack(self, fp, bin_rect, rots=(0, 90), step=0.5, margin=None):
        saved = self.margin
        if margin is not None:
            self.margin = margin
        try:
            return self._pack(fp, bin_rect, rots, step)
        finally:
            self.margin = saved

    def _pack(self, fp, bin_rect, rots, step):
        for rot in rots:
            fp.SetOrientationDegrees(rot)
            x1, y1, x2, y2 = crt_box(fp)
            w, h = x2 - x1, y2 - y1
            if w > bin_rect[2] - bin_rect[0] or h > bin_rect[3] - bin_rect[1]:
                continue
            y = bin_rect[1] + self.margin
            while y + h + self.margin <= bin_rect[3] + 1e-6:
                x = bin_rect[0] + self.margin
                while x + w + self.margin <= bin_rect[2] + 1e-6:
                    r = (x, y, x + w, y + h)
                    if self.fits(r, bin_rect):
                        p = fp.GetPosition()
                        fp.SetPosition(pcbnew.VECTOR2I(p.x + mm(x - x1), p.y + mm(y - y1)))
                        self.register(fp, r)
                        return True
                    x += step
                y += step
        return False

# ------------------------------------------------------------------ board helpers
def add_seg(board, layer, a, b, w=0.1):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(layer)
    s.SetStart(V(*a)); s.SetEnd(V(*b)); s.SetWidth(mm(w)); board.Add(keep(s))

def add_rect(board, layer, a, b, w=0.12):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_RECT); s.SetLayer(layer)
    s.SetStart(V(*a)); s.SetEnd(V(*b)); s.SetWidth(mm(w)); board.Add(keep(s))

def add_circle(board, layer, c, r, w=0.12):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_CIRCLE); s.SetLayer(layer)
    s.SetStart(V(*c)); s.SetEnd(V(c[0] + r, c[1])); s.SetWidth(mm(w)); board.Add(keep(s))

def add_text(board, layer, s, x, y, size=1.0, rot=0, bold=False, just='center'):
    t = pcbnew.PCB_TEXT(board); t.SetText(s); t.SetLayer(layer); t.SetPosition(V(x, y))
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(size * 0.15)); t.SetTextAngleDegrees(rot)
    if bold: t.SetBold(True)
    if just == 'left': t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    board.Add(keep(t))

def rule_area(board, name, pts):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True); z.SetZoneName(name)
    z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    z.SetLayerSet(pcbnew.LSET.AllCuMask(LAYERS))
    poly = pcbnew.SHAPE_POLY_SET(); poly.NewOutline()
    for x, y in pts:
        poly.Append(mm(x), mm(y))
    keep(poly); z.SetOutline(poly); board.Add(keep(z))

def board_only(fp):
    fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

def npth_footprint(board, name, holes, dia, silk_r=None):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPID(pcbnew.LIB_ID('dcload', name))
    for dx, dy in holes:
        pad = pcbnew.PAD(fp)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetSize(pcbnew.VECTOR2I(mm(dia), mm(dia))); pad.SetDrillSize(pcbnew.VECTOR2I(mm(dia), mm(dia)))
        pad.SetLayerSet(pcbnew.PAD.UnplatedHoleMask())
        pad.SetPosition(pcbnew.VECTOR2I(mm(dx), mm(dy))); pad.SetNumber('')
        fp.Add(keep(pad))
    if silk_r:
        s = pcbnew.PCB_SHAPE(fp); s.SetShape(pcbnew.SHAPE_T_CIRCLE); s.SetLayer(pcbnew.F_SilkS)
        s.SetStart(V(0, 0)); s.SetEnd(V(silk_r, 0)); s.SetWidth(mm(0.12)); fp.Add(keep(s))
    fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    board_only(fp)
    return keep(fp)

# ------------------------------------------------------------------ placement plan (all on F.Cu)
XC = lambda i: FET_X[i]
ANCHORS = {
    # ---- control board: what the user sees (OLED window x 14..50, nothing tall there)
    'ENC1': (140, 21, 0),
    'SW3': (98, 30, 0), 'SW4': (112, 30, 0), 'SW5': (126, 30, 0),
    'D5': (56, 9, 0), 'D6': (56, 15, 0), 'D2': (56, 25, 0), 'D4': (56, 31, 0),
    'J5': (32, 36, 0),
    # ---- control board: electronics beside the window, under the bezel
    'J1': (6.0, 20, 270), 'U4': (80, 17, 0), 'SW1': (72, 34, 0), 'SW2': (84, 34, 0),
    'J10': (120, 11, 0, None, 'B'), 'J2': (154, 34, 0), 'J3': (152, 10, 90), 'J4': (161, 24, 90),
    # ---- power board
    'J11': (15, py(9), 90), 'U8': (16, ISL_Y + 2, 270), 'PS1': (ISL_X + 2, py(9), 0), 'U11': (88, py(26), 0),
    'NT1': (76, py(38), 0), 'J6': (128, py(50), 0), 'J8': (88, py(54), 0),
    'F1': (162, py(38), 90), 'J7': (162, py(21), 0), 'D51': (155, py(50), 90), 'R71': (164, py(50), 90), 'C58': (164, py(56), 0),
}
for n in range(4):
    xc = XC(n)
    ANCHORS['Q%d01' % (n + 1)] = (xc, FET_Y, 180, '2')                   # by pad 2 (drain), pin 1 to the right (tab-down under the board)
    ANCHORS['R%d06' % (n + 1)] = (xc - 9.5, py(40), 90)                  # Rs pair beside the source pad
    ANCHORS['R%d07' % (n + 1)] = (xc - 14, py(40), 90)
LOCK = {'ENC1', 'SW3', 'SW4', 'SW5', 'J1', 'J5', 'J10', 'J11', 'U8', 'PS1', 'J6', 'J7', 'J8', 'F1',
        'Q101', 'Q201', 'Q301', 'Q401'}

def chk_u8(fp):                 # pins 1..8 (side 1) toward the island = smaller y
    return pad_pos(fp, '1')[1] < pad_pos(fp, '16')[1]
def chk_ps1(fp):                # pin row along x across the vertical band, pin 1 (VIN+) on the island side = smaller x
    p1, p4 = pad_pos(fp, '1'), pad_pos(fp, '4')
    return abs(p1[1] - p4[1]) < 0.1 and p1[0] < p4[0]
def chk_fet(fp):                # gate (pin 1) at +x: TO-247 tab down with the leads toward the front reads S D G left to right
    return pad_pos(fp, '1')[0] > pad_pos(fp, '3')[0]
def chk_j1(fp):                 # USB-C opening toward the left edge: pin row vertical and to the right of the courtyard centre
    a1, a12 = pad_pos(fp, 'A1'), pad_pos(fp, 'A12'); c = crt_box(fp)
    return abs(a1[0] - a12[0]) < 0.1 and a1[0] > (c[0] + c[2]) / 2
def chk_j11(fp):                # vertical header, rows along x, pin 1 at the left
    p1, p11 = pad_pos(fp, '1'), pad_pos(fp, '11')
    return abs(p1[1] - p11[1]) < 0.1 and p1[0] < p11[0]
def chk_j10(fp):                # vertical header on the back face, rows along x
    p1, p11 = pad_pos(fp, '1'), pad_pos(fp, '11')
    return abs(p1[1] - p11[1]) < 0.1
CHECKS = {'U8': chk_u8, 'PS1': chk_ps1, 'Q101': chk_fet, 'Q201': chk_fet, 'Q301': chk_fet, 'Q401': chk_fet, 'J1': chk_j1, 'J10': chk_j10, 'J11': chk_j11}

CH = lambda n, names: ['%s%d%02d' % (k, n, i) for k, i in names]
AMP = [('R', 1), ('R', 2), ('R', 3), ('R', 5), ('R', 8), ('C', 1), ('D', 1), ('D', 2)]
CB_BOT = HC - SCORE_KEEP                        # 38.5: nothing below this on the control board
BINS = [
    # control board
    ('cb_usb',   (1, 30, 13, CB_BOT), ['D1', 'R1', 'R2', 'U1', 'C1', 'C2', 'R3']),
    ('cb_usb2',  (1, 1, 13, 10), ['D1', 'R1', 'R2', 'U1', 'C1', 'C2', 'R3']),
    ('cb_led',   (52, 1, 64, CB_BOT), ['R17', 'R18', 'R16']),
    ('cb_mcu',   (66, 1, 96, 9), ['C13', 'C14', 'C15', 'C16', 'C17', 'C18', 'C19', 'R13']),
    ('cb_mcu2',  (66, 25, 96, 30), ['C13', 'C14', 'C15', 'C16', 'C17', 'C18', 'C19', 'R13']),
    ('cb_hdr',   (96, 1, 108, 24), ['R14', 'R15', 'R19', 'R20', 'C24', 'C25']),
    ('cb_fan',   (132, 1, 170, 5), ['Q1', 'Q2', 'Q3', 'R7', 'R8', 'R9', 'R10', 'R11', 'C3']),
    ('cb_fan2',  (132, 28, 148, CB_BOT), ['Q1', 'Q2', 'Q3', 'R7', 'R8', 'R9', 'R10', 'R11', 'C3']),
    ('cb_spill', (108, 17, 132, 24), []),
    ('cb_spill2', (14, 1, 50, 6), []),
    # power board
    ('pb_isl_L',  (0.6, py(15), 10.5, py(21.5)), ['C27', 'R21', 'R22', 'R23']),
    ('pb_isl_R',  (22, py(14.5), 36, py(21.5)), ['C6', 'R23', 'R22', 'R21', 'C27']),
    ('pb_isopwr', (42, py(SCORE_KEEP), 56, py(19.5)), ['U3', 'C7', 'C8', 'R12', 'C9', 'C10', 'C11', 'C12']),
    ('pb_isoB',   (0.8, py(31), 18, py(40)), ['C28']),
    ('pb_dacadc', (57, py(SCORE_KEEP), 80, py(19.5)), ['U9', 'U10', 'C29', 'R24', 'C30', 'C31', 'C32']),
    ('pb_set',    (81, py(SCORE_KEEP), 104, py(19.5)), ['U12', 'Q11', 'Q12', 'Q13', 'R31', 'R32', 'R33', 'R34', 'R35', 'R36', 'R37', 'C33', 'C34', 'C35', 'TP11', 'TP31']),
    ('pb_sense',  (105, py(SCORE_KEEP), 128, py(19.5)), ['R45', 'R48', 'R41', 'R42', 'R43', 'R44', 'R46', 'R47', 'R49', 'R50', 'C41', 'C42', 'D41', 'D42', 'TP21', 'TP22']),
    ('pb_prot',   (129, py(SCORE_KEEP), 153, py(20.5)), ['U14', 'R60', 'C57'] + ['R%d' % i for i in range(51, 71) if i != 60] + ['C%d' % i for i in range(51, 57)] + ['D43', 'D44', 'D45', 'TP41']),
    ('pb_ppath',  (154, py(SCORE_KEEP), 169.4, py(19)), ['J9', 'R72', 'R73', 'TP51', 'TP52']),
    ('pb_ampL',   (64, py(21), 80, py(29)), CH(1, AMP) + CH(2, AMP)),
    ('pb_ampL2',  (42, py(21), 62, py(29)), CH(1, AMP) + CH(2, AMP)),
    ('pb_ampR',   (96, py(21), 112, py(29)), CH(3, AMP) + CH(4, AMP)),
    ('pb_ampR2',  (114, py(21), 134, py(29)), CH(3, AMP) + CH(4, AMP)),
    ('pb_prot2',  (136, py(21.5), 152, py(29)), ['R%d' % i for i in range(51, 71)] + ['C%d' % i for i in range(51, 58)]),
]
for n in range(4):
    xc = XC(n)
    BINS.append(('pb_ch%d' % (n + 1), (xc + 2, py(35), xc + 16, py(47)), CH(n + 1, [('R', 4), ('D', 3), ('TP', 1), ('TP', 2)])))
BINS += [
    ('pb_ampL3',  (40, py(35), 54, py(55)), CH(1, AMP) + CH(2, AMP)),
    ('pb_ampR4',  (114, py(35), 126, py(55)), CH(3, AMP) + CH(4, AMP)),
    ('pb_prot3',  (136, py(31), 150, py(44)), ['D44', 'D45', 'D43'] + ['R%d' % i for i in range(51, 71)] + ['C%d' % i for i in range(51, 58)]),
]
BINS.append(('pb_spill', (0.8, py(41), 18, py(50)), []))
BINS.append(('pb_spill2', (20, py(47.5), 56, py(58)), []))
BINS.append(('pb_spill3', (96, py(31), 112, py(34)), []))

HOLES = {'H1': (4, 4), 'H2': (166, 4), 'H3': (4, 36), 'H4': (166, 36),                  # control board, enclosure standoffs
         'H5': (5, py(26)), 'H6': (165, py(4)), 'H7': (15, py(54)), 'H8': (62, py(57))}  # power board, M3 tapped into the 3 mm base


# ------------------------------------------------------------------ reference labels
def board_rect_for(cy):
    if cy < HC:
        return (0.6, 0.6, W - 0.6, HC - 1.2)
    return (0.6, HC + 1.2, W - 0.6, HC + HP - 0.6)

def place_refs(fps, occ):
    size, thick = 0.8, 0.12
    labels, failed = [], []
    for ref, fp in fps.items():
        t = fp.Reference()
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(thick))
        txt = fp.GetReference()
        w, h = max(1.2, len(txt) * size * 1.0), size
        x1, y1, x2, y2 = crt_box(fp); cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        others = [r for r in occ if not (abs(r[0] - x1) < 0.05 and abs(r[1] - y1) < 0.05 and abs(r[2] - x2) < 0.05 and abs(r[3] - y2) < 0.05)]
        brd = board_rect_for(cy)
        cands = []
        for d in (0.25, 0.7, 1.2, 1.8, 2.5, 3.3):
            cands += [((cx, y1 - d - h / 2), 0, w, h), ((cx, y2 + d + h / 2), 0, w, h),
                      ((x1 - d - h / 2, cy), 90, h, w), ((x2 + d + h / 2, cy), 90, h, w)]
            cands += [((x1 + w / 2, y1 - d - h / 2), 0, w, h), ((x2 - w / 2, y1 - d - h / 2), 0, w, h),
                      ((x1 + w / 2, y2 + d + h / 2), 0, w, h), ((x2 - w / 2, y2 + d + h / 2), 0, w, h)]
        done = False
        for (px, pyy), ang, bw, bh in cands:
            box = (px - bw / 2, pyy - bh / 2, px + bw / 2, pyy + bh / 2)
            if box[0] < brd[0] or box[1] < brd[1] or box[2] > brd[2] or box[3] > brd[3]:
                continue
            if any(overlaps(box, r, 0.2) for r in others) or any(overlaps(box, l, 0.1) for l in labels):
                continue
            t.SetPosition(V(px, pyy)); t.SetTextAngleDegrees(ang); t.SetVisible(True)
            labels.append(box); done = True
            break
        if not done:
            failed.append(ref)
    return failed


def main():
    comps, nets = read_netlist(XML)
    log('netlist', len(comps), 'components', len(nets), 'nets')
    board = pcbnew.BOARD()
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(LAYERS)
    # page: KiCad's default for a new board is A4 landscape, which is what the centring below assumes
    try:
        board.SetLayerName(pcbnew.User_1, 'V_SCORE'); VLAYER = pcbnew.User_1
    except Exception:
        VLAYER = pcbnew.Cmts_User
    # --- nets
    netmap = {}
    for name in nets:
        ni = pcbnew.NETINFO_ITEM(board, name); board.Add(keep(ni)); netmap[name] = ni
    # --- footprints
    fps = {}
    for ref, c in comps.items():
        fp = load_fp(c['fp'])
        fp.SetReference(ref); fp.SetValue(c['value'])
        fp.SetPath(pcbnew.KIID_PATH(c['path']))
        board.Add(keep(fp)); fps[ref] = fp
    for name, nodes in nets.items():
        for ref, pin in nodes:
            if ref not in fps:
                continue
            for pad in fps[ref].Pads():
                if pad.GetNumber() == pin:
                    pad.SetNet(netmap[name])
    log('footprints loaded and netted')

    packer = Packer()
    # --- board-only mechanical footprints first, so the packer keeps clear of them
    for ref, (x, y) in HOLES.items():
        fp = load_fp('MountingHole:MountingHole_3.2mm_M3'); fp.SetReference(ref); fp.Reference().SetVisible(False)
        board_only(fp); fp.SetPosition(V(x, y)); fp.SetLocked(True); board.Add(keep(fp)); packer.block(crt_box(fp))
    for n in range(4):
        fp = npth_footprint(board, 'ScrewAccess_D7', [(0, 0)], 7.0, silk_r=3.8)
        fp.SetReference('HA%d' % (n + 1)); fp.SetPosition(V(XC(n), py(51.5))); fp.SetLocked(True); board.Add(fp)
        packer.block((XC(n) - 4, py(47.5), XC(n) + 4, py(55.5)))
    # keep the V-score corridor free
    packer.block((-1, HC - SCORE_KEEP, W + 1, HC + SCORE_KEEP))

    # --- anchors
    for ref, a in ANCHORS.items():
        fp = fps.get(ref)
        if fp is None:
            log('anchor without footprint:', ref); continue
        x, y, rot = a[:3]
        by_pad = a[3] if len(a) > 3 else None
        if len(a) > 4 and a[4] == 'B':                       # hand-soldered THT header on the back face of the control board
            fp.Flip(fp.GetPosition(), False)
        rots = [rot] + [r for r in (0, 90, 180, 270) if r != rot]
        for r in rots:
            if by_pad:
                place_pad(fp, by_pad, x, y, r)
            else:
                place_centre(fp, x, y, r)
            if ref not in CHECKS or CHECKS[ref](fp):
                if r != rot:
                    log('  %s: rotation corrected %d -> %d' % (ref, rot, r))
                break
        else:
            log('  WARNING %s: no rotation satisfies its check' % ref)
        if ref in LOCK:
            fp.SetLocked(True)
        packer.register(fp)

    # --- bins
    placed = set(ANCHORS)
    for b in BINS:
        name, rect, refs = b[:3]; margin = b[3] if len(b) > 3 else None
        for ref in refs:
            if ref in placed or ref not in fps:
                continue
            if packer.pack(fps[ref], rect, margin=margin):
                placed.add(ref)
    home = {}
    for b in BINS:
        for ref in b[2]:
            home.setdefault(ref, b[0][:2])
    for ref in [r for r in fps if r not in placed]:
        for b in BINS:
            name, rect = b[0], b[1]
            if name.startswith(home.get(ref, 'pb') + '_spill') and packer.pack(fps[ref], rect):
                placed.add(ref); log('  spilled %s into %s' % (ref, name)); break
    left = [r for r in fps if r not in placed]
    if left:
        log('UNPLACED:', left)
        for i, ref in enumerate(left):
            fps[ref].SetPosition(V(10 + 6 * i, HC + HP + 10))
    log('bins done')

    # --- reference labels
    failed = place_refs(fps, packer.occ)
    log('reference labels placed, %d left at their default spot: %s' % (len(failed), failed))

    # --- outline and V-score
    E = pcbnew.Edge_Cuts
    add_rect(board, E, (0, 0), (W, HC + HP), 0.1)
    add_seg(board, VLAYER, (-3, HC), (W + 3, HC), 0.15)
    add_text(board, VLAYER, 'V-SCORE', -8, HC, 1.2); add_text(board, VLAYER, 'V-SCORE', W + 8, HC, 1.2)

    # --- isolation keep-out on the power board: L around the USB-side island, all four copper layers
    rule_area(board, 'ISO_BARRIER_4mm_A', [(0, ISL_Y), (ISL_X + 4, ISL_Y), (ISL_X + 4, ISL_Y + 4), (0, ISL_Y + 4)])
    rule_area(board, 'ISO_BARRIER_4mm_B', [(ISL_X, Y0P), (ISL_X + 4, Y0P), (ISL_X + 4, ISL_Y + 4), (ISL_X, ISL_Y + 4)])

    # --- mechanical drawing (User.Drawings) and notes (User.Comments)
    D, Cm = pcbnew.Dwgs_User, pcbnew.Cmts_User
    add_rect(board, D, (HS_X0 + 0.3, Y0P + 0.3), (HS_X1 - 0.3, Y0P + HP - 0.3), 0.2)
    add_text(board, D, 'HEATSINK BASE 170 x 60 x 3 = this board outline, fins below. 4 x M3 tapped; keep-out rings (sink = USB side)', 62, py(58.6), 0.9)
    add_rect(board, D, (HS_X0, Y0P + HP + 0.5), (HS_X1, Y0P + HP + 5.5), 0.2)
    add_text(board, D, 'HEATSINK WALL 45 mm tall (rear). Enclosure rear panel. Ragged fins behind it.', 85, Y0P + HP + 3, 1.0)
    for n in range(4):
        xc = XC(n)
        add_rect(board, D, (xc - 8, py(36)), (xc + 8, py(57)), 0.15)
        add_circle(board, D, (xc, py(51.5)), 1.8, 0.15)
        add_text(board, D, 'Q%d01 body UNDER board, tab down' % (n + 1), xc, py(40), 0.7)
        add_text(board, D, 'M3 + pad + shoulder washer', xc, py(44), 0.7)
    add_circle(board, D, (126, py(44)), 2.5, 0.15); add_text(board, D, 'NTC lug under board', 126, py(47.5), 0.7)
    add_text(board, Cm, 'CONTROL BOARD 170 x 40   F.Cu = front face (bezel over the electronics); J10 on the back', 85, -2.5, 1.5, bold=True)
    add_text(board, Cm, 'POWER BOARD 170 x 60   F.Cu = top, all parts; TO-247 hand-soldered underneath; heatsink wall at the rear edge', 85, Y0P + HP + 8.5, 1.5, bold=True)
    add_rect(board, Cm, (14, 2), (50, 38), 0.15); add_text(board, Cm, 'OLED module window (1.3" SH1106, 35 x 34 mm) on the bezel; low parts only', 32, 20, 0.7)
    add_text(board, Cm, 'BARRIER', 4.5, ISL_Y + 2, 0.7)
    add_text(board, Cm, 'barrier', ISL_X + 2, Y0P + 8, 0.7, rot=90)
    add_text(board, Cm, 'USB-C exits the LEFT edge', 7, 31.5, 0.8, rot=90)
    add_text(board, Cm, 'TOP of the front panel', 85, 1.0, 0.8)
    add_text(board, Cm, 'J10 (back face) ribbon rearward -> J11 (vertical) on the island; pin 1 to pin 1', 120, 17.5, 0.7)
    add_text(board, Cm, 'ISOLATION BARRIER = rule areas ISO_BARRIER_4mm_A / _B on both copper layers: no copper, tracks, vias or pours', 100, py(0.75), 0.7)
    add_text(board, Cm, 'DRAIN bus: F1 -> 4 drains along the pad row, >= 5 mm of 2 oz on both layers. PGND: Rs bottoms -> NT1 -> J8. Analog pour ties at NT1 only', 88, py(30.5), 0.7)
    add_text(board, Cm, 'J7 / J8: plated M4 holes, ring lugs under the bolt heads', 150, py(58.6), 0.7)

    # --- centre the panel on the A4 sheet, origins at its top-left corner
    dx, dy = (PAGE_W - W) / 2, (PAGE_H - (HC + HP)) / 2
    off = V(dx, dy)
    for fp in board.GetFootprints():
        fp.Move(off)
    for d in board.GetDrawings():
        d.Move(off)
    for z in board.Zones():
        z.Move(off)
    ds.SetAuxOrigin(off); ds.SetGridOrigin(off)

    pcbnew.SaveBoard(OUT, board)
    log('wrote %s: %d footprints, %d nets, %d unplaced, panel origin at (%.1f, %.1f)' % (OUT, len(fps), len(nets), len(left), dx, dy))


if __name__ == '__main__':
    main()
