"""Advance only the black-warning LGAActionEvent start fields; retain every other byte."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from investigate_black_timing import inspect
from build_yellow_alert_v011 import store_table
from parse_fx import FXParser


def verify_action_scope(analysis):
    checked=0
    for asset in analysis['assets']:
        q=FXParser(ROOT/'work/black-timing-investigation/assets'/(asset['cid']+'.uasset'))
        for i in asset['power_exports']:
            q.p=q.exports()[i]['start'];idx=0;fragments=[];zc=0
            while True:
                h=q.take('H');idx+=h&127;zero=bool(h&128);count=h>>9
                fragments.extend((idx+j,zero)for j in range(count));idx+=count
                if zero:zc+=count
                if h&256:break
            mask=q.take('B')if 0<zc<=8 else q.take('H')if 8<zc<=16 else int.from_bytes(q.raw((zc+31)//32*4),'little')if zc else 0
            # All current instances inherit the prototype's Post_001 asset.
            # A new game version with explicit overrides requires re-auditing scope.
            assert not any(index==5 for index,z in fragments),(asset['path'],i)
            checked+=1
    return {'checked_action_instances':checked,'all_inherit_black_Post_001':True,
            'no_other_warning_effect_class_modified':True}


def patch_all(chunks):
    investigation=ROOT/'work/black-timing-investigation'
    analysis=json.loads((investigation/'timing-analysis.json').read_text())
    assert not analysis['errors']
    assert len(analysis['inherited_resolution'])==10
    assert all(x['matches']and x['matches'][0]['event']['power_warning']for x in analysis['inherited_resolution'])
    scope=verify_action_scope(analysis)
    stores=store_table((ROOT/'work/black-alert-investigation/current/container-header').read_bytes())[0]
    changed=[];limited=[];already_zero=[];total_full=0
    for asset in analysis['assets']:
        events=asset['events']
        if not events:continue
        original=(investigation/'assets'/(asset['cid']+'.uasset')).read_bytes()
        assert hashlib.sha256(original).hexdigest()==asset['sha256']
        data=bytearray(original);allowed=set();edits=[]
        for event in events:
            old=event['start']
            if old==0:
                already_zero.append({'path':asset['path'],'timeline':event['timeline_name'],'guid':event['guid']})
                continue
            at=event['start_field_offset'];assert at is not None
            assert struct.unpack_from('<f',original,at)[0]==old
            new=max(0.,old-.1)
            struct.pack_into('<f',data,at,new)
            actual=struct.unpack_from('<f',data,at)[0]
            allowed.update(range(at,at+4))
            edit={'timeline':event['timeline_name'],'action_export':event['action']-1,'guid':event['guid'],
                  'field_offset':at,'previous_start':old,'new_start':actual,
                  'actual_advance_ms':(old-actual)*1000,'duration_unchanged':event['duration'],
                  'limited_by_timeline_start':old<.1}
            edits.append(edit)
            if old<.1:limited.append(dict(edit,path=asset['path']))
            else:
                assert abs(old-actual-.1)<2e-5
                total_full+=1
        if not edits:continue
        assert len(data)==len(original)
        diff={i for i,(a,b)in enumerate(zip(original,data))if a!=b}
        assert diff<=allowed
        hs=struct.unpack_from('<I',data,4)[0]
        assert data[:hs]==original[:hs]
        destination=chunks/asset['cid'];destination.write_bytes(data)
        info={k:asset[k]for k in ['path','index','cid','package_id']}
        after=inspect(destination,info,stores[asset['package_id']][0])
        before_by_guid={(e['timeline_name'],tuple(e['guid'])):e for e in events}
        for event in after['events']:
            prior=before_by_guid[event['timeline_name'],tuple(event['guid'])]
            assert abs(event['start']-max(0,prior['start']-.1))<2e-5
            assert event['duration']==prior['duration']and event['action']==prior['action']
        # All event-array indices and non-warning events retain their exact bytes.
        assert len(after['timeline_arrays'])==len(asset['timeline_arrays'])
        for a,b in zip(asset['timeline_arrays'],after['timeline_arrays'],strict=True):
            for old_event,new_event in zip(a['events'],b['events'],strict=True):
                assert tuple(old_event['guid'])==tuple(new_event['guid'])and old_event['action']==new_event['action']
                if not old_event['power_warning']:
                    start,end=old_event['record_start'],old_event['record_end']
                    assert original[start:end]==data[start:end]
        changed.append({'path':asset['path'],'cid':asset['cid'],'package_id':asset['package_id'],
                        'original_sha256':asset['sha256'],'new_sha256':hashlib.sha256(data).hexdigest(),
                        'edits':edits,'only_warning_start_float_bytes_changed':True,
                        'native_header_and_event_order_bit_exact':True})
    return {'requested_advance_ms':100,'modified_ability_assets':len(changed),
            'full_100ms_events':total_full,'limited_events':limited,'already_at_start_events':already_zero,
            'inherited_variants_follow_parent_timings':len(analysis['inherited_resolution']),
            'action_scope_verification':scope,
            'unchanged_attack_damage_parry_events_and_animation_data':True,'assets':changed}
