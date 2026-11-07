"""Pale-gold renderer overrides for the actual Couter timeline follow-up systems."""
import sys,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from fx_parser_v202 import FX202
from zen_fx_edit import append_names,rebuild_exports,read_fields,encode_fields,raw_field,object_bytes
from counter_gold_v202 import TINT,ancestors

def patch_all(raw):
    chain=json.loads((ROOT/'work/investigate-v203/followup-material-chain.json').read_text())
    mats={m['pid']:m for m in chain['materials']};results=[]
    for asset in chain['assets']:
        if not asset['renderers']:continue
        q=FX202(Path(asset['file']));planned=[];skipped=[]
        for row in asset['renderers']:
            pid,=row['pids'];params={}
            for cur in ancestors(pid,mats):
                for p in mats[cur].get('properties',{}).get('VectorParameterValues',[]):
                    params.setdefault(p['ParameterInfo']['Name'],p['ParameterValue']or[0.,0.,0.,0.])
            root=mats[list(ancestors(pid,mats))[-1]]['path']
            if Path(root).stem in ['M_FX_BlendMaster_001','M_FX_AddMaster_001']:
                params.setdefault('Main_Color_0',[0.,0.,0.,0.])
                params.setdefault('Main_Color_1',[.5,.5,.5,.5])
                params.setdefault('Main_Color_2',[1.,1.,1.,1.])
                names=['Main_Color_0','Main_Color_1','Main_Color_2']
            elif Path(root).stem=='M_FX_Refraction_001':names=['Color']
            elif Path(root).stem=='M_FX_PowerUp':names=['EmissiveAndOpcaity']
            else:
                assert Path(root).stem in ['M_FX_Shockwave_Air','M_FX_RadialBlur','M_FX_Modulate'],root
                skipped.append(dict(renderer=row['export'],material=mats[pid]['path'],reason='non-color distortion / radial blur / modulate'));continue
            colors={n:params[n]for n in names if any(params[n][:3])}
            assert colors
            planned.append((row,colors,mats[pid]['path']))
        def fname(n):
            return ('Main_Color',int(n.rsplit('_',1)[1])+1)if n.startswith('Main_Color_')else(n,0)
        required=sorted({fname(n)[0]for _,colors,_ in planned for n in colors})
        header,delta,added=append_names(q,[n for n in required if n not in q.names])
        indices={n:i for i,n in enumerate(q.names)};indices.update(added);replacements={};edits=[]
        for row,colors,material in planned:
            idx=row['export'];e=q.exports()[idx];q.p=e['start'];fields=read_fields(q,row['type']);end=q.p
            fi=next(i for i,n,t in q.schema(row['type'])if n=='MaterialParameters')
            if fi in fields and not fields[fi].get('zero'):
                q.p=fields[fi]['start'];mf=read_fields(q,'NiagaraRendererMaterialParameters')
            else:mf={}
            existing=mf.get(2,{}).get('data',struct.pack('<I',0));count=struct.unpack_from('<I',existing)[0]
            old_vectors={p['MaterialParameterName'] for p in (row['properties'].get('MaterialParameters')or{}).get('VectorParameters',[])}
            assert not old_vectors.intersection(colors)
            vectors=[];updated={}
            for name,old in colors.items():
                new=tuple(float(old[i])*TINT[i]for i in range(3))+(float(old[3]),)
                base,number=fname(name)
                vectors.append(object_bytes({0:struct.pack('<II',indices[base],number),1:struct.pack('<ffff',*new)}))
                updated[name]=dict(before=old,after=new)
            mf[2]=raw_field(struct.pack('<I',count+len(vectors))+existing[4:]+b''.join(vectors))
            fields[fi]=raw_field(encode_fields(mf))
            replacements[idx]=encode_fields(fields)+q.b[end:e['start']+e['size']]
            edits.append(dict(renderer=idx,type=row['type'],material=material,colors=updated,existing_vector_count=count))
        destination=raw/'chunks'/asset['cid'];destination.write_bytes(rebuild_exports(q,header,delta,replacements));after=FX202(destination)
        for a,b in zip(q.exports(),after.exports(),strict=True):
            if a['index']not in replacements:assert q.b[a['start']:a['start']+a['size']]==after.b[b['start']:b['start']+b['size']]
        for edit in edits:
            idx=edit['renderer'];typ=edit['type'];after.p=after.exports()[idx]['start'];props=after.obj(typ)
            old=next(r['properties']for r in asset['renderers']if r['export']==idx)
            assert json.loads(json.dumps({k:v for k,v in props.items()if k!='MaterialParameters'}))=={k:v for k,v in old.items()if k!='MaterialParameters'}
            prior_params=old.get('MaterialParameters')or{};new_params=props['MaterialParameters']
            for key,value in prior_params.items():
                if key!='VectorParameters':assert json.loads(json.dumps(new_params[key]))==value
            assert json.loads(json.dumps(new_params['VectorParameters'][:edit['existing_vector_count']]))==prior_params.get('VectorParameters',[])
            values={p['MaterialParameterName']:p['Value']for p in new_params['VectorParameters']}
            for n,v in edit['colors'].items():assert all(abs(a-b)<1e-6 for a,b in zip(values[n],v['after']))
            q.p=q.exports()[idx]['start'];of=read_fields(q,typ);after.p=after.exports()[idx]['start'];nf=read_fields(after,typ)
            fi=next(i for i,n,t in q.schema(typ)if n=='MaterialParameters')
            for key,v in of.items():
                if key!=fi:assert v['data']==nf[key]['data']and v['zero']==nf[key]['zero']
        results.append(dict(cid=asset['cid'],path=asset['path'],edits=edits,skipped=skipped,
            all_other_exports_bit_exact=True,all_non_color_properties_and_original_overrides_preserved=True,
            cpu_vm_gpu_shader_lifetime_size_and_timing_bit_exact=True,shared_materials_unmodified=True))
    assert len(results)==4
    return dict(rgb_multiplier=TINT,assets=results,changed_renderers=sum(len(a['edits'])for a in results),
        source='GuardPoint Couter actions65/64/66/53: PowerUp_202 / Wind_201 / Attack_202 / Trail_201',in_game_confirmation_pending=True)
