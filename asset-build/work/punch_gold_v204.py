"""Fix the missed emissive wave and scope the on-contact gold burst to the gauntlet."""
import sys,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work'),str(ROOT/'work/hash-deps')]
from cityhash import CityHash64
from fx_parser_v202 import FX202
from zen_fx_edit import append_names,rebuild_exports,read_fields,encode_fields,raw_field,object_bytes
from restore_black_post_v162 import read_name_batch
from read_pbz import Reader
from build_yellow_alert_v011 import store_table
from counter_gold_v202 import TINT,ancestors
B=ROOT/'work/investigate-v204'
ATTACK='3dde1ed4bacb125700000001'
HIT='6cf592a880e72a0900000001'
OLD_BASE='NS_FistAddict_HuShock';NEW_BASE='NS_PBZCounter_GdShock'
OLD_PATH='/PBZVFXPack/VFX/BattleFX/FistAddict/'+OLD_BASE+'_201'
NEW_PATH='/PBZVFXPack/VFX/BattleFX/FistAddict/'+NEW_BASE+'_201'
NEW_PID=CityHash64(NEW_PATH.lower().encode('utf-16-le'))
NEW_CID=struct.pack('<Q',NEW_PID).hex()+'00000001'

def cached_colors(file):
    q=FX202(Path(file));q.p=q.exports()[0]['start'];q.obj('Material')
    assert q.take('II')==(0,1) # UObject GUID flag, saved cached-expression flag
    start=q.p;q.records=[];cached=q.obj('MaterialCachedExpressionData')
    # RuntimeEntries is a static array in the usmap. The general object reader
    # returns the last repeated key; raw indexed fields retain every entry.
    q.p=start;fields=read_fields(q,'MaterialCachedExpressionData')
    names=[p['Name']for p in fields[1]['value']['ParameterInfoSet']]
    vectors=dict(zip(names,cached['VectorValues'],strict=True))
    return dict(file=str(file),vector_parameters=vectors,scalar_count=len(cached['ScalarValues']))

def tint(source,destination,planned):
    q=FX202(source)
    def fn(n):return ('Main_Color',int(n.rsplit('_',1)[1])+1)if n.startswith('Main_Color_')else(n,0)
    needed=sorted({fn(n)[0]for _,colors in planned for n in colors})
    header,delta,added=append_names(q,[n for n in needed if n not in q.names]);indices={n:i for i,n in enumerate(q.names)};indices.update(added)
    replacements={};edits=[]
    for row,colors in planned:
        idx=row['export'];e=q.exports()[idx];typ=row['type'];q.p=e['start'];fields=read_fields(q,typ);end=q.p
        fi=next(i for i,n,t in q.schema(typ)if n=='MaterialParameters')
        if fi in fields and not fields[fi].get('zero'):
            q.p=fields[fi]['start'];mf=read_fields(q,'NiagaraRendererMaterialParameters')
        else:mf={}
        existing=mf.get(2,{}).get('data',struct.pack('<I',0));count=struct.unpack_from('<I',existing)[0]
        original_props=row['properties'];old_params=original_props.get('MaterialParameters')or{}
        assert not {p['MaterialParameterName']for p in old_params.get('VectorParameters',[])}.intersection(colors)
        vectors=[];updated={}
        for name,old in colors.items():
            new=tuple(float(old[i])*TINT[i]for i in range(3))+(float(old[3]),)
            base,number=fn(name);vectors.append(object_bytes({0:struct.pack('<II',indices[base],number),1:struct.pack('<ffff',*new)}))
            updated[name]=dict(before=old,after=new)
        mf[2]=raw_field(struct.pack('<I',count+len(vectors))+existing[4:]+b''.join(vectors));fields[fi]=raw_field(encode_fields(mf))
        replacements[idx]=encode_fields(fields)+q.b[end:e['start']+e['size']]
        edits.append(dict(renderer=idx,type=typ,colors=updated,previous_vector_count=count))
    destination.write_bytes(rebuild_exports(q,header,delta,replacements));after=FX202(destination)
    for a,b in zip(q.exports(),after.exports(),strict=True):
        if a['index']not in replacements:assert q.b[a['start']:a['start']+a['size']]==after.b[b['start']:b['start']+b['size']]
    for edit in edits:
        idx=edit['renderer'];typ=edit['type'];after.p=after.exports()[idx]['start'];props=after.obj(typ)
        row=next(r for r,c in planned if r['export']==idx);old=row['properties']
        assert json.loads(json.dumps({k:v for k,v in props.items()if k!='MaterialParameters'}))=={k:v for k,v in old.items()if k!='MaterialParameters'}
        newp=props['MaterialParameters'];oldp=old.get('MaterialParameters')or{}
        for name,value in oldp.items():
            if name!='VectorParameters':assert json.loads(json.dumps(newp[name]))==value
        assert json.loads(json.dumps(newp['VectorParameters'][:edit['previous_vector_count']]))==oldp.get('VectorParameters',[])
        values={p['MaterialParameterName']:p['Value']for p in newp['VectorParameters']}
        for n,v in edit['colors'].items():assert all(abs(a-b)<1e-5 for a,b in zip(values[n],v['after']))
        q.p=q.exports()[idx]['start'];of=read_fields(q,typ);after.p=after.exports()[idx]['start'];nf=read_fields(after,typ)
        fi=next(i for i,n,t in q.schema(typ)if n=='MaterialParameters')
        for i,v in of.items():
            if i!=fi:assert v['data']==nf[i]['data']and v['zero']==nf[i]['zero']
    return dict(edits=edits,all_other_exports_bit_exact=True,all_non_material_properties_and_existing_overrides_preserved=True,
                gpu_shaders_cpu_vm_lifetime_geometry_alpha_timing_unchanged=True)

def rename_batch_in_place(data,at):
    names,version,end=read_name_batch(data,at);p=at+16+10*len(names);changed=0
    for i,name in enumerate(names):
        new=name.replace(OLD_BASE,NEW_BASE);assert len(new)==len(name)
        if new!=name:
            data[p:p+len(name)]=new.encode('ascii');struct.pack_into('<Q',data,at+16+8*i,CityHash64(new.lower().encode('ascii')));changed+=1
        p+=len(name)
    assert p==end
    return changed

def scoped_clone(source,destination):
    q=FX202(source);data=bytearray(q.b);assert rename_batch_in_place(data,60)==2
    main=next(e for e in q.exports()if e['name']==OLD_BASE);assert main['number']==202
    at=struct.unpack_from('<I',data,32)[0]+main['index']*72+56
    old_hash=CityHash64((OLD_BASE+'_201').lower().encode('utf-16-le'));new_hash=CityHash64((NEW_BASE+'_201').lower().encode('utf-16-le'))
    assert struct.unpack_from('<Q',data,at)[0]==old_hash;struct.pack_into('<Q',data,at,new_hash)
    destination.write_bytes(data);after=FX202(destination)
    assert after.names[struct.unpack_from('<I',data,8)[0]&0x3fffffff]==NEW_PATH.rsplit('_201',1)[0]
    assert struct.unpack_from('<I',data,12)[0]==202
    for a,b in zip(q.exports(),after.exports(),strict=True):assert q.b[a['start']:a['start']+a['size']]==after.b[b['start']:b['start']+b['size']]
    return old_hash,new_hash

def patch(prior,raw,build):
    chain=json.loads((B/'followup-material-chain.json').read_text());mats={m['pid']:m for m in chain['materials']}
    defaults={m['pid']:cached_colors(m['file'])for m in mats.values()if m['type']=='Material'}
    (build/'material-defaults.json').write_text(json.dumps(list(defaults.values()),indent=2))
    wave=next(a for a in chain['assets']if a['cid']==ATTACK);wr=next(r for r in wave['renderers']if r['export']==34)
    pid,=wr['pids'];root=list(ancestors(pid,mats))[-1];emissive=defaults[root]['vector_parameters']['Emissive']
    assert emissive==(10.,10.,10.,1.)or emissive==[10.,10.,10.,1.]
    # Read current renderer fields from V203 so previous gold layers are untouched.
    q=FX202(prior/'chunks'/ATTACK);q.p=q.exports()[34]['start'];wr=dict(wr,properties=json.loads(json.dumps(q.obj(wr['type']))))
    wave_proof=tint(prior/'chunks'/ATTACK,raw/'chunks'/ATTACK,[(wr,{'Emissive':emissive})])
    hit=next(a for a in chain['assets']if a['cid']==HIT);planned=[];skipped=[]
    for row in hit['renderers']:
        pid,=row['pids'];parents=list(ancestors(pid,mats));root=parents[-1];rootname=Path(mats[root]['path']).stem
        if rootname in ['M_FX_RadialBlur','M_FX_Modulate']:skipped.append(row['export']);continue
        params={}
        for cur in parents:
            for p in mats[cur].get('properties',{}).get('VectorParameterValues',[]):params.setdefault(p['ParameterInfo']['Name'],p['ParameterValue']or[0.,0.,0.,0.])
        for name,value in defaults[root]['vector_parameters'].items():params.setdefault(name,value)
        keys=['Main_Color_0','Main_Color_1','Main_Color_2','EdgeColor']if rootname in ['M_FX_BlendMaster_001','M_FX_AddMaster_001','M_FX_ClipMaster_001']else['Color']if rootname=='M_FX_Refraction_001'else[]
        assert keys,(row['export'],rootname)
        colors={name:params[name]for name in keys if name in params and any(params[name][:3])};assert colors
        planned.append((row,colors))
    hit_stage=build/'hit-gold-before-clone.uasset';hit_proof=tint(Path(hit['file']),hit_stage,planned)
    old_hash,new_hash=scoped_clone(hit_stage,raw/'chunks'/NEW_CID)
    # Redirect only the gauntlet counter bullet, leaving the boss's original asset intact.
    reader=Reader();rows=json.loads((ROOT/'analysis/build-20261105/asset-index.json').read_text())
    bullet=next(r for r in rows if r['path'].endswith('/BulletData_TieKuangQuanTao_Counter_01.uasset'))
    cid=reader.toc[144+bullet['index']*12:156+bullet['index']*12].hex();data=reader.read(bullet['index']);source=build/'counter-bullet-original.uasset';source.write_bytes(data);q=FX202(source)
    from investigate_black_timing import prefix_field
    refs=[]
    for i in [0,1]:
        q.p=q.exports()[i]['start'];ref=prefix_field(q,'BP_BulletEvent_Effect_C','Niagara')['value'];assert ref==-10;refs.append(ref)
    native=store_table((ROOT/'work/black-alert-investigation/current/container-header').read_bytes())[0]
    bpid=int.from_bytes(bytes.fromhex(cid)[:8],'little');deps,shaders=native[bpid];deps=bytearray(deps)
    at=struct.unpack_from('<I',data,28)[0]+(-refs[0]-1)*8;g=struct.unpack_from('<Q',data,at)[0];assert g>>62==2
    dep_index=(g&0x3fffffffffffffff)>>32;hash_index=g&0xffffffff
    old_pid=int.from_bytes(bytes.fromhex(HIT)[:8],'little');assert struct.unpack_from('<Q',deps,dep_index*8)[0]==old_pid
    struct.pack_into('<Q',deps,dep_index*8,NEW_PID)
    modified=bytearray(data);hash_at=struct.unpack_from('<I',data,24)[0]+hash_index*8
    assert struct.unpack_from('<Q',modified,hash_at)[0]==old_hash;struct.pack_into('<Q',modified,hash_at,new_hash)
    assert rename_batch_in_place(modified,struct.unpack_from('<I',data,48)[0])==1
    (raw/'chunks'/cid).write_bytes(modified);check=FX202(raw/'chunks'/cid)
    for a,b in zip(q.exports(),check.exports(),strict=True):assert data[a['start']:a['start']+a['size']]==check.b[b['start']:b['start']+b['size']]
    assert len(modified)==len(data) and data[struct.unpack_from('<I',data,4)[0]:]==modified[struct.unpack_from('<I',data,4)[0]:]
    assert old_pid not in [x[0]for x in struct.iter_unpack('<Q',native[old_pid][0])]
    return dict(wave=wave_proof,hit=hit_proof,non_color_hit_layers_unchanged=skipped,clone_cid=NEW_CID,clone_path='ProjectPBZ/Plugins/PBZVFXPack/Content/VFX/BattleFX/FistAddict/'+NEW_BASE+'_201.uasset',
        clone_template_cid=HIT,bullet_cid=cid,bullet_path=bullet['path'],bullet_store=(bytes(deps),shaders),
        bullet_native_exports_and_damage_timing_payload_bit_exact=True,original_boss_hit_asset_unmodified=True,
        clone_export_payload_identical_to_tinted_template=True,old_hit_public_hash=old_hash,new_hit_public_hash=new_hash,
        root_emissive_original=emissive,in_game_confirmation_pending=True)
