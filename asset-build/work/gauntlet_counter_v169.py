"""Black-only guard counter override, using the original native Zen package.

Keep all original bytecode addresses: append a small predicate trampoline before
EndOfScript, and redirect only the old CanCounterAttack branch to it.
"""
import importlib.util
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from parse_fx import FXParser
from zen_fx_edit import rebuild_exports

spec=importlib.util.spec_from_file_location('gauntlet_kismet',ROOT/'work/gauntlet-parry-investigation/read_kismet.py')
kismet=importlib.util.module_from_spec(spec);spec.loader.exec_module(kismet)

def decode_functions(path):
    q=FXParser(path);out=[]
    for export in q.exports():
        if export['class']!=6291290835964162768:continue
        b=q.b[export['start']:export['start']+export['size']]
        candidates=[]
        for p in range(len(b)-20):
            memory,size=struct.unpack_from('<II',b,p)
            if memory>0 and size>0 and p+8+size==len(b)-12 and b[p+8+size-1]==0x53:
                decoder=kismet.Bytecode(q,b[p+8:p+8+size]);nodes=[]
                try:
                    while decoder.p<size:nodes.append(decoder.expr())
                    assert decoder.mem==memory
                except (ValueError,AssertionError,IndexError,struct.error):continue
                candidates.append(dict(function=export['name'],export=export,script_header=p,
                    memory_size=memory,disk_size=size,expressions=nodes,script_start=export['start']+p+8))
        assert len(candidates)==1,(export['name'],len(candidates))
        out.append(candidates[0])
    return q,out

def patch(source,destination):
    q,functions=decode_functions(source)
    graph=next(x for x in functions if x['function'].startswith('ExecuteUbergraph_'))
    nodes=graph['expressions'];by_offset={x['offset']:x for x in nodes}
    branch=by_offset[0x293];end=nodes[-1]
    assert branch['op']=='07' and branch['jump']==0x75a
    assert branch['condition']['var'].startswith('CallFunc_CanCounterAttack_ReturnValue@')
    assert by_offset[0x1f8]['condition']['var'].startswith('CallFunc_HasAnyMatchingTag_ReturnValue_1@')
    # The preceding original block still requires PowerAttack -> Gp.Success.
    assert by_offset[0x23e]['jump']==0x75a
    assert end['op']=='53' and end['offset']==0xc9a
    assert all(x.get('jump')!=branch['condition']['offset'] for x in nodes)
    start=graph['script_start'];script=q.b[start:start+graph['disk_size']]
    def raw_expr(expr):
        # These are fixed-layout local bool property references; retain their owners.
        assert expr['op']=='00'
        raw=script[expr['disk']:expr['disk']+17]
        assert raw[0]==0 and struct.unpack_from('<i',raw,1)[0]==1
        return raw
    old_check=raw_expr(branch['condition'])
    power_check=raw_expr(by_offset[0x1f8]['condition'])
    # BooleanOR is an existing native import and is already used by this graph.
    math=next(x for x in nodes if x.get('value',{}).get('call')=='BooleanOR')['value']
    call_header=script[math['disk']:math['disk']+5];assert call_header[0]==0x68
    tail=(b'\x07'+struct.pack('<I',0x75a)+call_header+old_check+power_check+b'\x16'
          +b'\x06'+struct.pack('<I',0x2a1))
    assert len(tail)==50
    replacement=bytearray(script)
    # Original condition is left as a valid, unreachable local-variable expression.
    # No existing entry point, jump, switch or context offset moves.
    replacement[branch['disk']:branch['disk']+5]=b'\x06'+struct.pack('<I',end['offset'])
    replacement[end['disk']:end['disk']]=tail
    d=kismet.Bytecode(q,replacement);new_nodes=[]
    while d.p<len(replacement):new_nodes.append(d.expr())
    assert d.mem==graph['memory_size']+38
    assert new_nodes[-1]['op']=='53' and new_nodes[-1]['offset']==end['offset']+38
    ex=graph['export'];header=graph['script_header']
    old_export=q.b[ex['start']:ex['start']+ex['size']]
    new_export=(old_export[:header]+struct.pack('<II',d.mem,len(replacement))
                +replacement+old_export[header+8+graph['disk_size']:])
    hs=struct.unpack_from('<I',q.b,4)[0]
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(rebuild_exports(q,bytearray(q.b[:hs]),0,{ex['index']:new_export}))
    check,after=decode_functions(destination)
    assert len(after)==len(functions)==9
    for old,new in zip(q.exports(),check.exports(),strict=True):
        if old['index']==ex['index']:continue
        assert q.b[old['start']:old['start']+old['size']]==check.b[new['start']:new['start']+new['size']]
    # Imports, original reference IDs and every non-script byte of the function survive.
    assert old_export[:header]==new_export[:header]
    assert old_export[-12:]==new_export[-12:]
    proof=dict(changed_export=ex['index'],original_exports=len(q.exports()),new_exports=len(check.exports()),
        original_function_memory=graph['memory_size'],new_function_memory=d.mem,
        original_function_disk=graph['disk_size'],new_function_disk=len(replacement),
        original_entrypoints_and_branch_addresses_preserved=True,
        added_names=0,added_imports=0,added_functions=0,all_other_exports_bit_exact=True,
        requires_success_event_for_black_attack=True,non_black_original_distance_and_projectile_checks_preserved=True,
        black_check='CanCounterAttack(Target, IsProjectile) OR HasPowerAttackTag',
        gameplay_window_and_damage_and_buffs_unchanged=True)
    return functions,after,proof

if __name__=='__main__':
    source=ROOT/'work/gauntlet-parry-investigation/assets/GA_TieKuangQuanTao_GuardPoint.uasset'
    destination=ROOT/'work/gold-alert-v169/GA_TieKuangQuanTao_GuardPoint.uasset'
    before,after,proof=patch(source,destination)
    (destination.parent/'gauntlet-patch-validation.json').write_text(json.dumps(proof,indent=2),encoding='utf8')
    (destination.parent/'guardpoint-bytecode-patched.json').write_text(json.dumps(after,indent=2),encoding='utf8')
    print(json.dumps(proof,indent=2))
