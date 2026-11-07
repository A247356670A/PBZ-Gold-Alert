"""Read-only extraction of selected PBZ IoStore chunks. Never writes game files."""
import argparse, json, pathlib, re, struct, zlib
from Crypto.Cipher import AES

ROOT = pathlib.Path(__file__).resolve().parent
PAKS = pathlib.Path(r'G:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks')

class Reader:
    def __init__(self):
        self.toc = (PAKS/'ProjectPBZ-Windows.utoc').read_bytes()
        self.key = bytes.fromhex((ROOT/'aes-key.txt').read_text().strip())
        self.aes = AES.new(self.key, AES.MODE_ECB)
        self.n = self.u32(24)
        self.blocksize = self.u32(44)
        self.partition_size = struct.unpack_from('<Q',self.toc,88)[0]
        self.blockbase = 144 + self.n*22 + self.u32(84)*4 + self.u32(96)*4
        self.assets = json.loads((ROOT/'asset-index.json').read_text(encoding='utf8'))
        self.by_path = {x['path']:x for x in self.assets}
    def u32(self,o): return struct.unpack_from('<I',self.toc,o)[0]
    def info(self,i):
        p=144+self.n*12+i*10
        return int.from_bytes(self.toc[p:p+5],'big'),int.from_bytes(self.toc[p+5:p+10],'big')
    def read(self,i,start=0,length=None):
        offset,size=self.info(i)
        if length is not None:
            if start<0 or start+length>size: raise ValueError('Requested range outside chunk')
            offset+=start;size=length
        blocks=[]
        for bi in range(offset//self.blocksize,(offset+size+self.blocksize-1)//self.blocksize):
            p=self.blockbase+bi*12
            disk=int.from_bytes(self.toc[p:p+5],'little')
            cs=int.from_bytes(self.toc[p+5:p+8],'little')
            us=int.from_bytes(self.toc[p+8:p+11],'little')
            method=self.toc[p+11]
            partition,fo=divmod(disk,self.partition_size)
            file=PAKS/('ProjectPBZ-Windows'+(f'_s{partition}' if partition else '')+'.ucas')
            with file.open('rb') as f:
                f.seek(fo); data=f.read((cs+15)&~15)
            if len(data)<cs: raise ValueError(f'Short read: {file}, {fo}, {cs}, {len(data)}')
            data=self.aes.decrypt(data)[:cs]
            if method==0: pass
            elif method==1:
                if not hasattr(self,'oodle'):
                    import ctypes
                    dll=ROOT.parent/'tools'/'oo2core_9_win64.dll'
                    self.oodle=ctypes.CDLL(str(dll))
                    self.oodle.OodleLZ_Decompress.restype=ctypes.c_int64
                import ctypes
                out=ctypes.create_string_buffer(us)
                got=self.oodle.OodleLZ_Decompress(data,ctypes.c_int64(cs),out,ctypes.c_int64(us),1,0,0,None,0,None,None,None,0,3)
                if got!=us: raise ValueError(f'Oodle decompression {got} != {us}')
                data=out.raw
            else: raise ValueError(f'Unsupported compression method {method}')
            assert len(data)==us,(i,bi,len(data),us)
            blocks.append(data)
        return b''.join(blocks)[offset%self.blocksize:offset%self.blocksize+size]
    def extract(self,pattern):
        selected=[x for x in self.assets if re.search(pattern,x['path'],re.I)]
        results=[]
        for a in selected:
            try:
                b=self.read(a['index'])
                out=ROOT/'extracted'/a['path'];out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(b)
                names=[s.decode('utf8','replace') for s in re.findall(rb'[A-Za-z_/][A-Za-z0-9_/.:\-]{5,}',b)]
                out.with_suffix(out.suffix+'.strings.txt').write_text('\n'.join(names),encoding='utf8')
                results.append(dict(a,size=len(b),status='ok',names=names))
            except Exception as e: results.append(dict(a,status='error',error=str(e)))
        return results

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('pattern');p.add_argument('--output',default='extraction-results.json');args=p.parse_args()
    r=Reader().extract(args.pattern)
    (ROOT/args.output).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
    for a in r: print(a['status'],a['path'],a.get('error',a.get('size')))
