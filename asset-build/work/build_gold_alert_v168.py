"""Synchronize the purple X lifetime with one float edit; preserve audible A audio."""
from pathlib import Path
import json,struct,subprocess,shutil,sys,uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from build_gold_alert_v160 import digest
from parse_fx import FXParser
from inspect_fx_vm import scripts,disassemble
from fx_vm_trace import output_expressions

BUILD=ROOT/'work/gold-alert-v168';RAW=BUILD/'raw';OUT=ROOT/'outputs/PBZ-Gold-Alert-v1.6.8'
PRIOR=ROOT/'work/gold-alert-v167/A-Confirmed-Purple/raw'
PRIOR_OUT=ROOT/'outputs/PBZ-Gold-Alert-v1.6.7-Audio-Test/A-Confirmed-Purple'
POST='7dc2590713fc314d00000001'
GAME_MOD=Path(r'G:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks\~mods')


def lifetime_record(path,outer):
    for q,ex,e,v,recs in scripts(path):
        if e['outer']!=outer or e['name']!='SpawnScript':continue
        vm=v['CachedScriptVM'];code=disassemble(vm);base=code[0]['inputs'][0][1]
        # Calculate the typed float layout; skip UniqueID's separate integer data.
        sizes={-30:1,-24:4,-26:2,-32:3};attrs={};cursor=0
        for attr in vm['Attributes']:
            typ=attr['TypeDef']['ClassStructOrEnum']
            if typ==-31:continue
            size=sizes[typ];attrs[attr['Name']]=list(range(cursor,cursor+size));cursor+=size
        target,=attrs['Lifetime'];expression=output_expressions(code)['outputdata_float',0,target]
        assert expression[0]=='c'
        offset=expression[1]-base;literals=bytes(vm['ScriptLiterals'])
        literal_row,=[r for r in recs if r['kind']=='value' and r['type']==('Array',('Byte',)) and r['parent']=='NiagaraVMExecutableData' and r['value']==list(literals)]
        return dict(script=e['index'],emitter=outer,literal_offset=offset,
            byte_offset=literal_row['start']+4+offset,lifetime=struct.unpack_from('<f',literals,offset)[0])
    raise ValueError('Missing particle spawn lifetime')


def verify_clocks_and_curves(path):
    q=FXParser(path);exports=q.exports();q.p=exports[23]['start'];system=q.obj('NiagaraSystem')
    compiled=system['SystemCompiledData']['DataSetCompiledData']
    floats={var['Name']:int(layout.get('FloatComponentStart')or 0)
        for var,layout in zip(compiled['Variables'],compiled['VariableLayouts'])
        if layout['LayoutInfo'].get('NumFloatComponents')}
    suffixes=['Age','CurrentLoopDelay','CurrentLoopDuration','LoopedAge','NormalizedLoopAge',
        'SpawnBurst_Instantaneous.SpawnBurst']
    for index in [19,20]:
        q.p=exports[index]['start'];vm=q.obj('NiagaraScript')['CachedScriptVM']
        out=output_expressions(disassemble(vm))
        for suffix in suffixes:
            a=floats['Minimal001.'+suffix];b=floats['Minimal002.'+suffix]
            assert out['outputdata_float',0,a]==out['outputdata_float',0,b],(index,suffix)
    for a,b in [(2,5),(3,6),(4,7)]:
        q.p=exports[a]['start'];x=q.obj('NiagaraDataInterfaceCurve')
        q.p=exports[b]['start'];y=q.obj('NiagaraDataInterfaceCurve')
        assert x==y
    updates={e['outer']:v for _,_,e,v,_ in scripts(path) if e['outer']in [10,11] and e['name']=='UpdateScript'}
    left=updates[10]['CachedScriptVM'];right=updates[11]['CachedScriptVM']
    for key in ['ByteCode','ScriptLiterals','Attributes','CalledVMExternalFunctions']:
        assert left[key]==right[key]
    for a,b in zip(left['DataInterfaceInfo'],right['DataInterfaceInfo'],strict=True):
        assert a['SourceEmitterName']=='Minimal001' and b['SourceEmitterName']=='Minimal002'
        assert {k:v for k,v in a.items()if k!='SourceEmitterName'}=={k:v for k,v in b.items()if k!='SourceEmitterName'}
    # Original optimized contexts differ only in their per-script identity bytes.
    a=bytes(left['ExperimentalContextData']);b=bytes(right['ExperimentalContextData'])
    assert len(a)==len(b) and a[:46]==b[:46] and a[54:]==b[54:]
    return dict(system_spawn_and_update_timing_expressions_equal=True,
        all_three_paired_curve_definitions_equal=True,particle_update_bytecode_and_literals_equal=True)


def build():
    (RAW/'chunks').mkdir(parents=True,exist_ok=True);(OUT/'Mod').mkdir(parents=True,exist_ok=True)
    installed={}
    for extension in ['pak','utoc','ucas']:
        name='zz_PBZ_YellowAlert_P.'+extension
        expected=digest(PRIOR_OUT/'Mod'/name);actual=digest(GAME_MOD/name)
        assert expected==actual,('Installed mod is not the user-confirmed A build',name)
        installed[name]=actual
    for p in (PRIOR/'chunks').iterdir():shutil.copyfile(p,RAW/'chunks'/p.name)
    shutil.copyfile(PRIOR/'manifest.json',RAW/'manifest.json')
    source=PRIOR/'chunks'/POST;destination=RAW/'chunks'/POST
    a=lifetime_record(source,10);b=lifetime_record(source,11)
    assert abs(a['lifetime']-.3)<1e-6 and b['lifetime']==.5
    clock_evidence=verify_clocks_and_curves(source)
    original=source.read_bytes();data=bytearray(original)
    struct.pack_into('<f',data,a['byte_offset'],b['lifetime'])
    assert len(data)==len(original)
    differences=[i for i,(old,new) in enumerate(zip(original,data)) if old!=new]
    assert set(differences)<=set(range(a['byte_offset'],a['byte_offset']+4))
    assert len(differences)==4
    destination.write_bytes(data)
    new_a=lifetime_record(destination,10);new_b=lifetime_record(destination,11)
    assert new_a['lifetime']==new_b['lifetime']==.5
    assert verify_clocks_and_curves(destination)==clock_evidence
    old_parser=FXParser(source);new_parser=FXParser(destination)
    for old,new in zip(old_parser.exports(),new_parser.exports(),strict=True):
        if old['index']!=a['script']:
            assert old_parser.b[old['start']:old['start']+old['size']]==new_parser.b[new['start']:new['start']+new['size']]
    for old,new in zip(scripts(source),scripts(destination),strict=True):
        before=old[3];after=new[3]
        if old[2]['index']==a['script']:
            previous=before['CachedScriptVM'].pop('ScriptLiterals');current=after['CachedScriptVM'].pop('ScriptLiterals')
            assert before==after  # Including the legacy and optimized bytecode.
            assert previous[:a['literal_offset']]==current[:a['literal_offset']]
            assert previous[a['literal_offset']+4:]==current[a['literal_offset']+4:]
        else:assert before==after
    unchanged={}
    for p in (PRIOR/'chunks').iterdir():
        if p.name!=POST:
            assert digest(p)==digest(RAW/'chunks'/p.name);unchanged[p.name]=digest(p)
    assert len(unchanged)==180
    retoc=ROOT/'tools/retoc/retoc.exe';toc=OUT/'Mod/zz_PBZ_YellowAlert_P.utoc'
    subprocess.run([str(retoc),'pack-raw',str(RAW),str(toc)],check=True)
    shutil.copyfile(PRIOR_OUT/'Mod/zz_PBZ_YellowAlert_P.pak',toc.with_suffix('.pak'))
    subprocess.run([str(retoc),'verify',str(toc)],check=True)
    check=BUILD/('roundtrip-'+uuid.uuid4().hex[:8]);subprocess.run([str(retoc),'unpack-raw',str(toc),str(check)],check=True)
    ids={p.name for p in (RAW/'chunks').iterdir()};assert len(ids)==181
    assert ids=={p.name for p in (check/'chunks').iterdir()}
    for p in (RAW/'chunks').iterdir():assert digest(p)==digest(check/'chunks'/p.name)
    inspect=BUILD/'inspect-post';inspect.mkdir(exist_ok=True)
    subprocess.run([str(retoc),'dump-test',str(toc),str(inspect),str(int.from_bytes(bytes.fromhex(POST)[:8],'little'))],check=True,capture_output=True)
    extracted,=inspect.glob('*.uasset');assert digest(extracted)==digest(destination)
    proof=dict(version='1.6.8',base='v1.6.7 A, user confirmed audio is now normal',
        installed_base_full_file_sha256=installed,visual_change='one particle lifetime literal, 0.3 -> 0.5 seconds',
        before=[a,b],after=[new_a,new_b],changed_post_byte_offsets=differences,
        only_four_post_bytes_changed=True,synchronization=clock_evidence,
        all_audio_and_timing_chunks_bit_exact_to_confirmed_a=True,unchanged_chunk_sha256=unchanged,
        dimensions_and_position_and_blackout_unchanged=True,no_new_objects=True,
        native_header_parse=True,container_verify=True,raw_roundtrip_exact=True,
        roundtrip_directory=str(check),installed=False,in_game_tested=False)
    (BUILD/'validation.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    (OUT/'validation.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    shutil.copytree(PRIOR_OUT/'Preview',OUT/'Preview',dirs_exist_ok=True)
    (OUT/'README.txt').write_text(
        'PBZ Gold Alert v1.6.8 开发测试版\n\n'
        '黑光攻击显示紫色45度X形预警，两个光条使用相同寿命并同步消失。\n'
        '保留加粗25%、上移到头顶附近、穿透显示、全屏变暗和提前100毫秒设置。\n'
        '音效沿用1.6.7 A已确认正常的紫光提示音。红黄光沿用正式版1.1。\n\n'
        '安装：完全退出游戏，将Mod内三个文件一起复制到\n'
        'ProjectPBZ\\Content\\Paks\\~mods，覆盖旧版同名文件后重启游戏。\n'
        '卸载：退出游戏后移除上述三个文件。\n',encoding='utf-8-sig')
    (OUT/'SHA256SUMS.txt').write_text(''.join(digest(p)+'  Mod/'+p.name+'\n' for p in sorted((OUT/'Mod').iterdir())),encoding='utf-8')
    print(json.dumps(dict(output=str(OUT),lifetimes_before=[a['lifetime'],b['lifetime']],lifetimes_after=[.5,.5],
        changed_post_bytes=len(differences),audio_bit_exact=True,offline_verified=True,in_game_tested=False)),flush=True)


if __name__=='__main__':build()
