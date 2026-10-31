import sys; sys.path.insert(0,sys.argv[1])
from sexp import *
S='/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/'
cache={}
def lib(n):
    if n not in cache: cache[n]=parse(open(S+n+'.kicad_sym').read())[0]
    return cache[n]
def sym(l,n):
    for s in find(lib(l),'symbol'):
        if s[1]==n: return s
for ln in sys.argv[2:]:
    l,n=ln.split(':'); s=sym(l,n)
    if s is None: print(ln,'MISSING'); continue
    e=find1(s,'extends')
    base=sym(l,e[1]) if e else s
    print('==',ln,'extends' if e else '', e[1] if e else '')
    for u in find(base,'symbol'):
        for p in find(u,'pin'):
            at=find1(p,'at'); nm=find1(p,'name')[1]; nu=find1(p,'number')[1]; L=find1(p,'length')[1]
            print('  ',u[1],p[1],'num',nu,nm,'at',at[1:],'len',L)
