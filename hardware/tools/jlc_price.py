#!/usr/bin/env python3
"""Looks parts up in the JLCPCB parts catalogue (same data as LCSC) and prints LCSC code, stock, basic/extended and the price
ladder. Keywords are LCSC codes or manufacturer part numbers.
usage: python3 jlc_price.py KEYWORD [KEYWORD ...]        one line per keyword, best (cheapest in-stock) match
       python3 jlc_price.py -a KEYWORD                   all matches"""
import json, sys, urllib.request, time

URL = 'https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList'


def search(keyword, n=10):
    body = json.dumps({'keyword': keyword, 'currentPage': 1, 'pageSize': n, 'searchSource': 'search', 'componentLibraryType': ''}).encode()
    req = urllib.request.Request(URL, data=body, headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    for attempt in range(3):
        try:
            d = json.load(urllib.request.urlopen(req, timeout=30))
            return (d.get('data') or {}).get('componentPageInfo', {}).get('list') or []
        except Exception as e:
            time.sleep(2)
    return []


def row(c):
    pr = sorted(c.get('componentPrices') or [], key=lambda p: p['startNumber'])
    ladder = ' '.join('%d+:%.4f' % (p['startNumber'], p['productPrice']) for p in pr[:4])
    return dict(code=c.get('componentCode'), mpn=c.get('componentModelEn'), brand=c.get('componentBrandEn'), pkg=c.get('componentSpecificationEn'),
                stock=c.get('stockCount'), lib=c.get('componentLibraryType'), p1=pr[0]['productPrice'] if pr else None, ladder=ladder,
                descr=(c.get('describe') or '')[:90])


def best(keyword):
    rows = [row(c) for c in search(keyword)]
    rows = [r for r in rows if r['stock'] and r['p1'] is not None]
    if not rows:
        return None
    exact = [r for r in rows if (r['mpn'] or '').upper() == keyword.upper() or r['code'] == keyword]
    rows = exact or rows
    rows.sort(key=lambda r: (r['lib'] != 'base', r['p1']))
    return rows[0]


if __name__ == '__main__':
    args = sys.argv[1:]
    if args and args[0] == '-a':
        for c in search(args[1], 20):
            r = row(c); print('%-10s %-28s %-14s %-24s stock %-7s %-8s %s   %s' % (r['code'], r['mpn'], r['brand'], r['pkg'], r['stock'], r['lib'], r['ladder'], r['descr']))
        sys.exit()
    for k in args:
        r = best(k)
        if r:
            print('%-24s %-10s %-28s %-24s stock %-7s %-8s %s' % (k, r['code'], r['mpn'], r['pkg'], r['stock'], r['lib'], r['ladder']))
        else:
            print('%-24s NOT FOUND' % k)
