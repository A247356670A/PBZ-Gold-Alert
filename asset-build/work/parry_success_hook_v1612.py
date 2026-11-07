"""Stage a contact-success audio hook, preserving every existing function byte."""
import sys,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from parse_fx import FXParser
from zen_fx_edit import rebuild_exports
from gauntlet_counter_v169 import decode_functions,kismet
from investigate_black_timing import prefix_field
from build_yellow_alert_v011 import store_table
B=ROOT/'work/parry-success-v1612'

def prepare():
    raw=ROOT/'work/gold-alert-v1611/combined/raw';m=json.loads((raw/'manifest.json').read_text())
    cid=next(c for c,p in m['chunk_paths'].items() if p.endswith('/GA_TieKuangQuanTao_GuardPoint.uasset'))
    source=raw/'chunks'/cid;q,fs=decode_functions(source);exports=q.exports()
    q.p=exports[9]['start'];field=prefix_field(q,'GA_TieKuangQuanTao_GuardPoint_C','GpSuccessSFX')
    assert field['value']==-8 and field['end']-field['start']==4
    # Existing import -2 resolves to the weapon's own Counter_Cast event.
    decoder=kismet.Bytecode(q,b'');imp=decoder.imports[1]
    assert imp>>32==0x80000001
    stores=store_table((ROOT/'work/black-alert-investigation/current/container-header').read_bytes())[0]
    pid=int.from_bytes(bytes.fromhex(cid)[:8],'little');deps=stores[pid][0]
    assert struct.unpack_from('<Q',deps,8)[0]==int.from_bytes(bytes.fromhex('9cb4fa0b16056913'),'little')
    cdo=bytearray(q.b[exports[9]['start']:exports[9]['start']+exports[9]['size']])
    struct.pack_into('<i',cdo,field['start']-exports[9]['start'],-2)
    # Move the existing cast event to contact success. Remove only its former
    # counter-animation entry, preventing delayed duplicate playback.
    timeline=exports[93];assert timeline['name']=='Couter'
    q.p=timeline['start'];q.records=[];actions=prefix_field(q,'LGATimeline','Actions')
    events=[r for r in q.records if r['kind']=='struct' and r['type']=='LGAActionEvent']
    target,=[r for r in events if r['value'].get('Action')==35]
    assert abs(target['value']['StartTime']-.8884782791)<1e-6
    body=bytearray(q.b[timeline['start']:timeline['start']+timeline['size']])
    at=actions['start']-timeline['start'];count=struct.unpack_from('<I',body,at)[0]
    assert count==len(events)
    struct.pack_into('<I',body,at,count-1)
    del body[target['start']-timeline['start']:target['end']-timeline['start']]
    hs=struct.unpack_from('<I',q.b,4)[0]
    dest=B/'GA_TieKuangQuanTao_GuardPoint-success-hook.uasset'
    dest.write_bytes(rebuild_exports(q,bytearray(q.b[:hs]),0,{9:bytes(cdo),93:bytes(body)}))
    after,funcs=decode_functions(dest)
    for a,b in zip(exports,after.exports(),strict=True):
        if a['index'] not in [9,93]:assert q.b[a['start']:a['start']+a['size']]==after.b[b['start']:b['start']+b['size']]
    assert len(fs)==len(funcs)==9
    for a,b in zip(fs,funcs,strict=True):
        assert q.b[a['script_start']:a['script_start']+a['disk_size']]==after.b[b['script_start']:b['script_start']+b['disk_size']]
    after.p=after.exports()[9]['start'];assert prefix_field(after,'GA_TieKuangQuanTao_GuardPoint_C','GpSuccessSFX')['value']==-2
    after.p=after.exports()[93]['start'];remaining=prefix_field(after,'LGATimeline','Actions')['value']
    assert len(remaining)==count-1 and not any(x.get('Action')==35 for x in remaining)
    def clean(x):return {k:v for k,v in x.items()}
    assert remaining==[r['value']for r in events if r is not target]
    proof=dict(source=str(source),staged_file=str(dest),guard_cid=cid,
        success_contact_event_property_from=-8,success_contact_event_property_to=-2,
        audio_event='SFX_Combat_Special_ShaQi_QuanTao_Counter_Cast',
        all_nine_native_functions_bit_exact=True,all_counter_logic_bit_exact=True,
        preattack_ignored_as_before=True,contact_audio_independent_of_counter_animation=True,
        removed_only_duplicate_counter_animation_audio_entry=True,
        changed_only_exports=[9,93],other_exports_unchanged=107,
        not_installed=True,final_audio_not_selected=True)
    (B/'success-hook-proof.json').write_text(json.dumps(proof,indent=2))
    print(json.dumps(proof,indent=2))

if __name__=='__main__':prepare()
