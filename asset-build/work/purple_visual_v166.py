"""Move only the two local purple sprites; leave the blackout and VM intact."""
import struct
from parse_fx import FXParser
from inspect_fx_vm import scripts
from zen_fx_edit import append_names,read_fields,encode_fields,raw_field,object_bytes,rebuild_exports

POSITION='User.PBZ_PPosition'


def patch(source,destination):
    q=FXParser(source);ex=q.exports()
    header,delta,names=append_names(q,[POSITION]);replacements={}
    # Reuse this package's actual Niagara Position type (3 x float in parameter data).
    for _,_,e,v,recs in scripts(source):
        if e['outer']!=10:continue
        definition=next(a['TypeDef'] for a in v['CachedScriptVM']['Attributes'] if a['Name']=='Position')
        type_rec=next(r for r in recs if r['kind']=='struct' and r['type']=='NiagaraTypeDefinition' and r['value']==definition)
        pos_type=q.b[type_rec['start']:type_rec['end']]
        break
    name=struct.pack('<II',names[POSITION],0);variable=name+pos_type
    binding=object_bytes({0:name,1:variable,2:name,3:b'\x04',4:b'\x01',5:b'\0'})
    records=[]
    for index,typ,store_type in [(10,'NiagaraEmitter','NiagaraParameterStore'),(11,'NiagaraEmitter','NiagaraParameterStore'),(23,'NiagaraSystem','NiagaraUserRedirectionParameterStore')]:
        e=ex[index];q.p=e['start'];q.records=[];value=q.obj(typ)
        if index!=23:assert value['VersionData'][0]['bLocalSpace']==1
        rec=next(r for r in q.records if r['kind']=='struct' and r['type']==store_type)
        q.p=rec['start'];fields=read_fields(q,store_type)
        data=bytearray(rec['value']['ParameterData']);items=[]
        for item in rec['value']['SortedParameterOffsets']:
            row=next(r for r in q.records if r['kind']=='value' and r['type']==('Struct','NiagaraVariableWithOffset') and rec['start']<=r['start']<r['end']<=rec['end'] and r['value']==item)
            items.append((item['Name'],q.b[row['start']:row['end']]))
            if item['Name']=='User.PBZ_PSize':
                at=item['Offset'];assert struct.unpack_from('<ff',data,at)==(1500.,120.)
                struct.pack_into('<ff',data,at,1500.,150.)
        assert POSITION not in [n for n,_ in items]
        items.append((POSITION,variable+struct.pack('<i',len(data))));data+=struct.pack('<fff',0,0,100)
        for i,f in fields.items():
            if f['name']=='SortedParameterOffsets':fields[i]=raw_field(struct.pack('<I',len(items))+b''.join(v for _,v in sorted(items)))
            if f['name']=='ParameterData':fields[i]=raw_field(struct.pack('<I',len(data))+data)
        replacements[index]=q.b[e['start']:rec['start']]+encode_fields(fields)+q.b[rec['end']:e['start']+e['size']]
        records.append(index)
    for index in [21,22]:
        e=ex[index];q.p=e['start'];fields=read_fields(q,'NiagaraSpriteRendererProperties');tail=q.b[q.p:e['start']+e['size']]
        fields[29]=raw_field(binding);fields[49]=raw_field(binding)
        replacements[index]=encode_fields(fields)+tail
    destination.write_bytes(rebuild_exports(q,header,delta,replacements))
    c=FXParser(destination);ce=c.exports();assert len(ex)==len(ce)==24
    for a,b in zip(ex,ce,strict=True):
        assert (a['name'],a['outer'],a['number'])==(b['name'],b['outer'],b['number'])
        if a['index'] not in replacements:assert q.b[a['start']:a['start']+a['size']]==c.b[b['start']:b['start']+b['size']]
    for old,new in zip(scripts(source),scripts(destination),strict=True):assert old[3]==new[3]
    for index,typ,store_type in [(10,'NiagaraEmitter','NiagaraParameterStore'),(11,'NiagaraEmitter','NiagaraParameterStore'),(23,'NiagaraSystem','NiagaraUserRedirectionParameterStore')]:
        c.p=ce[index]['start'];c.records=[];c.obj(typ)
        rec=next(r for r in c.records if r['kind']=='struct' and r['type']==store_type)
        params={p['Name']:p for p in rec['value']['SortedParameterOffsets']};data=bytes(rec['value']['ParameterData'])
        assert struct.unpack_from('<fff',data,params[POSITION]['Offset'])==(0,0,100)
        assert struct.unpack_from('<ff',data,params['User.PBZ_PSize']['Offset'])==(1500,150)
    for index in [21,22]:
        c.p=ce[index]['start'];v=c.obj('NiagaraSpriteRendererProperties')
        for key in ['PositionBinding','PrevPositionBinding']:assert v[key]['RootName']==POSITION
        assert v['Material']==-34
        assert v['MaterialParameters']['ScalarParameters'][0]['Value']==0
    return dict(length=1500,thickness_before=120,thickness_after=150,thickness_ratio=1.25,
        local_position=[0,0,100],upward_offset_cm=100,position_binding=POSITION,
        two_renderers_share_exact_position=True,all_vm_and_blackout_exports_bit_exact=True,
        no_new_objects=True,native_export_count=24,depth_off_material_preserved=True)
