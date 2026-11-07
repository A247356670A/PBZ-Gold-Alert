"""Read warning-only timeline events from current original assets."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from read_pbz import Reader
from parse_fx import FXParser
from zen_fx_edit import read_fields
from build_yellow_alert_v011 import store_table

OUT=ROOT/'work/black-timing-investigation'
TIMELINE_CLASS=0x5df315ef9af6076f
ABILITY_CLASS=0x52081f33179d7ab8
ACTION_PID=int.from_bytes(bytes.fromhex('7807bc1ded4a64b8'),'little')


def prefix_field(q,schema,stop,stop_decoder=None):
    props={i:(n,t)for i,n,t in q.schema(schema)}
    index=0;fragments=[];zc=0
    while True:
        h=q.take('H');index+=h&127;z=bool(h&128);count=h>>9
        fragments.extend((index+i,z)for i in range(count));index+=count
        if z:zc+=count
        if h&256:break
    mask=q.take('B')if 0<zc<=8 else q.take('H')if 8<zc<=16 else int.from_bytes(q.raw((zc+31)//32*4),'little')if zc else 0
    zi=0
    for index,z in fragments:
        zero=z and bool(mask&(1<<zi));zi+=int(z)
        n,t=props[index];start=q.p
        value=None if zero else stop_decoder(q,t)if n==stop and stop_decoder else q.value(t)
        if n==stop:return {'start':start,'end':q.p,'value':value,'zero':zero,'type':t}
    return None


def inspect(path,info,deps):
    q=FXParser(path);exports=q.exports();pids=[i[0]for i in struct.iter_unpack('<Q',deps)]
    powers=[]
    for e in exports:
        cls=e['class']
        if cls>>62==2:
            package=(cls&0x3fffffffffffffff)>>32
            if package<len(pids)and pids[package]==ACTION_PID:powers.append(e['index'])
    events=[];arrays=[];overrides=[];parents=[]
    for e in exports:
        if e['class']==TIMELINE_CLASS:
            q.p=e['start'];q.records=[]
            row=prefix_field(q,'LGATimeline','Actions')
            if not row or not row['value']:continue
            records=[r for r in q.records if r['kind']=='struct'and r['type']=='LGAActionEvent']
            assert len(records)==len(row['value'])
            all_events=[]
            for n,rec in enumerate(records):
                value=rec['value'];q.p=rec['start'];fields=read_fields(q,'LGAActionEvent')
                timing=next((f for f in fields.values()if f['name']=='StartTime'),None)
                matched=value.get('Action')in [p+1 for p in powers]
                item={'array_index':n,'record_start':rec['start'],'record_end':rec['end'],
                      'start':value.get('StartTime')or 0.,'duration':value.get('duration')or 0.,
                      'guid':value.get('Guid'),'action':value.get('Action'),'power_warning':matched,
                      'start_field_offset':timing['start']if timing and not timing['zero']else None}
                all_events.append(item)
                if matched:events.append(dict(item,timeline_export=e['index'],timeline_name=e['name']))
            arrays.append({'timeline_export':e['index'],'name':e['name'],
                           'start':row['start'],'end':row['end'],'events':all_events,
                           'sorted':all(a['start']<=b['start']for a,b in zip(all_events,all_events[1:]))})
        if e['class']==ABILITY_CLASS:
            q.p=e['start'];q.records=[]
            try:props=q.obj('LegoAbilityBlueprintGeneratedClass')
            except KeyError as error:
                # Two generated classes contain a newer optional blend-setting schema.
                # Read only the one override map we need; never modify blend settings.
                assert error.args==(5,)
                q.p=e['start'];q.records=[]
                def decode_single_override(parser,typ):
                    assert typ==('Array',('Struct','LGAActionOverride'))
                    assert parser.take('I')==1
                    begin=parser.p
                    row=prefix_field(parser,'LGAActionOverride','Overrides')
                    name=next(r['value']for r in parser.records if r['kind']=='value'
                              and r['type']==('Name',)
                              and begin<=r['start']<row['start'])
                    return [{'TimelineName':name,'Overrides':row['value']}]
                row=prefix_field(q,'LegoAbilityBlueprintGeneratedClass','ActionOverrides',decode_single_override)
                props={'ActionOverrides':row['value']}
            for ov in props.get('ActionOverrides')or[]:
                for item in ov.get('Overrides')or[]:
                    if item['value']in [p+1 for p in powers]:overrides.append({'timeline':ov['TimelineName'],'guid':item['key'],'action':item['value']})
            super_ref=struct.unpack_from('<Q',q.b,struct.unpack_from('<I',q.b,32)[0]+e['index']*72+40)[0]
            if super_ref>>62==2:
                i=(super_ref&0x3fffffffffffffff)>>32
                if i<len(pids):parents.append(pids[i])
    return dict(info,sha256=hashlib.sha256(q.b).hexdigest(),power_exports=powers,
                events=events,timeline_arrays=arrays,inherited_overrides=overrides,parent_packages=parents)


def run():
    (OUT/'assets').mkdir(exist_ok=True)
    r=Reader()
    rows=json.loads((ROOT/'analysis/build-20261105/asset-index.json').read_text())
    r.by_path={x['path']:x for x in rows}
    paths={int.from_bytes(r.toc[144+x['index']*12:152+x['index']*12],'little'):x for x in rows if x['path'].endswith('.uasset')}
    stores=store_table((ROOT/'work/black-alert-investigation/current/container-header').read_bytes())[0]
    targets=json.loads((OUT/'reverse-actions.json').read_text())['hits']
    results=[];errors=[]
    for n,x in enumerate(targets):
        cid=r.toc[144+x['index']*12:144+(x['index']+1)*12].hex()
        pid=int.from_bytes(bytes.fromhex(cid)[:8],'little')
        path=OUT/'assets'/(cid+'.uasset')
        if not path.exists():path.write_bytes(r.read(x['index']))
        try:results.append(inspect(path,dict(x,cid=cid,package_id=pid),stores[pid][0]))
        except Exception as error:errors.append(dict(x,cid=cid,error=repr(error)))
        if n%40==0:print('inspected',n+1,'/',len(targets),flush=True)
    by_pid={x['package_id']:x for x in results}
    inherited=[]
    for x in results:
        for ov in x['inherited_overrides']:
            hits=[];seen=set();todo=list(x['parent_packages'])
            while todo:
                pid=todo.pop()
                if pid in seen:continue
                seen.add(pid)
                if pid not in by_pid:
                    if pid not in paths:continue
                    item=paths[pid];cid=r.toc[144+item['index']*12:144+(item['index']+1)*12].hex()
                    path=OUT/'assets'/(cid+'.uasset')
                    if not path.exists():path.write_bytes(r.read(item['index']))
                    try:
                        parent=inspect(path,dict(item,cid=cid,package_id=pid),stores[pid][0]);by_pid[pid]=parent
                    except Exception as error:
                        errors.append(dict(item,error=repr(error)));continue
                parent=by_pid[pid]
                for arr in parent['timeline_arrays']:
                    if arr['name']!=ov['timeline']:continue
                    for event in arr['events']:
                        if event['guid']==ov['guid']:hits.append({'parent_pid':pid,'parent_path':parent['path'],'event':event})
                if not hits:todo.extend(parent['parent_packages'])
            inherited.append({'path':x['path'],'override':ov,'matches':hits})
    all_results=list(by_pid.values())
    output={'assets':all_results,'errors':errors,'inherited_resolution':inherited}
    (OUT/'timing-analysis.json').write_text(json.dumps(output,indent=2))
    events=[e for x in all_results for e in x['events']]
    print(json.dumps({'assets':len(all_results),'errors':len(errors),'direct_events':len(events),
                      'events_under_100ms':sum(e['start']<.1 for e in events),
                      'inherited_overrides':len(inherited),
                      'unresolved_inherited':sum(not x['matches']for x in inherited),
                      'inherited_from_non_power':sum(bool(x['matches'])and not x['matches'][0]['event']['power_warning']for x in inherited),
                      'unsorted_arrays':sum(not a['sorted']for x in all_results for a in x['timeline_arrays'])},indent=2))


if __name__=='__main__':run()
