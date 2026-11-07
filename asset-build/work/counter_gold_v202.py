"""Tint only this counter system's renderer material instances, including GPU effects."""
import sys,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from fx_parser_v202 import FX202
from zen_fx_edit import append_names,rebuild_exports,read_fields,encode_fields,raw_field,object_bytes
B=ROOT/'work/investigate-v202'
TINT=(1.08,.86,.50)

def patch(destination):
    source=B/'NS_Hun_ShaChiWeaponQuanTao_Couter_401.uasset'
    original=FX202(source);chain=json.loads((B/'counter-material-chain.json').read_text())
    mats={r['pid']:r for r in chain['materials']}
    # Match native FNames exactly: Main_Color_1 is base Main_Color + number 2,
    # not a newly interned literal Main_Color_1 with number 0.
    required=['Main_Color','Color']
    header,delta,names=append_names(original,[n for n in required if n not in original.names])
    indices={n:i for i,n in enumerate(original.names)};indices.update(names)
    replacements={};edits=[]
    for row in chain['renderers']:
        idx=row['export'];pid,=row['pids'];mat=mats[pid]
        if mat['type']=='Material':
            # The Modulate emitter darkens/distorts the scene; it is not a white emission layer.
            assert idx==50 and mat['path'].endswith('/M_FX_Modulate.uasset');continue
        params={};cursor=pid
        while cursor:
            m=mats[cursor]
            for p in m.get('properties',{}).get('VectorParameterValues',[]):
                params.setdefault(p['ParameterInfo']['Name'],p['ParameterValue']or[0.,0.,0.,0.])
            cursor=m.get('parent_pid')
        # The blend-master palette uses these three documented/cooked names.
        if any(mats[x]['path'].endswith('/M_FX_BlendMaster_001.uasset') for x in ancestors(pid,mats)):
            assert idx in [49,51,53]
            # Main_Color_1/2 are also explicit on sibling instances of this same master.
            params.setdefault('Main_Color_0',[0.,0.,0.,0.])
            params.setdefault('Main_Color_1',[.5,.5,.5,.5])
            params.setdefault('Main_Color_2',[1.,1.,1.,1.])
        colors={n:v for n,v in params.items()if n in ['Main_Color_0','Main_Color_1','Main_Color_2','Color'] and any(v[:3])}
        assert colors,(idx,mat['path'])
        original.p=original.exports()[idx]['start'];fields=read_fields(original,row['type']);end=original.p
        field_idx,= [i for i,n,t in original.schema(row['type'])if n=='MaterialParameters']
        if field_idx in fields and not fields[field_idx].get('zero'):
            original.p=fields[field_idx]['start'];mf=read_fields(original,'NiagaraRendererMaterialParameters')
        else:mf={}
        existing=mf.get(2,{}).get('data',struct.pack('<I',0));count=struct.unpack_from('<I',existing)[0]
        newvectors=[];updated={}
        for name,old in colors.items():
            new=tuple(float(old[i])*TINT[i] for i in range(3))+(float(old[3]),)
            base,number=('Main_Color',int(name.rsplit('_',1)[1])+1) if name.startswith('Main_Color_') else(name,0)
            newvectors.append(object_bytes({0:struct.pack('<II',indices[base],number),1:struct.pack('<ffff',*new)}))
            updated[name]=dict(before=old,after=new)
        mf[2]=raw_field(struct.pack('<I',count+len(newvectors))+existing[4:]+b''.join(newvectors))
        fields[field_idx]=raw_field(encode_fields(mf))
        e=original.exports()[idx];replacements[idx]=encode_fields(fields)+original.b[end:e['start']+e['size']]
        edits.append(dict(renderer=idx,type=row['type'],material=mat['path'],colors=updated,
            previous_vector_overrides_preserved=count,alpha_values_preserved=True))
    assert set(replacements)=={31,32,49,51,52,53}
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(rebuild_exports(original,header,delta,replacements))
    after=FX202(destination)
    for a,b in zip(original.exports(),after.exports(),strict=True):
        if a['index']not in replacements:assert original.b[a['start']:a['start']+a['size']]==after.b[b['start']:b['start']+b['size']]
    for row in edits:
        after.p=after.exports()[row['renderer']]['start'];props=after.obj(row['type'])
        values={v['MaterialParameterName']:v['Value']for v in props['MaterialParameters']['VectorParameters']}
        for n,v in row['colors'].items():
            assert all(abs(a-b)<1e-6 for a,b in zip(values[n],v['after']))
        encoded_names=[r for r in after.records if r['kind']=='value'and r['type']==('Name',)and r.get('parent')=='NiagaraRendererMaterialVectorParameter']
        for rec in encoded_names:
            if rec['value'] not in row['colors']:continue
            ni,nn=struct.unpack_from('<II',after.b,rec['start'])
            if rec['value'].startswith('Main_Color_'):
                assert after.names[ni]=='Main_Color' and nn==int(rec['value'].rsplit('_',1)[1])+1
            else:assert after.names[ni]=='Color' and nn==0
        # Every non-material parameter property remains exactly as the original renderer.
        prior=next(r for r in chain['renderers']if r['export']==row['renderer'])['properties']
        assert json.loads(json.dumps({k:v for k,v in props.items()if k!='MaterialParameters'}))=={k:v for k,v in prior.items()if k!='MaterialParameters'}
        original.p=original.exports()[row['renderer']]['start'];old_fields=read_fields(original,row['type'])
        after.p=after.exports()[row['renderer']]['start'];new_fields=read_fields(after,row['type'])
        material_index=next(i for i,n,t in original.schema(row['type'])if n=='MaterialParameters')
        for index,value in old_fields.items():
            if index!=material_index:assert value['data']==new_fields[index]['data'] and value['zero']==new_fields[index]['zero']
    return dict(source=str(source),cid='aa16994f9470996900000001',rgb_multiplier=TINT,
        renderer_overrides=edits,all_other_49_exports_bit_exact=True,
        all_gpu_compute_shaders_cpu_vm_particle_times_and_sizes_unchanged=True,
        no_shared_material_assets_changed=True,non_emissive_modulate_renderer_unchanged=True,
        native_material_parameter_fname_base_and_number_verified=True,
        scope='GA_TieKuangQuanTao_GuardPoint Couter action export56 references Couter_401',
        in_game_visual_confirmation_pending=True)

def ancestors(pid,mats):
    while pid:
        yield pid;pid=mats[pid].get('parent_pid')

if __name__=='__main__':
    out=ROOT/'work/gold-alert-v202/NS_Hun_ShaChiWeaponQuanTao_Couter_401.uasset'
    proof=patch(out);(out.parent/'counter-gold-proof.json').write_text(json.dumps(proof,indent=2),encoding='utf8')
    print(json.dumps(dict(changed_renderers=len(proof['renderer_overrides']),tint=TINT,file=str(out))))
