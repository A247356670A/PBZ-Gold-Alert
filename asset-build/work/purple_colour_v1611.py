"""Keep the original scene blackout, composite the purple warning after it."""
import struct
from pathlib import Path
from parse_fx import FXParser
from zen_fx_edit import read_fields,encode_fields,raw_field,rebuild_exports
from inspect_fx_vm import scripts
from build_gold_alert_v168 import verify_clocks_and_curves,lifetime_record

def resize_recolour(source,destination):
    q=FXParser(source);data=bytearray(q.b);allowed=set();stores=[]
    for index,typ,store_type in [(10,'NiagaraEmitter','NiagaraParameterStore'),
        (11,'NiagaraEmitter','NiagaraParameterStore'),(23,'NiagaraSystem','NiagaraUserRedirectionParameterStore')]:
        q.p=q.exports()[index]['start'];q.records=[];q.obj(typ)
        store=next(r for r in q.records if r['kind']=='struct' and r['type']==store_type)
        value=store['value'];params={p['Name']:p['Offset'] for p in value['SortedParameterOffsets']}
        arr=next(r for r in q.records if r['kind']=='value' and r['type']==('Array',('Byte',))
            and store['start']<=r['start']<r['end']<=store['end'] and r['value']==value['ParameterData'])
        start=arr['start']+4
        size_at=start+params['User.PBZ_PSize'];colour_at=start+params['User.PBZ_PColor']
        assert struct.unpack_from('<ff',data,size_at)==(1500.,225.)
        assert struct.unpack_from('<ffff',data,colour_at)==(10.,6.,24.,1.)
        struct.pack_into('<ff',data,size_at,1200.,180.)
        struct.pack_into('<ffff',data,colour_at,6.,1.,10.,1.)
        allowed.update(range(size_at,size_at+8));allowed.update(range(colour_at,colour_at+16));stores.append(index)
    assert len(data)==len(q.b)
    differences=[i for i,(a,b) in enumerate(zip(q.b,data)) if a!=b]
    assert set(differences)<=allowed
    destination.write_bytes(data)
    assert verify_clocks_and_curves(source)==verify_clocks_and_curves(destination)
    assert lifetime_record(destination,10)['lifetime']==lifetime_record(destination,11)['lifetime']==.5
    c=FXParser(destination)
    for a,b in zip(q.exports(),c.exports(),strict=True):
        if a['index'] not in stores:assert q.b[a['start']:a['start']+a['size']]==c.b[b['start']:b['start']+b['size']]
    for a,b in zip(scripts(source),scripts(destination),strict=True):assert a[3]==b[3]
    return dict(size_before=[1500,225],size_after=[1200,180],both_dimensions_ratio=.8,
        aspect_ratio_preserved=True,linear_colour_before=[10,6,24,1],linear_colour_after=[6,1,10,1],
        original_blackout_component_and_curves_unchanged=True,all_niagara_scripts_unchanged=True,
        two_ray_lifetimes_seconds=.5,position_angles_depthoff_and_renderer_count_preserved=True,
        changed_post_byte_count=len(differences))

def move_blackout_before_separate_translucency(source,destination):
    q=FXParser(source);e,=q.exports();q.p=e['start']
    fields=read_fields(q,'MaterialInstanceConstant');end=q.p
    schema={name:(i,typ) for i,name,typ in q.schema('MaterialInstanceConstant')}
    flag,_=schema['bOverrideBlendableLocation'];location,_=schema['BlendableLocationOverride']
    assert flag not in fields and location not in fields
    # Actual 5.7 game usmap: 1 = SceneColorAfterDOF, before AfterDOF translucency.
    fields[flag]=raw_field(b'\x01');fields[location]=raw_field(b'\x01')
    replacement=encode_fields(fields)+q.b[end:e['start']+e['size']]
    hs=struct.unpack_from('<I',q.b,4)[0]
    destination.write_bytes(rebuild_exports(q,bytearray(q.b[:hs]),0,{0:replacement}))
    c=FXParser(destination);ce,=c.exports();c.p=ce['start']
    result=read_fields(c,'MaterialInstanceConstant');new_end=c.p
    assert result[flag]['value']==1 and result[location]['value']==1
    for i,f in fields.items():
        if i not in (flag,location):
            assert result[i]['data']==f['data'] and result[i]['zero']==f['zero']
    assert c.b[new_end:ce['start']+ce['size']]==q.b[end:e['start']+e['size']]
    return dict(material='MT_FX_PP_StrongAttackWarning_001',runtime_instance_location_override=True,
        previous_inherited_location='SceneColorAfterTonemapping (default 0)',
        new_location='SceneColorAfterDOF (1), before AfterDOF separate translucency composition',
        parent_material_and_all_shader_data_unchanged=True,blackout_parameters_and_MPC_unchanged=True,
        exactly_two_material_instance_properties_added=True,engine_rendering_not_yet_tested=True)
