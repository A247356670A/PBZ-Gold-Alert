"""Dispatch actual gauntlet contacts before the old tag/success/distance gates."""
import json,re,struct,sys
from pathlib import Path
from gauntlet_counter_v169 import ROOT,decode_functions,kismet
from zen_fx_edit import append_names,rebuild_exports

def add_native_imports(q,header,ids):
    old_end=struct.unpack_from('<I',header,32)[0]
    first=(old_end-struct.unpack_from('<I',header,28)[0])//8
    out=bytearray(header[:old_end]+struct.pack('<'+'Q'*len(ids),*ids)+header[old_end:])
    for off in [4,32,36,40,44,48,52,56]:
        struct.pack_into('<I',out,off,struct.unpack_from('<I',header,off)[0]+len(ids)*8)
    return out,[-first-i-1 for i in range(len(ids))]

def patch(source,destination):
    original,original_fns=decode_functions(source)
    # These native functions are already referenced by the original impact helper.
    helper,helper_fns=decode_functions(ROOT/'work/gauntlet-trigger-v1610/BP_DelayImpactObject.uasset')
    hd=kismet.Bytecode(helper,b'');native_ids=[]
    for name in ['GetTimelineByName','IsPlayingTimeline']:
        found=[i for i,g in enumerate(hd.imports) if kismet.SCRIPT_IDS.get(g)==name]
        assert len(found)==1,(name,found)
        native_ids.append(hd.imports[found[0]])
    header,_,names=append_names(original,['Bullet.SkillType.PowerAttack'])
    header,refs=add_native_imports(original,header,native_ids)
    linked=destination.with_name('gauntlet-linked-native.uasset');linked.parent.mkdir(parents=True,exist_ok=True)
    hs=struct.unpack_from('<I',original.b,4)[0];linked.write_bytes(header+original.b[hs:])
    q,functions=decode_functions(linked);g=next(x for x in functions if x['function'].startswith('ExecuteUbergraph_'))
    nodes=g['expressions'];by={n['offset']:n for n in nodes};s=q.b[g['script_start']:g['script_start']+g['disk_size']]
    def raw(a,b):return s[by[a]['disk']:by[b]['disk']]
    def expression(n):
        assert n['op']=='00'
        return s[n['disk']:n['disk']+17]
    def length(b):
        d=kismet.Bytecode(q,b)
        while d.p<len(b):d.expr()
        return d.mem
    end=nodes[-1];assert end['op']=='53' and end['offset']==0xc9a
    dispatcher=bytearray();fixups=[]
    def emit(b):dispatcher.extend(b)
    def jump(op,label,condition=b''):
        at=len(dispatcher);emit(bytes([op])+bytes(4)+condition);fixups.append((at+1,label))
    power_container=bytearray(raw(0x16d,0x1c0))
    # Locate the nested native array count using the decoded original expression.
    assignment=by[0x16d];array=assignment['value']['args'][0]['values'][0]
    assert array['op']=='65' and array['count']==1
    element=array['values'][0];item=s[element['disk']:element['disk']+19]
    assert item[0]==0x2f and item[9]==0x21 and item[-1]==0x30
    newitem=bytearray(item);struct.pack_into('<I',newitem,10,names['Bullet.SkillType.PowerAttack'])
    at=power_container.find(b'\x01\x00\x00\x00'+item)
    assert at>=0
    struct.pack_into('<I',power_container,at,2)
    power_container[at+4+len(item):at+4+len(item)]=newitem
    emit(power_container);emit(raw(0x1c0,0x1f8))
    power_condition=expression(by[0x1f8]['condition'])
    original_condition=expression(by[0x15f]['condition'])
    jump(7,'original',power_condition)
    name_const=b'\x21'+struct.pack('<II',q.names.index('Couter'),0)
    timeline=b'\x1c'+struct.pack('<i',refs[0])+name_const+b'\x16'
    playing=b'\x1c'+struct.pack('<i',refs[1])+timeline+b'\x16'
    # Do not restart a counter already running during a multihit attack.
    jump(7,'play',playing);emit(b'\x4d')
    play_addr=end['offset']+length(dispatcher)
    play=by[0x2a1];first=play['args'][0]
    assert first['var'].startswith('Couter@')
    original_play=raw(0x2a1,0x2d0);offset=first['disk']-play['disk']
    emit(original_play[:offset]+timeline+original_play[offset+17:])
    emit(raw(0x2d0,0x2de));emit(b'\x4d')
    original_addr=end['offset']+length(dispatcher)
    jump(7,0x75a,original_condition);jump(6,0x16d)
    labels={'original':original_addr,'play':play_addr}
    for at,label in fixups:struct.pack_into('<I',dispatcher,at,labels[label] if isinstance(label,str) else label)
    code=bytearray(s)
    branch=by[0x15f]
    code[branch['disk']:branch['disk']+5]=b'\x06'+struct.pack('<I',end['offset'])
    code[end['disk']:end['disk']]=dispatcher
    d=kismet.Bytecode(q,code);parsed=[]
    while d.p<len(code):parsed.append(d.expr())
    # Every original address is stable; the old gates remain only for nonblack attacks.
    assert all(n['offset'] in {x['offset'] for x in parsed} for n in nodes[:-1])
    e=g['export'];h=g['script_header'];old=q.b[e['start']:e['start']+e['size']]
    replacement=old[:h]+struct.pack('<II',d.mem,len(code))+code+old[h+8+g['disk_size']:]
    hs=struct.unpack_from('<I',q.b,4)[0]
    destination.write_bytes(rebuild_exports(q,bytearray(q.b[:hs]),0,{e['index']:replacement}))
    c,after=decode_functions(destination);assert len(after)==9
    for a,b in zip(original.exports(),c.exports(),strict=True):
        if a['index']!=2:assert original.b[a['start']:a['start']+a['size']]==c.b[b['start']:b['start']+b['size']]
    return original_fns,after,dict(
        base='original game; v1.6.9 predicate patch replaced',changed_export=2,
        black_dispatch_before_original_success_and_distance_gates=True,
        accepts_actual_normal_and_continuous_contact_events=True,
        preattack_still_ignored=True,black_tags=['Bullet.Tag.Feature.Deflect.PowerAttack','Bullet.SkillType.PowerAttack'],
        timeline_resolved_by_native_name='Couter',prevents_restarting_active_counter=True,
        native_imports_added=['GetTimelineByName','IsPlayingTimeline'],
        unchanged_other_exports=108,original_entry_addresses_preserved=True,
        in_game_tested=False)

if __name__=='__main__':
    source=ROOT/'work/gauntlet-parry-investigation/assets/GA_TieKuangQuanTao_GuardPoint.uasset'
    destination=ROOT/'work/gold-alert-v1610/GA_TieKuangQuanTao_GuardPoint.uasset'
    before,after,proof=patch(source,destination)
    (destination.parent/'gauntlet-trigger-proof.json').write_text(json.dumps(proof,indent=2))
    (destination.parent/'guardpoint-bytecode-patched.json').write_text(json.dumps(after,indent=2))
    print(json.dumps(proof,indent=2))
