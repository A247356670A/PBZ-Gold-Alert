"""Append exactly one sentence to the native simplified-Chinese weapon description."""
import struct,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'work/investigate-v202'
REL='ProjectPBZ/Content/Localization/Game/zh-Hans/Game.locres'
SENTENCE='跟...根本没有这样的拳套!'

def strings(b):
    assert b[:16].hex()=='0e147475674a03fc4a15909dc3377f1b' and b[16]==3
    start=struct.unpack_from('<q',b,17)[0];p=start
    count=struct.unpack_from('<I',b,p)[0];p+=4;rows=[]
    for i in range(count):
        length_at=p;n=struct.unpack_from('<i',b,p)[0];p+=4;assert abs(n)<100000
        size=abs(n)*(2 if n<0 else 1);payload=b[p:p+size];p+=size
        value=payload.decode('utf-16-le'if n<0 else'utf8').rstrip('\0')
        refs=struct.unpack_from('<i',b,p)[0];p+=4
        rows.append(dict(index=i,start=length_at,end=p-4,value=value,refs=refs,wide=n<0))
    assert p==len(b),(p,len(b),count)
    return start,rows

def patch(destination):
    original=(B/'pak'/REL).read_bytes();start,rows=strings(original)
    target,=[r for r in rows if r['value'].startswith('沉重而朴实的钢铁拳套，钉刺与铁面已磨得发亮。')]
    assert target['value'].endswith('使得每次攻击更加强大。')
    assert target['wide'] and SENTENCE not in target['value']
    text=target['value']+'\n'+SENTENCE;payload=(text+'\0').encode('utf-16-le')
    replacement=struct.pack('<i',-len(payload)//2)+payload
    changed=original[:target['start']]+replacement+original[target['end']:]
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(changed)
    after_start,after=strings(changed);assert after_start==start and len(after)==len(rows)
    for a,b in zip(rows,after,strict=True):
        assert a['refs']==b['refs']
        if a['index']==target['index']:assert b['value']==text
        else:assert a['value']==b['value']
    assert original[:start]==changed[:start]
    proof=dict(path=REL,sentence=SENTENCE,original_description=target['value'],new_description=text,
        localized_string_index=target['index'],reference_count=target['refs'],string_count=len(rows),
        native_namespace_keys_source_hashes_and_string_indices_bit_exact=True,
        all_other_localized_strings_unchanged=True,original_highlight_tags_preserved=True)
    (ROOT/'work/gold-alert-v202/description-proof.json').write_text(json.dumps(proof,indent=2,ensure_ascii=False),encoding='utf8')
    return proof

if __name__=='__main__':
    proof=patch(ROOT/'work/gold-alert-v202/pak-root'/REL)
    print(json.dumps(proof,ensure_ascii=True))
