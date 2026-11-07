"""Native depth-off material and a measured increase of the actual warning PCM."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from parse_fx import FXParser
from zen_fx_edit import append_names,read_fields,encode_fields,raw_field,object_bytes,rebuild_exports
from restore_black_post_v162 import read_name_batch,name_batch
from investigate_black_timing import prefix_field
from inspect_fx_vm import scripts
from read_pbz import Reader

MATERIAL='/PBZVFXPack/VFX/A_Materials/Common/AddMaster_001/MI_FX_A1_Glow_011_Nd'
MONSTER='e769c85cabe3aa8400000001'
MONSTER_BULK='e769c85cabe3aa8400000002'


def depth_off(destination):
    q=FXParser(destination);ex=q.exports()
    header,delta,names=append_names(q,['DepthFade'])
    scalar=object_bytes({0:struct.pack('<II',names['DepthFade'],0),1:struct.pack('<f',0)})
    params=object_bytes({1:struct.pack('<I',1)+scalar})
    replacements={}
    for i in [21,22]:
        e=ex[i];q.p=e['start'];fields=read_fields(q,'NiagaraSpriteRendererProperties');end=q.p
        assert fields[0]['value']==-34 and 48 not in fields
        fields[48]=raw_field(params)
        replacements[i]=encode_fields(fields)+q.b[end:e['start']+e['size']]
    stage=destination.parent.parent/'post-depth-stage.uasset';stage.write_bytes(rebuild_exports(q,header,delta,replacements))
    s=FXParser(stage);b=bytearray(s.b)
    package_at=struct.unpack_from('<I',b,48)[0];hs=struct.unpack_from('<I',b,4)[0]
    packages,version,end=read_name_batch(b,package_at)
    assert len(packages)==4 and packages[3]==MATERIAL.replace('_Nd','_B')
    # Take identity from the current game's real cooked material, not an invented import.
    reader=Reader();rows=json.loads((ROOT/'analysis/build-20261105/asset-index.json').read_text())
    row=next(x for x in rows if x['path'].endswith('/MI_FX_A1_Glow_011_Nd.uasset'))
    cid=reader.toc[144+row['index']*12:144+(row['index']+1)*12]
    pid=int.from_bytes(cid[:8],'little')
    mat=reader.read(row['index'])
    public_hash=struct.unpack_from('<Q',mat,struct.unpack_from('<I',mat,32)[0]+56)[0]
    hash_at=struct.unpack_from('<I',b,24)[0];imports_at=struct.unpack_from('<I',b,28)[0]
    assert imports_at-hash_at==5*8
    assert struct.unpack_from('<Q',b,imports_at+33*8)[0]==0x8000000300000004
    struct.pack_into('<Q',b,hash_at+4*8,public_hash)
    packages[3]=MATERIAL
    new=bytearray(b[:package_at]+name_batch(packages,version)+b[end:hs])
    struct.pack_into('<I',new,4,len(new));new.extend(b[hs:]);destination.write_bytes(new)
    c=FXParser(destination);assert len(c.exports())==24
    for old,now in zip(ex,c.exports(),strict=True):
        if old['index']not in replacements:
            assert q.b[old['start']:old['start']+old['size']]==c.b[now['start']:now['start']+now['size']]
    for i in [21,22]:
        c.p=c.exports()[i]['start'];v=c.obj('NiagaraSpriteRendererProperties')
        p,=v['MaterialParameters']['ScalarParameters'];assert p['MaterialParameterName']=='DepthFade' and p['Value']==0
        assert v['Material']==-34
    for old,now in zip(scripts(stage),scripts(destination),strict=True):assert old[3]==now[3]
    root=FXParser(ROOT/'work/material-depth-investigation/M_FX_AddMaster_001_DepthOff.uasset')
    assert prefix_field(root,'Material','bDisableDepthTest')['value']==1
    return {'material_path':MATERIAL,'material_package_id':pid,'material_public_export_hash':public_hash,
            'compiled_root_material_disable_depth_test':True,'both_sprite_depth_fade':0,
            'native_export_count':24,'no_new_components_or_packages':True,
            'all_non_renderer_exports_bit_exact_after_resize':True}


def amplify(prior,raw,build,out):
    import numpy as np
    old=(prior/'chunks'/MONSTER_BULK).read_bytes()
    q=FXParser(prior/'chunks'/MONSTER)
    table=q.name_end+16+struct.unpack_from('<Q',q.b,q.name_end)[0]
    offset,_,length,flags,index=struct.unpack_from('<qqqIB3x',q.b,table+145*32)
    assert (offset,length,flags,index)==(781392768,396896,66817,0)
    wem=old[offset:offset+length]
    assert wem==(ROOT/'work/gold-alert-v161/purple-warning.wem').read_bytes()
    assert wem[:4]==b'RIFF'and wem[88:92]==b'data'and struct.unpack_from('<I',wem,92)[0]==len(wem)-96
    samples=np.frombuffer(wem[96:],'<i2').astype(np.float64)/32768
    before=float(np.sqrt(np.mean(samples**2)))
    knee,cap=.82,.96
    def limited(gain):
        a=np.abs(samples)*gain
        a=np.where(a<=knee,a,knee+(cap-knee)*np.tanh((a-knee)/(cap-knee)))
        return np.copysign(a,samples)
    low,high=1.,8.
    for _ in range(60):
        mid=(low+high)/2
        if np.sqrt(np.mean(limited(mid)**2))<2*before:low=mid
        else:high=mid
    pcm=np.rint(limited((low+high)/2)*32768).astype('<i2').tobytes()
    after=np.frombuffer(pcm,'<i2').astype(np.float64)/32768
    ratio=float(np.sqrt(np.mean(after**2))/before)
    assert abs(ratio-2)<.00001 and np.max(np.abs(after))<.961
    replacement=wem[:96]+pcm;assert len(replacement)==length
    changed=old[:offset]+replacement+old[offset+length:]
    assert changed[:offset+96]==old[:offset+96] and changed[offset+length:]==old[offset+length:]
    (raw/'chunks'/MONSTER_BULK).write_bytes(changed)
    (build/'purple-warning.wem').write_bytes(replacement)
    preview=out/'Preview';preview.mkdir(exist_ok=True)
    def write_wav(path,payload):
        with wave.open(str(path),'wb')as f:
            f.setparams((2,2,48000,len(payload)//4,'NONE','not compressed'));f.writeframes(payload)
    write_wav(preview/'Purple-Before.wav',wem[96:])
    write_wav(preview/'Purple-After.wav',pcm)
    write_wav(preview/'Volume-Comparison.wav',wem[96:]+b'\0'*(28800*4)+pcm)
    subprocess.run([str(ROOT/'tools/vgmstream/vgmstream-cli.exe'),'-i','-o',str(build/'decoded-check.wav'),str(build/'purple-warning.wem')],check=True,capture_output=True)
    with wave.open(str(build/'decoded-check.wav'),'rb')as f:
        assert (f.getnchannels(),f.getframerate(),f.getsampwidth())==(2,48000,2)
        assert f.readframes(f.getnframes())==pcm
    return {'actual_pcm_rms_ratio':ratio,'rms_before':before,'rms_after':float(np.sqrt(np.mean(after**2))),
            'peak_before':float(np.max(np.abs(samples))),'peak_after':float(np.max(np.abs(after))),
            'input_gain_before_peak_limiting':(low+high)/2,'soft_knee':knee,'peak_ceiling':cap,
            'hard_clipped_samples':int(np.sum(np.abs(after)>=1)),
            'bank_gain_preserved_from_v163':True,'wem_header_format_cache_and_duration_unchanged':True,
            'all_other_monster_bulk_bytes_exact':True,'independent_decoder_pcm_exact':True,
            'media_offset':offset,'media_length':length,'comparison_order':'v163 PCM, 600ms silence, new PCM'}
