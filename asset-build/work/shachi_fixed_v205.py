"""Set player Shachi to 30% of the current maximum after a black gauntlet contact."""
import sys,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work'),str(ROOT/'work/hash-deps')]
from cityhash import CityHash64
from fx_parser_v205 import FX205
from zen_fx_edit import read_fields,raw_field,encode_fields,object_bytes,rebuild_exports
from restore_black_post_v162 import name_batch,read_name_batch
from gauntlet_counter_v169 import decode_functions,kismet
from build_yellow_alert_v011 import store_table

GUARD='b1bf5d2781c0dfbe00000001'
GE_OLD='GE_Cost_Shachi_ToZero';GE_NEW='GE_PBZ_Shachi_Set0030'
GE_PATH='/PBZCombatAsset/Prototypes/Abilities/Base/GE/'+GE_NEW
GE_PID=CityHash64(GE_PATH.lower().encode('utf-16-le'))
GE_CID=struct.pack('<Q',GE_PID).hex()+'00000001'
PERIOD=.05;DURATION=.075

def scale(value):return object_bytes({0:struct.pack('<f',value)})

def effect(destination):
    source=ROOT/'work/investigate-v205/GE_Cost_Shachi_ToZero.uasset';q=FX205(source);old=q.b
    assert len(GE_OLD)==len(GE_NEW)
    names=[n.replace(GE_OLD,GE_NEW)for n in q.names]+['Shachi_Max'];assert len(names)==len(set(names))
    version=struct.unpack_from('<Q',old,68)[0];batch=name_batch(names,version);end=60+len(batch);pad=(-end)%8
    old_imports=struct.unpack_from('<I',old,24)[0];hs=struct.unpack_from('<I',old,4)[0]
    prefix=old[:60]+batch+struct.pack('<Q',pad)+bytes(pad)+struct.pack('<Q',0)
    old_bulk=q.name_end+8+struct.unpack_from('<Q',old,q.name_end)[0]
    assert struct.unpack_from('<Q',old,old_bulk)[0]==0 and old_bulk+8==old_imports
    delta=len(prefix)-old_imports;header=bytearray(prefix+old[old_imports:hs])
    for at in [4,24,28,32,36,40,44,48,52,56]:struct.pack_into('<I',header,at,struct.unpack_from('<I',old,at)[0]+delta)
    for e in q.exports():
        at=struct.unpack_from('<I',header,32)[0]+e['index']*72+56
        assert struct.unpack_from('<Q',header,at)[0]==CityHash64(e['name'].lower().encode('utf-16-le'))
        struct.pack_into('<Q',header,at,CityHash64(e['name'].replace(GE_OLD,GE_NEW).lower().encode('utf-16-le')))
    e=q.exports()[1];q.p=e['start'];fields=read_fields(q,'GameplayEffect');end=q.p
    q.p=fields[6]['start'];assert q.take('I')==1;mf=read_fields(q,'GameplayModifierInfo')
    assert mf[1]['value']==3
    q.p=mf[2]['start'];mag=read_fields(q,'GameplayEffectModifierMagnitude')
    q.p=mag[2]['start'];af=read_fields(q,'AttributeBasedFloat')
    # Capture the owner's real maximum, including upgrades; preserve the native
    # BasicAttributeSet import already used by the source effect's Shachi field.
    old_attribute=mf[0]['data'];q.p=mf[0]['start'];attr=read_fields(q,'GameplayAttribute')
    assert attr[0]['value']=='Shachi'and attr[1]['value']==dict(path=['Shachi'],owner=-2)and attr[2]['value']==-2
    name='Shachi_Max';name_index=names.index(name)
    max_attr=object_bytes({0:struct.pack('<i',len(name)+1)+name.encode()+b'\0',
        1:struct.pack('<IIIi',1,name_index,0,-2),2:struct.pack('<i',-2)})
    af[0]=raw_field(scale(.3))
    af[3]=raw_field(object_bytes({0:max_attr,1:b'\x01',2:b'\x01'})) # Target, snapshot
    mag[0]=raw_field(b'\x01');mag[2]=raw_field(encode_fields(af))
    mf[2]=raw_field(encode_fields(mag));fields[6]=raw_field(struct.pack('<I',1)+encode_fields(mf))
    # A single delayed periodic execution runs after the original contact cost.
    # Periodic modifiers execute on the base attribute; expiration does not undo it.
    fields[0]=raw_field(b'\x02') # HasDuration
    fields[1]=raw_field(object_bytes({0:b'\0',1:scale(DURATION)}))
    fields[3]=raw_field(scale(PERIOD));fields[4]=raw_field(b'\0')
    payload=encode_fields(fields)+old[end:e['start']+e['size']]
    destination.write_bytes(rebuild_exports(q,header,delta,{1:payload}));after=FX205(destination)
    ae=after.exports()[0];assert old[q.exports()[0]['start']:q.exports()[0]['start']+q.exports()[0]['size']]==after.b[ae['start']:ae['start']+ae['size']]
    after.p=after.exports()[1]['start'];props=after.obj('GameplayEffect');assert after.p+4==len(after.b)
    m,=props['Modifiers'];assert m['Attribute']['AttributeName']=='Shachi'and m['ModifierOp']==3
    a=m['ModifierMagnitude']['AttributeBasedMagnitude'];assert abs(a['Coefficient']['Value']-.3)<1e-6
    assert a['BackingAttribute']['AttributeToCapture']['Attribute']['path']==['Shachi_Max']
    assert a['BackingAttribute']['AttributeSource']==1 and a['BackingAttribute']['bSnapshot']==1
    assert props['bExecutePeriodicEffectOnApplication']==0 and props['DurationPolicy']==2
    assert abs(props['Period']['Value']-PERIOD)<1e-6
    return dict(cid=GE_CID,path='ProjectPBZ/Plugins/Secret/PBZCombatAsset/Content/Prototypes/Abilities/Base/GE/'+GE_NEW+'.uasset',
        template_cid=next(r['cid']for r in json.loads((ROOT/'work/investigate-v205/cost-assets.json').read_text())if r['index']==52256),
        public_class_hash=CityHash64((GE_NEW+'_C').lower().encode('utf-16-le')),
        attribute='Shachi',operation='Override',capture='Target.BasicAttributeSet.Shachi_Max',fraction=.3,
        duration_seconds=DURATION,period_seconds=PERIOD,execute_on_application=False,
        scheduled_executions=1,expiry_does_not_restore_previous_base_value=True,properties=props)

def link_guard(source,destination,public_hash):
    q,fs=decode_functions(source);b=q.b;off={at:struct.unpack_from('<I',b,at)[0]for at in [4,24,28,32,36,40,44,48,52,56]}
    assert off[52]==off[56]==off[36]
    packages,version,end=read_name_batch(b,off[48]);assert end+len(packages)*4==off[4]
    numbers=b[end:off[4]];new_names=name_batch(packages+[GE_PATH],version)+numbers+bytes(4)
    hashes=list(struct.unpack('<'+'Q'*((off[28]-off[24])//8),b[off[24]:off[28]]));hash_index=len(hashes);hashes.append(public_hash)
    imports=list(struct.unpack('<'+'Q'*((off[32]-off[28])//8),b[off[28]:off[32]]))
    native_id,= [gid for gid,n in kismet.SCRIPT_IDS.items()if n=='BP_ApplyGameplayEffectToOwner']
    native_ref=-len(imports)-1;imports.append(native_id)
    ge_ref=-len(imports)-1;imports.append(0x8000000000000000|(len(packages)<<32)|hash_index)
    entries=[v[0]for v in struct.iter_unpack('<i',b[off[44]:off[48]])];groups=[]
    for i in range(len(q.exports())):
        first,*counts=struct.unpack_from('<i4I',b,off[40]+i*20);g=[]
        for count in counts:g.append(entries[first:first+count]);first+=count
        groups.append(g)
    groups[2][2].append(ge_ref)
    depheaders=bytearray();depentries=[]
    for g in groups:
        depheaders.extend(struct.pack('<i4I',len(depentries),*map(len,g)))
        for v in g:depentries.extend(v)
    result=bytearray(b[:off[24]]);starts={24:len(result)}
    result.extend(struct.pack('<'+'Q'*len(hashes),*hashes));starts[28]=len(result)
    result.extend(struct.pack('<'+'Q'*len(imports),*imports));starts[32]=len(result)
    result.extend(b[off[32]:off[36]]);starts[52]=starts[56]=starts[36]=len(result)
    result.extend(b[off[36]:off[40]]);starts[40]=len(result);result.extend(depheaders)
    starts[44]=len(result);result.extend(struct.pack('<'+'i'*len(depentries),*depentries))
    starts[48]=len(result);result.extend(new_names);starts[4]=len(result)
    for at,v in starts.items():struct.pack_into('<I',result,at,v)
    result.extend(b[off[4]:]);destination.write_bytes(result)
    linked,lfs=decode_functions(destination)
    for a,z in zip(q.exports(),linked.exports(),strict=True):assert b[a['start']:a['start']+a['size']]==linked.b[z['start']:z['start']+z['size']]
    return linked,lfs,native_ref,ge_ref,len(packages)

def guard_patch(source,destination,build,ge):
    q,fs,native_ref,ge_ref,package_count=link_guard(source,build/'guard-linked.uasset',ge['public_class_hash'])
    g=next(f for f in fs if f['function'].startswith('ExecuteUbergraph_'));nodes=g['expressions'];end=nodes[-1]
    assert end['op']=='53'
    # Select the already gated black-only dispatcher path, not the original
    # distance-based blue counter path and not the common success handler.
    plays=[n for n in nodes if n.get('call')=='PlayTimeline'and n.get('args',[{}])[0].get('call')=='GetTimelineByName'];play,=plays
    branch,= [n for n in nodes if n.get('op')=='07'and n.get('condition',{}).get('call')=='IsPlayingTimeline']
    assert branch['jump']==play['offset']
    following=[n for n in nodes if n['offset']>=play['offset']];assert following[1].get('call')=='OnCounter'and following[2]['op']=='4d'
    start=g['script_start'];s=q.b[start:start+g['disk_size']]
    original_play=s[play['disk']:following[2]['disk']+1]
    call=b'\x1c'+struct.pack('<i',native_ref)+b'\x20'+struct.pack('<i',ge_ref)+b'\x26\x26\x16'
    tail=original_play[:-1]+call+b'\x4d'
    code=bytearray(s);struct.pack_into('<I',code,branch['disk']+1,end['offset']);code[end['disk']:end['disk']]=tail
    d=kismet.Bytecode(q,code);parsed=[]
    while d.p<len(code):parsed.append(d.expr())
    assert parsed[-1]['op']=='53'and d.mem==g['memory_size']+sum_memory(q,tail)
    assert all(a['offset']==z['offset']for a,z in zip(nodes[:-1],parsed[:len(nodes)-1],strict=True))
    e=g['export'];h=g['script_header'];old=q.b[e['start']:e['start']+e['size']]
    payload=old[:h]+struct.pack('<II',d.mem,len(code))+code+old[h+8+g['disk_size']:]
    hs=struct.unpack_from('<I',q.b,4)[0];destination.write_bytes(rebuild_exports(q,bytearray(q.b[:hs]),0,{e['index']:payload}))
    after,af=decode_functions(destination)
    for a,z in zip(q.exports(),after.exports(),strict=True):
        if a['index']!=2:assert q.b[a['start']:a['start']+a['size']]==after.b[z['start']:z['start']+z['size']]
    return af,dict(changed_export=2,old_memory=g['memory_size'],new_memory=d.mem,
        old_black_play_address=play['offset'],new_black_play_address=end['offset'],
        existing_entrypoints_and_all_other_branch_addresses_preserved=True,
        applies_only_after_valid_power_contact_and_before_counter_reentry_return=True,
        existing_active_counter_not_restarted_or_reapplied=True,
        no_added_delay_to_counter_or_audio=True,only_shachi_settlement_deferred_ms=50,
        all_other_exports_and_function_property_metadata_bit_exact=True,
        original_dependency_count=package_count,added_dependency_pid=GE_PID,
        native_function='BP_ApplyGameplayEffectToOwner',effect_class_ref=ge_ref)

def sum_memory(q,code):
    d=kismet.Bytecode(q,code)
    while d.p<len(code):d.expr()
    return d.mem
