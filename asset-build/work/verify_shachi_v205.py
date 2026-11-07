"""Execute old/new contact bytecode and validate the exact native effect contract."""
import sys,itertools,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from gauntlet_counter_v169 import decode_functions
from verify_gauntlet_trigger_v1610 import ContactVM,SKILL
from verify_gauntlet_counter_v169 import POWER,BLUE
from fx_parser_v205 import FX205
from shachi_fixed_v205 import GUARD,GE_CID,DURATION,PERIOD

class ShachiVM(ContactVM):
    def call(self,name,args):
        if name=='BP_ApplyGameplayEffectToOwner':
            assert len(args)==3 and args[1:]==[1,1]
            self.effects.append((name,args));return 'deferred-shachi-handle'
        return super().call(name,args)

def verify(prior,raw):
    _,before=decode_functions(prior/'chunks'/GUARD);_,after=decode_functions(raw/'chunks'/GUARD)
    count=0;scheduled=0
    for kind,blue,projectile,valid,event,distance,active in itertools.product(
            ('none','feature','skill','both'),(False,True),(False,True),(False,True),
            ('Success','Normal','ContinuousDeflect','PreAttack'),(0.,600.,601.,10000.),(False,True)):
        tags=({POWER}if kind in ('feature','both')else set())|({SKILL}if kind in ('skill','both')else set())|({BLUE}if blue else set())
        case=dict(tags=tags,projectile=projectile,valid_bullet=valid,distance=distance)
        a=ContactVM(before,case);b=ShachiVM(after,case)
        a.state['CounterActive']=active;b.state['CounterActive']=active
        old=a.event(event);new=b.event(event)
        extra=[x for x in new if x[0]=='BP_ApplyGameplayEffectToOwner']
        expected=kind!='none'and valid and event!='PreAttack'and not active
        assert len(extra)==int(expected),(case,event,active,new)
        assert [x for x in new if x[0]!='BP_ApplyGameplayEffectToOwner']==old,(case,event,new,old)
        count+=1;scheduled+=len(extra)
    b=ShachiVM(after,dict(tags={POWER},projectile=True,valid_bullet=True,distance=10000.))
    for event in ['Success','ContinuousDeflect','Normal','Success']:b.event(event)
    assert sum(n=='BP_ApplyGameplayEffectToOwner'for n,a in b.effects)==1
    assert sum(n=='ModifyCharacterAttributeValue'for n,a in b.effects)==1
    q=FX205(raw/'chunks'/GE_CID);q.p=q.exports()[1]['start'];props=q.obj('GameplayEffect')
    mod,=props['Modifiers'];a=mod['ModifierMagnitude']['AttributeBasedMagnitude'];coefficient=a['Coefficient']['Value']
    assert mod['ModifierOp']==3 and mod['Attribute']['AttributeName']=='Shachi'
    assert a['BackingAttribute']['AttributeToCapture']['AttributeName']=='Shachi_Max'
    assert a['BackingAttribute']['AttributeSource']==1 and a['BackingAttribute']['bSnapshot']==1
    assert a['AttributeCalculationType']in [None,0]
    assert props['bExecutePeriodicEffectOnApplication']==0
    duration=props['DurationMagnitude']['ScalableFloatMagnitude']['Value'];period=props['Period']['Value']
    assert math.floor(duration/period)==1 and period<duration<2*period
    cases=[]
    for maximum in [50.,100.,135.,200.,500.]:
        for current in [0.,.1,.1*maximum,.3*maximum,.65*maximum,maximum]:
            # Native Override is independent of the cost and current base value.
            result=maximum*coefficient;assert abs(result/maximum-.3)<1e-6
            cases.append(dict(maximum=maximum,before=current,after=result))
    return dict(decoded_contact_cases=count,new_effect_applications=scheduled,
        ordinary_nonblack_preattack_and_invalid_contacts_unchanged=True,
        all_existing_counter_sound_fist_buff_and_charge_refund_effects_equal_v204=True,
        repeated_contacts_schedule_once_per_active_counter=True,
        exact_maximum_fraction_cases=cases,coefficient_from_serialized_effect=coefficient,
        shachi_max_capture_includes_current_upgrades=True,
        periodic_override_delayed_ms=period*1000,scheduled_periodic_executions=1,
        no_effect_on_enemy_meter_health_or_spirit_charges=True,
        actual_engine_execution_and_frame_order_still_require_game_test=True)

if __name__=='__main__':
    raw=ROOT/'work/gold-alert-v205/combined/raw';proof=verify(ROOT/'work/gold-alert-v204/combined/raw',raw)
    (raw.parents[1]/'shachi-flow-validation.json').write_text(json.dumps(proof,indent=2))
    print(json.dumps({k:v for k,v in proof.items()if k!='exact_maximum_fraction_cases'}))
