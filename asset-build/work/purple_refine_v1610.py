"""Widen/brighten the native purple sprites and let the finite cue finish."""
import json,struct
import numpy as np
from pathlib import Path
from gauntlet_counter_v169 import ROOT,decode_functions,kismet
from parse_fx import FXParser
from zen_fx_edit import rebuild_exports
from inspect_fx_vm import scripts
from build_gold_alert_v168 import verify_clocks_and_curves,lifetime_record

def visual(source,destination):
    q=FXParser(source);data=bytearray(q.b);allowed=set();old_values=[]
    for index,typ,store_type in [(10,'NiagaraEmitter','NiagaraParameterStore'),
            (11,'NiagaraEmitter','NiagaraParameterStore'),(23,'NiagaraSystem','NiagaraUserRedirectionParameterStore')]:
        q.p=q.exports()[index]['start'];q.records=[];q.obj(typ)
        store=next(r for r in q.records if r['kind']=='struct' and r['type']==store_type)
        value=store['value'];params={p['Name']:p['Offset'] for p in value['SortedParameterOffsets']}
        arr=next(r for r in q.records if r['kind']=='value' and r['type']==('Array',('Byte',))
            and store['start']<=r['start']<r['end']<=store['end'] and r['value']==value['ParameterData'])
        start=arr['start']+4
        size_at=start+params['User.PBZ_PSize'];color_at=start+params['User.PBZ_PColor']
        assert struct.unpack_from('<ff',data,size_at)==(1500.,150.)
        old_values.append(struct.unpack_from('<ffff',data,color_at))
        struct.pack_into('<ff',data,size_at,1500.,225.)
        struct.pack_into('<ffff',data,color_at,10.,6.,24.,1.)
        allowed.update(range(size_at,size_at+8));allowed.update(range(color_at,color_at+16))
    assert len(set(old_values))==1
    assert len(data)==len(q.b)
    assert {i for i,(a,b) in enumerate(zip(q.b,data)) if a!=b}<=allowed
    destination.write_bytes(data)
    assert verify_clocks_and_curves(source)==verify_clocks_and_curves(destination)
    assert lifetime_record(destination,10)['lifetime']==lifetime_record(destination,11)['lifetime']==.5
    for a,b in zip(scripts(source),scripts(destination),strict=True):assert a[3]==b[3]
    c=FXParser(destination)
    for a,b in zip(q.exports(),c.exports(),strict=True):
        if a['index'] not in (10,11,23):assert q.b[a['start']:a['start']+a['size']]==c.b[b['start']:b['start']+b['size']]
    return dict(thickness_before=150,thickness_after=225,length=1500,
        linear_color_before=old_values[0],linear_color_after=[10.,6.,24.,1.],
        brighter_pale_violet_core=True,positions_angles_and_depthoff_preserved=True,
        blackout_and_all_vm_scripts_unchanged=True,two_rays_synchronized_lifetime=.5,
        no_new_components=True)

def audio_completion(source,destination):
    q,functions=decode_functions(source)
    end=next(f for f in functions if f['function']=='Received_ActionEnd')
    stop,=[n for n in end['expressions'] if n.get('expr',{}).get('call')=='PBZStopPlayingID']
    assert stop['op']=='19' and stop['expr']['args'][1]['literal']==.5
    # This short direct function has no jumps/fastcall entrypoints to relocate.
    assert not any(n['op'] in ('06','07','4c','4e','69') for n in end['expressions'])
    original=q.b[end['script_start']:end['script_start']+end['disk_size']]
    following=end['expressions'][end['expressions'].index(stop)+1]
    code=original[:stop['disk']]+original[following['disk']:]
    d=kismet.Bytecode(q,code);after_nodes=[]
    while d.p<len(code):after_nodes.append(d.expr())
    assert not any(n.get('expr',{}).get('call')=='PBZStopPlayingID' for n in after_nodes)
    e=end['export'];h=end['script_header'];old=q.b[e['start']:e['start']+e['size']]
    assert old[-8:]==bytes(8)
    new=old[:h]+struct.pack('<II',d.mem,len(code))+code+old[h+8+end['disk_size']:]
    hs=struct.unpack_from('<I',q.b,4)[0]
    destination.write_bytes(rebuild_exports(q,bytearray(q.b[:hs]),0,{e['index']:new}))
    c,fns=decode_functions(destination)
    for a,b in zip(q.exports(),c.exports(),strict=True):
        if a['index']!=e['index']:assert q.b[a['start']:a['start']+a['size']]==c.b[b['start']:b['start']+b['size']]
    # Original parent action end and stencil-unset notification are preserved.
    end_after=next(f for f in fns if f['function']=='Received_ActionEnd')
    assert len(end_after['expressions'])==len(end['expressions'])-1
    def normalized(value):
        if isinstance(value,dict):return {k:normalized(v) for k,v in value.items() if k not in ('offset','disk')}
        if isinstance(value,list):return [normalized(v) for v in value]
        return value
    for a,b in zip([n for n in end['expressions'] if n is not stop],end_after['expressions'],strict=True):
        assert normalized(a)==normalized(b)
    wem=(ROOT/'work/gold-alert-v167/A-Confirmed-Purple/approved-padded.wem').read_bytes()
    pcm=np.frombuffer(wem[96:],'<i2').reshape(-1,2)
    active=np.flatnonzero(np.max(np.abs(pcm.astype(float)),axis=1)>32)
    return dict(removed_only_action_end_stop_call=True,previous_stop_fade_seconds=.5,
        audio_media_duration_seconds=len(pcm)/48000.,audible_tail_end_seconds=float(active[-1]+1)/48000.,
        original_audio_samples_and_bank_unchanged=True,finite_single_shot_media=True,
        original_parent_end_and_blackout_stencil_cleanup_preserved=True,
        actual_playback_recording_not_available=True)
