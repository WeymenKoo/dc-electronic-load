import re,sys
def fmt(v):
    try: return "%.4g"%float(v)
    except: return v[:30]
for f in sys.argv[1:]:
    t=open(f,encoding='latin-1').read()
    print('=====',f)
    for e in re.findall(r'^.*(?:[Ee]rror|WARNING|failed|Singular).*$',t,re.M)[:5]: print('  !!',e)
    for m in re.finditer(r'Measurement: (\w+)\n.*?\n((?:\s+\d+\t.*\n)+)',t):
        vals=[l.split('\t')[1] for l in m.group(2).strip().splitlines()]
        print('  %-22s %s'%(m.group(1),' | '.join(fmt(v) for v in vals)))
    for m in re.finditer(r'^(\w+): (.*)$',t,re.M):
        if '=' in m.group(2): print('  %-22s %s'%(m.group(1),m.group(2)[:80]))
