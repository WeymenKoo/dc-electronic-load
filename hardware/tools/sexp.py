import re
def parse(s):
    tok = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+')
    stack=[[]]
    for m in tok.finditer(s):
        t=m.group(0)
        if t=='(':
            stack.append([])
        elif t==')':
            x=stack.pop(); stack[-1].append(x)
        else:
            if t.startswith('"'): t=Str(t[1:-1].replace('\\"','"').replace('\\\\','\\'))
            stack[-1].append(t)
    return stack[0]
class Str(str): pass
def dump(x, ind=0):
    if isinstance(x,list):
        if all(not isinstance(i,list) for i in x):
            return '('+' '.join(q(i) for i in x)+')'
        out='('+' '.join(q(i) for i in x if not isinstance(i,list))
        for i in x:
            if isinstance(i,list): out+='\n'+'\t'*(ind+1)+dump(i,ind+1)
        return out+'\n'+'\t'*ind+')'
    return q(x)
def q(i):
    if isinstance(i,Str): return '"'+i.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')+'"'
    return str(i)
def find(x,key):
    return [i for i in x if isinstance(i,list) and i and i[0]==key]
def find1(x,key):
    r=find(x,key); return r[0] if r else None
