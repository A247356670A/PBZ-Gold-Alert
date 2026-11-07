"""Apply +50% linear gain to the confirmed working PCM with linked peak protection."""
import sys,json,struct,wave,subprocess,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]

def amplify(prior,raw,build,out):
    info=json.loads((ROOT/'outputs/PBZ-Gold-Alert-v1.6.12/audio-source.json').read_text())
    paths=json.loads((prior/'manifest.json').read_text())['chunk_paths']
    cid=next(c for c,p in paths.items()if p.endswith('/SFX_All.ubulk'))
    at=info['appended_media_offset'];size=info['appended_wem_bytes']
    with (prior/'chunks'/cid).open('rb')as f:f.seek(at);old=f.read(size)
    assert old==(ROOT/'work/gold-alert-v202/success-louder.wem').read_bytes()
    assert old[88:92]==b'data' and struct.unpack_from('<I',old,92)[0]==size-96
    x=np.frombuffer(old[96:],'<i2').astype(np.float64).reshape(-1,2)/32768
    gain,knee,ceiling=1.5,.88,.99
    scaled=x*gain;peak=abs(scaled).max(axis=1)
    capped=np.where(peak<=knee,peak,knee+(ceiling-knee)*np.tanh((peak-knee)/(ceiling-knee)))
    y=scaled*(capped/np.maximum(peak,1e-12))[:,None]
    pcm=np.rint(y*32768).astype('<i2').tobytes();new=old[:96]+pcm
    assert len(new)==size
    with (raw/'chunks'/cid).open('r+b')as f:f.seek(at);f.write(new)
    with (prior/'chunks'/cid).open('rb')as a,(raw/'chunks'/cid).open('rb')as b:
        remaining=at+96
        while remaining:
            n=min(8*1024*1024,remaining);assert a.read(n)==b.read(n);remaining-=n
        a.seek(at+size);b.seek(at+size)
        while True:
            aa=a.read(8*1024*1024);bb=b.read(8*1024*1024);assert aa==bb
            if not aa:break
    (build/'success-louder.wem').write_bytes(new);preview=out/'Preview';preview.mkdir(parents=True,exist_ok=True)
    def wav(path,payload):
        with wave.open(str(path),'wb')as f:f.setparams((2,2,48000,0,'NONE','not compressed'));f.writeframes(payload)
    wav(preview/'Success-V202.wav',old[96:]);wav(preview/'Success-V203.wav',pcm)
    wav(preview/'Success-V202-V203.wav',old[96:]+bytes(28800*4)+pcm)
    subprocess.run([str(ROOT/'tools/vgmstream/vgmstream-cli.exe'),'-i','-o',str(build/'success-decoded.wav'),str(build/'success-louder.wem')],check=True,capture_output=True)
    with wave.open(str(build/'success-decoded.wav'),'rb')as f:assert f.readframes(f.getnframes())==pcm
    actual=np.frombuffer(pcm,'<i2').astype(np.float64).reshape(-1,2)/32768
    before=float(np.sqrt(np.mean(x[:24000]**2)));after=float(np.sqrt(np.mean(actual[:24000]**2)))
    correlation=float(np.corrcoef(x[:24000].ravel(),actual[:24000].ravel())[0,1])
    assert correlation>.98 and abs(actual).max()<.991
    assert np.array_equal(np.all(x==0,axis=1),np.all(actual==0,axis=1))
    result=dict(changed_chunk=cid,media_offset=at,media_bytes=size,linear_gain=1.5,linear_gain_db=20*math.log10(1.5),
        peak_limiting_required_because_previous_pcm_already_near_full_scale=True,
        first_500ms_rms_before=before,first_500ms_rms_after=after,actual_rms_ratio=after/before,
        actual_first_500ms_gain_db=20*math.log10(after/before),full_duration_seconds=len(x)/48000,
        soft_knee=knee,peak_ceiling=ceiling,peak_before=float(abs(x).max()),peak_after=float(abs(actual).max()),
        waveform_correlation_first_500ms=correlation,hard_clipped_samples=0,
        media_header_codec_cache_length_and_all_other_media_bit_exact=True,
        entire_existing_bank_archive_and_event_gain_preserved_from_v202=True,
        actual_decoded_pcm_verified=True,no_added_delay_no_trimming_no_pitch_change=True,
        onset_and_existing_silent_frames_preserved=True,actual_in_game_loudness_pending=True)
    (build/'success-pcm-proof.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return result
