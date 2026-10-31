import olefile, sys, struct, collections
def recs(path):
    d = olefile.OleFileIO(path).openstream('FileHeader').read()
    out=[]; i=0
    while i < len(d):
        n=struct.unpack('<I',d[i:i+4])[0]; ln=n&0xffffff
        s=d[i+4:i+4+ln].rstrip(b'\0').decode('latin1'); i+=4+ln
        r={}
        for kv in s.split('|'):
            if '=' in kv:
                k,v=kv.split('=',1); r[k.upper()]=v
        out.append(r)
    return out
def c(r,k):
    v=float(r.get(k,0) or 0)+float(r.get(k+'_FRAC',0) or 0)/1e5
    return v
def P(r,p='LOCATION.'): return (round(c(r,p+'X'),2), round(c(r,p+'Y'),2))
def run(path):
    R=recs(path); hdr=R[0]; R=R[1:]
    comps={}
    for idx,r in enumerate(R):
        if r.get('RECORD')=='1': comps[idx]={'lib':r.get('LIBREFERENCE',''),'desc':r.get('COMPONENTDESCRIPTION',''),'part':r.get('CURRENTPARTID','1'),'mode':r.get('DISPLAYMODE','0'),'des':'?','params':{}}
    for r in R:
        o=r.get('OWNERINDEX')
        if o is None: continue
        o=int(o)
        if o in comps:
            if r.get('RECORD')=='34': comps[o]['des']=r.get('TEXT','?')
            if r.get('RECORD')=='41': comps[o]['params'][r.get('NAME','')]=r.get('TEXT','')
    parent=dict()
    def f(x):
        parent.setdefault(x,x)
        while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
        return x
    def u(a,b): parent[f(a)]=f(b)
    pts=[]; segs=[]; names=collections.defaultdict(set); pinat=collections.defaultdict(list)
    dirs={0:(1,0),1:(0,1),2:(-1,0),3:(0,-1)}
    for r in R:
        t=r.get('RECORD')
        if t=='2':
            o=int(r.get('OWNERINDEX',-1))
            if o not in comps: continue
            cp=comps[o]
            if r.get('OWNERPARTID','1') not in (cp['part'],'-1','0'): continue
            if r.get('OWNERPARTDISPLAYMODE','0')!=cp['mode']: continue
            x,y=P(r); L=c(r,'PINLENGTH'); ori=int(r.get('PINCONGLOMERATE','0'))&3
            dx,dy=dirs[ori]; p=(round(x+dx*L,2),round(y+dy*L,2))
            pts.append(p); pinat[p].append('%s.%s(%s)'%(cp['des'],r.get('DESIGNATOR',''),r.get('NAME','')))
        elif t=='27':
            n=int(r.get('LOCATIONCOUNT',0)); v=[(round(c(r,'X%d'%k),2),round(c(r,'Y%d'%k),2)) for k in range(1,n+1)]
            for a,b in zip(v,v[1:]): segs.append((a,b)); u(a,b)
            pts+=v
        elif t in ('25','17'):
            p=P(r); pts.append(p); names[p].add(r.get('TEXT',''))
        elif t=='18':
            p=P(r); w=c(r,'WIDTH'); st=int(r.get('STYLE','0') or 0)
            pts.append(p); names[p].add('PORT:'+r.get('NAME',''))
            p2=(round(p[0]+w,2),p[1]) if st in (0,1,2,3) else (p[0],round(p[1]+w,2))
            # style 0-3 horizontal, 4-7 vertical
            p2=(round(p[0]+w,2),p[1]) if st<4 else (p[0],round(p[1]+w,2))
            pts.append(p2); names[p2].add('PORT:'+r.get('NAME',''))
        elif t=='29': pts.append(P(r))
    for p in pts: f(p)
    def on(p,a,b):
        (x,y),(x1,y1),(x2,y2)=p,a,b
        if x1==x2==x and min(y1,y2)<=y<=max(y1,y2): return True
        if y1==y2==y and min(x1,x2)<=x<=max(x1,x2): return True
        return False
    for p in set(pts):
        for a,b in segs:
            if on(p,a,b): u(p,a)
    nets=collections.defaultdict(lambda:[set(),[]])
    for p in set(pts):
        k=f(p); nets[k][0]|=names.get(p,set()); nets[k][1]+=pinat.get(p,[])
    print('#### ',path.split('/')[-1])
    for i,cp in sorted(comps.items(), key=lambda kv: kv[1]['des']):
        pr=cp['params']; val=pr.get('Comment') or pr.get('Value','')
        extra={k:v for k,v in pr.items() if k in ('Value','Manufacturer Part Number','MPN','Part Number','Supplier Part Number 1','LCSC','Description')}
        print(' %-8s %-28s %-30s %s'%(cp['des'],cp['lib'][:28],val[:30],extra if extra else cp['desc'][:60]))
    print(' -- nets')
    for k,(nm,pins) in sorted(nets.items(), key=lambda kv: sorted(kv[1][0]) or ['~']):
        if len(pins)+len(nm)<2 and not pins: continue
        if not pins and not nm: continue
        print('  [%s] %s'%(','.join(sorted(nm)) or '-', ' '.join(sorted(pins))))
    # sheet symbols
    for r in R:
        if r.get('RECORD') in ('15',): print(' SHEETSYM', r.get('SHEETNAME',''), r.get('FILENAME',''))
        if r.get('RECORD') in ('32','33'): print('  sheettxt',r.get('TEXT',''))
if __name__=="__main__":
    for p in sys.argv[1:]: run(p)
