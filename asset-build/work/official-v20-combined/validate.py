from pathlib import Path
import os,json,hashlib,zipfile,shutil,struct,subprocess,sys
from Crypto.Cipher import AES
ROOT=Path(__file__).resolve().parents[2];B=ROOT/'work/official-v20-combined';REL=ROOT/'official release'
FULL=REL/'PBZ-Gold-Alert-Official-V2.0-Combined-Fullpack';INS=REL/'PBZ-Gold-Alert-Official-V2.0-Combined-Installer'
DEV=ROOT/'outputs/PBZ-Gold-Alert-v2.0.5/Mod';PS=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def js(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sums(folder):
    expected={n.split('  ',1)[1]:n.split('  ',1)[0]for n in (folder/'SHA256SUMS.txt').read_text().splitlines()}
    assert expected.keys()=={p.relative_to(folder).as_posix()for p in folder.rglob('*')if p.is_file()and p.name!='SHA256SUMS.txt'}
    for n,h in expected.items():assert sha(folder/n)==h,n
    return len(expected)
def installer():
    out=B/'installer-extracted';assert not out.exists()
    with zipfile.ZipFile(REL/(INS.name+'.zip')) as z:
        assert z.testzip() is None
        assert not any(n.lower().endswith(('.exe','.zip','.7z','.gz','.rar'))for n in z.namelist())
        z.extractall(out)
    app=out/INS.name;inputs=sums(app);built=B/'reconstructed-triplet'
    args=[PS,'-NoProfile','-ExecutionPolicy','Bypass','-File',app/'Build-And-Install.ps1',
        '-GameExe',Path(r'G:\SteamLibrary\steamapps\common\PBZ\platform\steam\PBZ.exe'),'-BuildOnly','-OutputDirectory',built]
    print('Reconstructing unchanged V2.0.5 from the extracted Installer archive.',flush=True)
    p=subprocess.run(list(map(str,args)),capture_output=True);(B/'archive-build.log').write_bytes(p.stdout+p.stderr)
    assert p.returncode==0,(p.stdout,p.stderr)
    assert {p.name for p in built.iterdir()}=={p.name for p in DEV.iterdir()}
    result={}
    for f in built.iterdir():
        result[f.name]=sha(f);assert result[f.name]==sha(DEV/f.name)==sha(FULL/'Mod'/f.name)
    assert not list(app.glob('.build-*'))
    js(B/'installer-validation.json',dict(archive_integrity=True,extracted_checksum_files=inputs,build_only=True,
        three_file_hashes_exact_development_V205_and_fullpack=result,no_component_split=True,temporary_build_cleaned=True,
        no_real_game_installation_command_run=True))
    print('Installer reconstructs the original three hashes exactly.',flush=True)
def fixture():
    t=B/'installer-fixture';app=t/'installer';game=t/'game';paks=game/'ProjectPBZ/Content/Paks';mods=paks/'~mods'
    assert not t.exists();app.mkdir(parents=True);mods.mkdir(parents=True)
    for n in ['Extract.cs','Build-And-Install.ps1','Select-Game.ps1','oo2core_9_win64.dll','key.txt']:shutil.copyfile(INS/n,app/n)
    (game/'PBZ.exe').write_bytes(b'isolated fixture')
    cid='010203040506070800000002';base=bytes(range(64));toc=bytearray(178)
    struct.pack_into('<I',toc,24,1);struct.pack_into('<I',toc,44,64);struct.pack_into('<Q',toc,88,2**60)
    toc[144:156]=bytes.fromhex(cid);toc[161:166]=(64).to_bytes(5,'big');toc[171:174]=toc[174:177]=(64).to_bytes(3,'little')
    (paks/'ProjectPBZ-Windows.utoc').write_bytes(toc)
    key=bytes.fromhex((app/'key.txt').read_text().strip());(paks/'ProjectPBZ-Windows.ucas').write_bytes(AES.new(key,AES.MODE_ECB).encrypt(base))
    r=json.loads((INS/'recipe.json').read_text());r['base_toc_sha256']=sha(paks/'ProjectPBZ-Windows.utoc')
    prefix=b'PREFIX';patch=b'XYZ';tail=b'TAIL';payload=prefix+patch+tail;(app/'payload.bin').write_bytes(payload)
    target=prefix+base[:5]+patch+base[8:]+tail
    r['parts']=[dict(kind='literal',payload_offset=0,bytes=6),dict(kind='base',cid=cid,base_bytes=64,target_bytes=68,tail=dict(payload_offset=9,bytes=4),patches=[dict(offset=5,payload_offset=6,bytes=3)])]
    r['files']={};expected={}
    for ext in ['.pak','.utoc','.ucas']:
        n='zz_PBZ_YellowAlert_P'+ext;data=target if ext=='.ucas'else ext.encode()
        if ext!='.ucas':(app/n).write_bytes(data)
        expected[n]=hashlib.sha256(data).hexdigest();r['files'][n]=dict(bytes=len(data),sha256=expected[n])
    js(app/'recipe.json',r)
    js(app/'inputs.json',{p.name:dict(bytes=p.stat().st_size,sha256=sha(p))for p in app.iterdir()if p.is_file()})
    old_names=[]
    for stem in ['zz_PBZ_YellowAlert_P','zz_PBZ_V20_SharedAudio_P','zz_PBZ_V20_AttackAlerts_P','zz_PBZ_V20_Gauntlet_P']:
        for ext in ['.pak','.utoc','.ucas']:
            n=stem+ext;old_names.append(n);(mods/n).write_bytes(('old '+n).encode())
    (mods/'unrelated.pak').write_bytes(b'other mod');other=sha(mods/'unrelated.pak')
    def state():return {p.name:sha(p)for p in mods.iterdir()if p.is_file()}
    original=state()
    command="& '"+str(app/'Build-And-Install.ps1')+"' -GameExe '"+str(game/'PBZ.exe')+"'"
    def invoke(success=True,extra=None,running=False):
        # Only the synthetic installation's process list is mocked; real PBZ is untouched.
        shim="function global:Get-Process { param([string]$Name,[string]$ErrorAction) return "+("@('fixture-running')" if running else '@()')+" }; "
        args=[PS,'-NoProfile','-ExecutionPolicy','Bypass','-Command',shim+(extra or command)+'; if ($null -ne $LASTEXITCODE) { exit $LASTEXITCODE }']
        p=subprocess.run(list(map(str,args)),capture_output=True)
        with (t/'test.log').open('ab') as f:f.write(p.stdout+p.stderr+b'\n')
        assert (p.returncode==0)==success,(p.returncode,p.stdout,p.stderr)
    invoke(success=False,running=True);assert state()==original
    invoke();assert state()==dict(expected,**{'unrelated.pak':other})
    backup,=list((game/'ModBackups').glob('PBZ*'))
    for n in old_names:assert sha(backup/n)==original[n]
    before=state();locked=mods/'zz_PBZ_YellowAlert_P.utoc'
    lock=t/'locked.ps1';lock.write_text("$lock=[IO.File]::Open('"+str(locked)+"',[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)\ntry { "+command+" } finally { $lock.Dispose() }",encoding='utf-8-sig')
    invoke(success=False,extra="& '"+str(lock)+"'");assert state()==before
    (paks/'ProjectPBZ-Windows.utoc').write_bytes(toc+b'x');invoke(success=False);assert state()==before
    (paks/'ProjectPBZ-Windows.utoc').write_bytes(toc);(app/'payload.bin').write_bytes(payload+b'tampered');invoke(success=False);assert state()==before
    assert not list(app.glob('.build-*'))
    js(B/'installer-fixture-validation.json',dict(old_split_nine_and_combined_triplet_backed_up=True,
        installs_exactly_three_files=True,unrelated_mod_preserved=True,partial_delete_failure_restores_originals=True,
        game_running_guard=True,unsupported_game_version_stops=True,tampered_payload_stops=True,
        synthetic_encrypted_base_and_patches_match=True,no_real_game_paths_mutated=True))
    print('Combined installation, split cleanup, backups, rollback and rejection guards verified in isolated fixture.',flush=True)
def fullpack():
    dest=B/'fullpack-extracted';assert not dest.exists();seven=Path('C:/Program Files/7-Zip/7z.exe');archive=REL/(FULL.name+'.7z')
    for verb,args in [('t',[]),('x',['-o'+str(dest)])]:
        p=subprocess.run(list(map(str,[seven,verb,archive,'-bsp0',*args])),capture_output=True)
        (B/('fullpack-'+verb+'.log')).write_bytes(p.stdout+p.stderr);assert p.returncode==0
    folder=dest/FULL.name;count=sums(folder);files=list((folder/'Mod').iterdir())
    assert len(files)==3 and {p.suffix for p in files}=={'.pak','.utoc','.ucas'}
    assert {p.suffix for p in folder.rglob('*')if p.is_file()}=={'.pak','.utoc','.ucas','.txt'}
    for p in files:assert sha(p)==sha(DEV/p.name)
    js(B/'fullpack-validation.json',dict(archive_integrity=True,extracted_checksum_files=count,
        pure_resource_triplet=True,byte_exact_original_development_V205=True,native_containers_not_repacked=True))
    print('Extracted Fullpack is the byte-exact original V2.0.5 triplet.',flush=True)
if __name__=='__main__':globals()[sys.argv[1]]()
