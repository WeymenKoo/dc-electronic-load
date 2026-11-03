#!/usr/bin/env python3
"""Prices the KiCad BOM at JLCPCB / LCSC. Lines with an LCSC field are looked up by code; the rest (generic 0603 / 0805 / 1206 resistors
and capacitors, test points, net ties) are searched by value + package, preferring JLC 'basic' parts (no extended-part fee).
Writes <bom>_JLC.csv with the chosen code, stock, unit price at the build quantity and the extended price, then prints the totals.
usage: python3 jlc_bom_price.py ../outputs/rev_e_v1/BOM_RevE.csv [boards=1]"""
import csv, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jlc_price import search, row

PKG = {'R_0603_1608Metric': '0603', 'R_1206_3216Metric': '1206', 'R_2512_6332Metric': '2512',
       'C_0603_1608Metric': '0603', 'C_0805_2012Metric': '0805', 'C_1206_3216Metric': '1206', 'LED_0603_1608Metric': '0603'}
NOT_BOUGHT = {'TestPoint', 'NetTie', 'MountingHole'}          # copper features, no part


def norm_value(v):
    """'10.0k' -> '10k', '0R2 2W' -> '0.2', '100nF 50V' -> '100nF', '22M' -> '22M'"""
    v = v.split()[0]
    m = re.match(r'^(\d+)R(\d+)$', v)
    if m:
        return '%s.%s' % (m.group(1), m.group(2))
    v = v.replace('R', '') if re.match(r'^\d+(\.\d+)?R$', v) else v
    v = re.sub(r'\.0+k$', 'k', v)
    return v


def price_at(prices, qty):
    best = None
    for p in sorted(prices, key=lambda p: p['startNumber']):
        if p['startNumber'] <= qty:
            best = p['productPrice']
    return best if best is not None else (prices[0]['productPrice'] if prices else None)


def pick(line, qty):
    code, value, fp, tol = line['LCSC'].strip(), line['Value'], line['Footprint'], line.get('Tolerance', '')
    if ':' not in fp:
        return dict(code='', mpn=line.get('MPN', ''), stock='', unit=None, note='off-board item, priced by hand')
    if any(k in fp for k in NOT_BOUGHT):
        return dict(code='', mpn='(copper feature)', stock='', unit=0.0, note='no part')
    if code:
        for c in search(code, 5):
            if c.get('componentCode') == code:
                return dict(code=code, mpn=c.get('componentModelEn'), stock=c.get('stockCount'), unit=price_at(c.get('componentPrices') or [], qty),
                            lib=c.get('componentLibraryType'), note='')
        return dict(code=code, mpn='', stock=0, unit=None, note='LCSC code not found')
    name = fp.split(':')[1]
    pkg = PKG.get(name)
    if pkg and name.startswith(('R_', 'C_', 'LED_')):
        v = norm_value(value)
        if name.startswith('R_'):
            kw = '%s %s' % (v if v.endswith(('k', 'M')) or '.' in v else v + 'Ω', pkg)
            kw = kw.replace('kΩ', 'k').replace('MΩ', 'M')
        elif name.startswith('C_'):
            kw = '%s %s' % (v, pkg)
        else:
            kw = ('%s LED %s' % (value.split()[-1], pkg)) if 'LED' in value else ('LED %s' % pkg)
        cands = []
        for c in search(kw, 30):
            d = (c.get('describe') or '') + ' ' + (c.get('componentSpecificationEn') or '')
            if pkg not in d:
                continue
            if name.startswith('R_') and '%' in tol and tol.split('%')[0] + '%' not in d:
                continue
            if name.startswith('C_') and 'C0G' in value and 'C0G' not in d and 'NP0' not in d:
                continue
            pr = c.get('componentPrices') or []
            if not c.get('stockCount') or not pr:
                continue
            cands.append((c.get('componentLibraryType') != 'base', price_at(pr, qty), c))
        if cands:
            cands.sort(key=lambda x: (x[0], x[1]))
            ext, unit, c = cands[0]
            return dict(code=c.get('componentCode'), mpn=c.get('componentModelEn'), stock=c.get('stockCount'), unit=unit,
                        lib=c.get('componentLibraryType'), note='auto: ' + kw)
        return dict(code='', mpn='', stock=0, unit=None, note='no match for ' + kw)
    return dict(code='', mpn=line.get('MPN', ''), stock='', unit=None, note='off-catalogue, priced by hand')


def main():
    src = sys.argv[1]; boards = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    rows = list(csv.DictReader(open(src)))
    out = []
    total, unpriced = 0.0, []
    for r in rows:
        qty = int(r['Qty']) * boards
        p = pick(r, qty)
        ext = (p['unit'] or 0) * qty
        total += ext
        if p['unit'] is None:
            unpriced.append((r['Refs'], r['Value'], p['note']))
        out.append(dict(Refs=r['Refs'], Value=r['Value'], Footprint=r['Footprint'].split(':')[-1], Qty=r['Qty'], LCSC=p['code'], MPN=p['mpn'] or r.get('MPN', ''),
                        Lib=p.get('lib', ''), Stock=p['stock'], Unit_USD='' if p['unit'] is None else '%.4f' % p['unit'], Ext_USD='%.3f' % ext, Note=p['note']))
        print('%-28s %-22s %-10s %-9s %s' % (r['Refs'][:28], r['Value'][:22], p['code'], '' if p['unit'] is None else '%.4f' % p['unit'], p['note']), flush=True)
    dst = src[:-4] + '_JLC.csv'
    with open(dst, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
        w.writerow(dict(Refs='TOTAL (catalogue parts, %d board%s)' % (boards, 's' if boards > 1 else ''), Ext_USD='%.2f' % total))
    print('\nwrote', dst); print('catalogue parts total: $%.2f for %d board(s)' % (total, boards))
    if unpriced:
        print('not priced (%d lines):' % len(unpriced))
        for u in unpriced:
            print('  ', u)


if __name__ == '__main__':
    main()
