"""Keep original darkening Niagara intact and add a child purple-X component renderer."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work'),str(ROOT/'work/hash-deps')]
from cityhash import CityHash64
from parse_fx import FXParser
from zen_fx_edit import append_names,read_fields,encode_fields,raw_field,object_bytes,rebuild_exports
from inspect_fx_vm import scripts

MASK=(1<<64)-1
POST_CID='7dc2590713fc314d00000001'
PURPLE_PATH='/PBZVFXPack/VFX/BattleFX/Common/NS_AttackAlert_Purp_001'
PURPLE_PID=CityHash64(PURPLE_PATH.lower().encode('utf-16-le'))
PURPLE_CID=struct.pack('<Q',PURPLE_PID).hex()+'00000001'
NIAGARA_CLASS=8778708291182891316
NIAGARA_CDO=5777982925424473344


def sha(b):return hashlib.sha256(b).hexdigest()


def name_batch(names,version):
    encoded=[n.encode('ascii')for n in names]
    return (struct.pack('<IIQ',len(names),sum(map(len,encoded)),version)
            +b''.join(struct.pack('<Q',CityHash64(n.lower().encode('ascii')))for n in names)
            +b''.join(struct.pack('>H',len(n))for n in encoded)+b''.join(encoded))


def read_name_batch(b,at):
    n,size,version=struct.unpack_from('<IIQ',b,at)
    pos=at+16+10*n
    names=[]
    for i in range(n):
        length=struct.unpack_from('>H',b,at+16+8*n+2*i)[0]
        assert not length&0x8000
        name=b[pos:pos+length].decode('ascii');pos+=length;names.append(name)
        assert struct.unpack_from('<Q',b,at+16+i*8)[0]==CityHash64(name.lower().encode('ascii'))
    assert pos==at+16+10*n+size
    return names,version,pos


def purple_child(destination):
    source=ROOT/'work/gold-alert-v160/purple-post.uasset'
    q=FXParser(source);b=bytearray(q.b)
    old='NS_AttackAlert_Post_001';new='NS_AttackAlert_Purp_001'
    pos=76+10*len(q.names)
    edits=0
    for i,name in enumerate(q.names):
        size=struct.unpack_from('>H',b,76+8*len(q.names)+2*i)[0]
        assert not size&0x8000
        if old in name:
            replacement=name.replace(old,new)
            assert len(replacement)==size
            b[pos:pos+size]=replacement.encode('ascii')
            struct.pack_into('<Q',b,76+8*i,CityHash64(replacement.lower().encode('ascii')))
            edits+=1
        pos+=size
    assert edits==2
    primary=next(e for e in q.exports()if e['name']==old)
    public_hash=CityHash64(new.lower().encode('utf-16-le'))
    struct.pack_into('<Q',b,struct.unpack_from('<I',b,32)[0]+primary['index']*72+56,public_hash)
    destination.write_bytes(b)
    c=FXParser(destination)
    assert c.names[struct.unpack_from('<I',b,8)[0]&0x3fffffff]==PURPLE_PATH
    for a,z in zip(q.exports(),c.exports(),strict=True):
        assert q.b[a['start']:a['start']+a['size']]==c.b[z['start']:z['start']+z['size']]
    return public_hash


def patch(build):
    build.mkdir(parents=True,exist_ok=True)
    public_hash=purple_child(build/'purple-child.uasset')
    original=ROOT/'work/black-alert-investigation/current/NS_AttackAlert_Post_001.uasset'
    q=FXParser(original)
    header,delta,names=append_names(q,['PBZ_PurpleFX_Component','PBZ_PurpleFX_Renderer'])
    # Add the new renderer to the original PP emitter, preserving all VM and curve data.
    host=q.exports()[12]
    q.p=host['start'];q.obj('NiagaraEmitter')
    version=next(r for r in q.records if r['kind']=='struct'and r['type']=='VersionedNiagaraEmitterData')
    q.p=version['start'];vf=read_fields(q,'VersionedNiagaraEmitterData')
    key=next(i for i,f in vf.items()if f['name']=='RendererProperties')
    assert vf[key]['value']==[2]
    vf[key]=raw_field(struct.pack('<Iii',2,2,26))
    host_payload=q.b[host['start']:version['start']]+encode_fields(vf)+q.b[version['end']:host['start']+host['size']]
    stage=rebuild_exports(q,header,delta,{12:host_payload})
    stage_path=build/'post-names-stage.uasset';stage_path.write_bytes(stage)
    s=FXParser(stage_path);b=s.b
    off={i:struct.unpack_from('<I',b,i)[0]for i in (4,24,28,32,36,40,44,48,52,56)}
    assert off[52]==off[56]==off[36] and (off[52]-off[32])//72==24
    hashes=list(struct.unpack('<'+'Q'*((off[28]-off[24])//8),b[off[24]:off[28]]))
    hash_index=len(hashes);hashes.append(public_hash)
    imports=list(struct.unpack('<'+'Q'*((off[32]-off[28])//8),b[off[28]:off[32]]))
    class_import=len(imports);imports.append(NIAGARA_CLASS)
    cdo_import=len(imports);imports.append(NIAGARA_CDO)
    asset_import=len(imports);imports.append(0x8000000300000000|hash_index)
    package_names,version,end=read_name_batch(b,off[48])
    assert len(package_names)==3 and end+12==off[4]
    numbers=b[end:off[4]]+struct.pack('<I',0)
    package_names.append(PURPLE_PATH)
    imported_names=name_batch(package_names,version)+numbers

    # Reuse only the original renderer's location binding; PP bindings stay on its renderer.
    renderer=q.exports()[1];q.p=renderer['start'];original_renderer=q.obj('NiagaraComponentRendererProperties')
    binding=next(r for r in q.records if r['kind']=='struct'and r['type']=='NiagaraComponentPropertyBinding'
                 and r['value'].get('PropertyName')=='RelativeLocation')
    q.p=renderer['start'];rf=read_fields(q,'NiagaraComponentRendererProperties')
    def field_index(key):return next(i for i,k,t in q.schema('NiagaraComponentRendererProperties')if k==key)
    rf[field_index('ComponentType')]=raw_field(struct.pack('<i',-class_import-1))
    rf[field_index('TemplateComponent')]=raw_field(struct.pack('<i',25))
    rf[field_index('PropertyBindings')]=raw_field(struct.pack('<I',1)+q.b[binding['start']:binding['end']])
    rf[field_index('bCreateComponentFirstParticleFrame')]=raw_field(b'\x01')
    rf[field_index('bOnlyActivateNewlyAquiredComponents')]=raw_field(b'\x01')
    renderer_payload=encode_fields(rf)+q.b[q.p:renderer['start']+renderer['size']]
    component_fields={'Asset':struct.pack('<i',-asset_import-1), 'bAutoActivate':b'\x01',
                      'bAutoDestroy':b'\x01', 'bAutoManageAttachment':b'\0',
                      'bAllowScalability':b'\0','bVisible':b'\x01','bHiddenInGame':b'\0'}
    component_payload=object_bytes({i:component_fields[k]for i,k,t in q.schema('NiagaraComponent')if k in component_fields})+b'\0'*4

    exports=s.exports()
    payload=bytearray(b[off[4]:])
    added=[]
    for label,data,template,outer,cls,cdo in [
        ('PBZ_PurpleFX_Component',component_payload,0,25,NIAGARA_CLASS,NIAGARA_CDO),
        ('PBZ_PurpleFX_Renderer',renderer_payload,1,12,renderer['class'],struct.unpack_from('<Q',q.b,struct.unpack_from('<I',q.b,32)[0]+72+48)[0])]:
        entry=bytearray(b[off[32]+template*72:off[32]+(template+1)*72])
        struct.pack_into('<QQIIQQQQQ',entry,0,len(payload),len(data),names[label],0,outer,cls,MASK,cdo,0)
        added.append(bytes(entry));payload.extend(data)

    # Preserve every existing dependency edge and append explicit child dependencies.
    entries=list(v[0]for v in struct.iter_unpack('<i',b[off[44]:off[48]]))
    deps=[]
    for i in range(24):
        first,*counts=struct.unpack_from('<i4I',b,off[40]+20*i);groups=[]
        for count in counts:groups.append(entries[first:first+count]);first+=count
        deps.append(groups)
    deps[12][2].append(26)
    deps.extend([[[26],[-cdo_import-1],[-asset_import-1],[]],
                 [[13],[],[-class_import-1,25],[]]])
    depheaders=bytearray();depentries=[]
    for groups in deps:
        depheaders.extend(struct.pack('<i4I',len(depentries),*map(len,groups)))
        for group in groups:depentries.extend(group)
    bundles=list(struct.iter_unpack('<II',b[off[36]:off[40]]))
    first_serialize=next(i for i,row in enumerate(bundles)if row[1]==1)
    bundles[first_serialize:first_serialize]=[(25,0),(24,0),(24,1),(25,1)]
    assert len(bundles)==52 and len(set(bundles))==52
    result=bytearray(b[:off[24]])
    starts={24:len(result)};result.extend(struct.pack('<'+'Q'*len(hashes),*hashes))
    starts[28]=len(result);result.extend(struct.pack('<'+'Q'*len(imports),*imports))
    starts[32]=len(result);result.extend(b[off[32]:off[52]]+b''.join(added))
    starts[52]=starts[56]=starts[36]=len(result)
    result.extend(b''.join(struct.pack('<II',*row)for row in bundles))
    starts[40]=len(result);result.extend(depheaders)
    starts[44]=len(result);result.extend(struct.pack('<'+'i'*len(depentries),*depentries))
    starts[48]=len(result);result.extend(imported_names)
    starts[4]=len(result)
    for field,at in starts.items():struct.pack_into('<I',result,field,at)
    result.extend(payload)
    destination=build/'post-with-blackout.uasset';destination.write_bytes(result)
    c=FXParser(destination);ce=c.exports()
    assert len(ce)==26 and len({(e['outer'],e['name'],e['number'])for e in ce})==26
    for i,old in enumerate(q.exports()):
        if i!=12:assert q.b[old['start']:old['start']+old['size']]==c.b[ce[i]['start']:ce[i]['start']+ce[i]['size']],old['name']
    for i,typ in [(24,'NiagaraComponent'),(25,'NiagaraComponentRendererProperties'),(12,'NiagaraEmitter')]:
        c.p=ce[i]['start'];v=c.obj(typ);assert c.p+4==ce[i]['start']+ce[i]['size'],(i,c.p,ce[i])
        if i==24:assert v['Asset']==-asset_import-1 and v['bAutoActivate']==1
        if i==25:assert v['TemplateComponent']==25 and len(v['PropertyBindings'])==1
        if i==12:assert v['VersionData'][0]['RendererProperties']==[2,26]
    # Native post scripts, exposed parameter stores and all original PP curves are exact.
    for a,z in zip(scripts(original),scripts(destination),strict=True):assert a[3]==z[3]
    return {'post_cid':POST_CID,'purple_cid':PURPLE_CID,'purple_pid':PURPLE_PID,
            'purple_path':PURPLE_PATH,'purple_public_hash':public_hash,
            'original_imported_package_count':3,'new_imported_package_count':4,
            'original_post_system_all_scripts_curves_and_parameters_bit_exact':True,
            'original_post_component_renderer_and_template_bit_exact':True,
            'original_emitter_only_additional_renderer_reference':True,
            'purple_spawned_as_child_niagara_component':True,'purple_child_export_payloads_bit_exact_v160':True,
            'post_sha256':sha(result),'in_game_tested':False}


if __name__=='__main__':
    build=ROOT/'work/gold-alert-v162'
    result=patch(build)
    (build/'visual-validation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
