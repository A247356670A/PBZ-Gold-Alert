"""Reuse the official 1.1 sprite streams at the strong-attack warning entry."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work'),str(ROOT/'work/hash-deps'),str(ROOT/'editor')]
from cityhash import CityHash64
from parse_fx import FXParser
from inspect_fx_vm import scripts
from zen_fx_edit import read_fields
from builder import recolour


def patch(destination):
    source=ROOT/'work/gold-alert-v157/raw/chunks/b21b224afd0ed4a800000001'
    original_post=ROOT/'work/black-alert-investigation/current/NS_AttackAlert_Post_001.uasset'
    plan=json.loads((ROOT/'editor/resources/colour-plan.json').read_text())[source.name]
    recolour(source,destination,plan,{'colour':'#B85CFF','brightness':100})
    q=FXParser(destination);data=bytearray(q.b);exports=q.exports()
    old_name='NS_AttackAlert_Blue_001';new_name='NS_AttackAlert_Post_001'
    renamed=[]
    lengths=76+len(q.names)*8
    string_at=76+len(q.names)*10
    for i,name in enumerate(q.names):
        length=struct.unpack_from('>H',data,lengths+i*2)[0]
        wide=bool(length&0x8000);n=length&0x7fff
        if old_name in name:
            assert not wide
            new=name.replace(old_name,new_name)
            assert len(new.encode())==n
            assert CityHash64(name.lower().encode())==struct.unpack_from('<Q',data,76+i*8)[0]
            data[string_at:string_at+n]=new.encode()
            struct.pack_into('<Q',data,76+i*8,CityHash64(new.lower().encode()))
            renamed.append((name,new))
        string_at+=n*(2 if wide else 1)
    assert len(renamed)==2
    primary=next(e for e in exports if e['name']==old_name)
    target=FXParser(original_post);target_primary=next(e for e in target.exports()if e['name']==new_name)
    export_map=struct.unpack_from('<I',data,32)[0]
    target_map=struct.unpack_from('<I',target.b,32)[0]
    # External references use the target's original public export identity.
    data[export_map+primary['index']*72+56:export_map+primary['index']*72+64]=target.b[target_map+target_primary['index']*72+56:target_map+target_primary['index']*72+64]
    angle_edits=0;size_edits=0
    for e in exports:
        typ='NiagaraSystem'if e==primary else'NiagaraEmitter'if e['name'].startswith('Empty')else None
        if not typ:continue
        q.p=e['start'];q.records=[];q.obj(typ)
        for rec in list(q.records):
            if rec['kind']!='struct' or rec['type']not in ('NiagaraParameterStore','NiagaraUserRedirectionParameterStore'):continue
            value=rec['value'];params=value.get('SortedParameterOffsets')or[]
            if not params:continue
            row=next((r for r in q.records if r['kind']=='value'and r['type']==('Array',('Byte',))and rec['start']<=r['start']<r['end']<=rec['end']and r['value']==value.get('ParameterData')),None)
            if row is None:continue
            payload=row['start']+4
            for param in params:
                name=param['Name']
                if 'PBZ_X_'in name:
                    angle=45.0 if name.endswith('Pos')else -45.0
                    struct.pack_into('<f',data,payload+param['Offset'],angle);angle_edits+=1
                if name.startswith('User.PBZ_YVSize'):
                    hname=name.replace('YVSize','YSize');hparam=next(p for p in params if p['Name']==hname)
                    data[payload+param['Offset']:payload+param['Offset']+8]=q.b[payload+hparam['Offset']:payload+hparam['Offset']+8];size_edits+=1
    assert angle_edits>=24 and size_edits==10
    # The action blueprint already plays ZiGuang. Disable the copied yellow
    # audio emitter so the black warning receives only its dedicated sound.
    q.p=primary['start'];q.records=[];system=q.obj('NiagaraSystem')
    handle=next(r for r in q.records if r['kind']=='struct'and isinstance(r['value'],dict)and r['value'].get('Name')=='Audio'and'VersionedInstance'in r['value'])
    q.p=handle['start'];fields=read_fields(q,handle['type']);enabled=next(f for f in fields.values()if f['name']=='bIsEnabled')
    assert enabled['value']==1 and enabled['end']-enabled['start']==1
    data[enabled['start']]=0
    destination.write_bytes(data)
    check=FXParser(destination);check.p=primary['start'];system=check.obj('NiagaraSystem')
    assert next(h for h in system['EmitterHandles']if h['Name']=='Audio')['bIsEnabled']is None or next(h for h in system['EmitterHandles']if h['Name']=='Audio')['bIsEnabled']==0
    identities=[(e['outer'],e['name'],e['number'])for e in check.exports()]
    assert len(identities)==len(set(identities))
    for e in check.exports():
        if e['name']=='NiagaraSpriteRendererProperties':
            check.p=e['start'];v=check.obj(e['name'])
            assert v['SpriteRotationBinding']['RootName']in ('User.PBZ_X_Pos','User.PBZ_X_Neg')
    for a,b in zip(scripts(source),scripts(destination),strict=True):
        av,bv=a[3],b[3];av['CachedScriptVM'].pop('ScriptLiterals',None);bv['CachedScriptVM'].pop('ScriptLiterals',None);assert av==bv
    return {'base':'official v1.1 / development v1.5.7','target':'NS_AttackAlert_Post_001',
            'cross_angles_degrees':[45,-45],'colour_srgb':'#B85CFF','angle_parameter_edits':angle_edits,
            'equal_diagonal_sizes':True,'copied_yellow_sound_emitter_disabled':True,
            'target_public_export_hash_preserved':True,'all_vm_programs_and_experimental_contexts_preserved':True,
            'unique_object_identities':True,'renamed_package_names':renamed,
            'sha256':hashlib.sha256(data).hexdigest(),'in_game_tested':False}


if __name__=='__main__':
    out=ROOT/'work/gold-alert-v160'
    out.mkdir(exist_ok=True)
    report=patch(out/'purple-post.uasset')
    (out/'visual-validation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
