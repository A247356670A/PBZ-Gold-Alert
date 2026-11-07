"""Read-only targeted UE5 Kismet decoder, checked against CUE4Parse structures.

Inputs are extracted native Zen exports, not rewritten legacy packages.
"""
import json, re, struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'analysis'))
from parse_fx import FXParser

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
SCRIPT_IDS = {int(v): k for k, v in re.findall(
    r'(?m)^(.+):\n  global_index:    Some\((\d+)\)',
    (ROOT/'analysis/script-objects.txt').read_text(encoding='utf8'))}

class Bytecode:
    def __init__(self, q, b):
        self.q, self.b, self.p, self.mem = q, b, 0, 0
        a, z = struct.unpack_from('<II', q.b, 28)
        self.imports = list(struct.unpack_from('<'+'Q'*((z-a)//8), q.b, a))
        self.exports = q.exports()
    def read(self, fmt):
        n=struct.calcsize('<'+fmt); v=struct.unpack_from('<'+fmt,self.b,self.p)
        self.p+=n; self.mem+=n
        return v[0] if len(v)==1 else v
    def name(self):
        n,extra=self.read('II'); self.mem+=4
        return self.q.names[n&0x3fffffff]+(f'_{extra-1}' if extra else '')
    def ref(self):
        i=self.read('i');self.mem+=4
        if i==0:return 'None'
        if i>0:return self.exports[i-1]['name']
        g=self.imports[-i-1]
        return SCRIPT_IDS.get(g, f'import[{i}]/{g}')
    def ptr(self):
        mem=self.mem;n=self.read('i');assert 0<=n<20,(self.p,n)
        names=[self.name() for _ in range(n)];owner=self.ref();self.mem=mem+8
        return '.'.join(names) + (f'@{owner}' if names else '')
    def array(self,end):
        out=[]
        while self.b[self.p]!=end:out.append(self.expr())
        self.read('B');return out
    def expr(self):
        pos,idx=self.p,self.mem;t=self.read('B');v={}
        if t in (0,1,2,0x48,0x33):v={'var':self.ptr()}
        elif t in (4,0x4e,0x4f,0x51,0x6b,0x6d):v={'expr':self.expr()}
        elif t in (6,0x4c):v={'jump':self.read('I')}
        elif t==7:v={'jump':self.read('I'),'condition':self.expr()}
        elif t==0x0f:v={'property':self.ptr(),'variable':self.expr(),'value':self.expr()}
        elif t in (0x14,0x43,0x44,0x5f,0x60):v={'variable':self.expr(),'value':self.expr()}
        elif t in (0x19,0x1a,0x12):v={'object':self.expr(),'skip':self.read('I'),'pointer':self.ptr(),'expr':self.expr()}
        elif t in (0x1b,0x45):v={'call':self.name(),'args':self.array(0x16)}
        elif t in (0x1c,0x46,0x68):v={'call':self.ref(),'args':self.array(0x16)}
        elif t in (0x1d,0x0c):v={'literal':self.read('i')}
        elif t==0x1e:v={'literal':self.read('f')}
        elif t==0x37:v={'literal':self.read('d')}
        elif t==0x20:v={'object':self.ref()}
        elif t in (0x21,0x4b):v={'name':self.name()}
        elif t in (0x22,0x23):v={'literal':self.read('ddd')}
        elif t in (0x24,0x2c):v={'literal':self.read('B')}
        elif t in (0x25,0x26,0x27,0x28):v={'literal':{0x25:0,0x26:1,0x27:True,0x28:False}[t]}
        elif t in (0x2e,0x52,0x54,0x55):v={'class':self.ref(),'expr':self.expr()}
        elif t==0x2f:v={'struct':self.ref(),'size':self.read('i'),'values':self.array(0x30)}
        elif t==0x38:v={'cast':self.read('B'),'expr':self.expr()}
        elif t==0x42:v={'property':self.ptr(),'expr':self.expr()}
        elif t==0x64:v={'property':self.ptr(),'expr':self.expr()}
        elif t==0x61:v={'name':self.name(),'delegate':self.expr(),'object':self.expr()}
        elif t==0x69:
            n=self.read('H');v={'end':self.read('I'),'index':self.expr(),'cases':[]}
            for _ in range(n):v['cases'].append({'match':self.expr(),'next':self.read('I'),'value':self.expr()})
            v['default']=self.expr()
        elif t==0x65:
            v={'property':self.ptr(),'count':self.read('i'),'values':self.array(0x66)}
        elif t==0x1f:
            end=self.b.index(0,self.p);v={'string':self.b[self.p:end].decode('utf8')}
            self.read(f'{end-self.p+1}s')
        elif t not in (0x0b,0x15,0x16,0x17,0x2a,0x2d,0x4d,0x53,0x5c):
            raise ValueError(f'unhandled {t:02x} at disk {pos}, memory {idx}')
        return {'offset':idx,'disk':pos,'op':f'{t:02x}',**v}

def render(v):
    if 'var' in v:return v['var']
    if 'literal' in v:return repr(v['literal'])
    if 'name' in v and len(v)==4:return repr(v['name'])
    if 'call' in v:return v['call']+'('+', '.join(map(render,v['args']))+')'
    if v['op'] in ('14','0f','5f','60'):return render(v['variable'])+' = '+render(v['value'])
    if v['op']=='07':return f"if not ({render(v['condition'])}): goto {v['jump']:04x}"
    if v['op'] in ('06','4c'):return ('goto ' if v['op']=='06' else 'push ')+f"{v['jump']:04x}"
    if v['op'] in ('19','1a','12'):return render(v['object'])+'.'+render(v['expr'])
    if v['op']=='20':return v['object']
    if v['op']=='2f':return v['struct']+'{'+', '.join(map(render,v['values']))+'}'
    if v['op']=='42':return render(v['expr'])+'.'+v['property']
    if 'expr' in v:return v['op']+'('+render(v['expr'])+')'
    if 'string' in v:return repr(v['string'])
    return str({k:x for k,x in v.items() if k not in ('offset','disk')})

def main():
    q=FXParser(BASE/'assets/GA_TieKuangQuanTao_GuardPoint.uasset')
    results=[]
    for export in q.exports()[:9]:
        b=q.b[export['start']:export['start']+export['size']];candidates=[]
        for p in range(len(b)-20):
            n,s=struct.unpack_from('<II',b,p)
            if n>0 and s>0 and p+8+s==len(b)-12 and b[p+8+s-1]==0x53:candidates.append((p,n,s))
        # Nonempty valid script size is always followed by function flags and eventgraph references.
        p,n,s=candidates[0];decoder=Bytecode(q,b[p+8:p+8+s]);expressions=[]
        result={'function':export['name'],'export':export,'script_header':p,'memory_size':n,'disk_size':s,'expressions':expressions}
        try:
            while decoder.p<s:expressions.append(decoder.expr())
            assert decoder.mem==n,(decoder.mem,n)
        except Exception as e:result['error']=repr(e)
        results.append(result)
        print(export['name'],len(expressions),'memory',decoder.mem,'/',n,result.get('error','OK'))
    (BASE/'guardpoint-bytecode.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    text=[]
    for r in results:
        text.append('\n'+r['function'])
        text.extend(f"{x['offset']:04x}: {render(x)}" for x in r['expressions'])
    (BASE/'guardpoint-bytecode.txt').write_text('\n'.join(text),encoding='utf8')

if __name__=='__main__':main()
