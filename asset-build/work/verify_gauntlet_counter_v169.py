"""Execute decoded original/patched guard graph under controlled combat inputs.

This checks real bytecode control flow, not Unreal's animation/physics runtime.
"""
import itertools,json
from pathlib import Path
from gauntlet_counter_v169 import ROOT,decode_functions

POWER='Bullet.Tag.Feature.Deflect.PowerAttack'
BLUE='Bullet.Tag.Feature.Deflect.CanDodgeAfterDeflect'
PREFIX='GameplayEvent.Ability.Action.TieKuangQuanTao.Gp.'

class VM:
    def __init__(self,functions,case,state=None):
        self.functions={x['function']:x for x in functions};self.case=case
        self.state=state if state is not None else {'Focus Radius':700.,'CanGetSpirit':True,
            'GpSuccessGameplay Tag':'gp-buff','GpSuccessSFX':'gp-audio','GpSuccessVFX':'gp-vfx',
            'Couter':'counter-timeline','Block_L':'block-left','Block_R':'block-right'}
        self.effects=[];self.locals={}
    def get(self,var):
        name=var.split('@')[0]
        return self.locals.get(name,self.state.get(name))
    def set(self,var,value):
        name=var.split('@')[0]
        if name in self.state or name in ('Target','Event Tag'):self.state[name]=value
        else:self.locals[name]=value
        return value
    def assign(self,node,value):
        if 'var' in node:return self.set(node['var'],value)
        assert node['op']=='42'
        parent=node['expr'];obj=self.value(parent)
        if obj is None:obj={};self.assign(parent,obj)
        obj[node['property'].split('@')[0]]=value
        return value
    def call(self,name,args):
        if name=='EqualEqual_GameplayTag':return args[0]==args[1]
        if name=='MakeLiteralGameplayTagContainer':return args[0]
        if name=='HasAnyMatchingTag':return bool(set(args[0]) & self.case['tags'])
        if name=='IsProjectile':return self.case['projectile']
        if name=='CanCounterAttack':return self.run('CanCounterAttack',{'TargetActor':args[0],'IsProjectile':args[1]})
        if name=='Subtract_DoubleDouble':return args[0]-args[1]
        if name=='FMax':return max(args)
        if name=='LessEqual_DoubleDouble':return args[0]<=args[1]
        if name=='GetCapsuleDistance2D':return self.case['distance']
        if name=='GetAvatarActorFromActorInfo':return 'avatar'
        if name=='BooleanOR':return bool(args[0] or args[1])
        if name=='HasMatchingGameplayTag':return False
        if name=='SelectFloat':return args[0] if args[2] else args[1]
        if name=='Get Bullet Instant Cost':return 1.
        if name in ('PlayTimeline','OnCounter','SuccessBuff','ModifyCharacterAttributeValue',
                    'SpawnSystemAttached','PBZPostEventAtLocation','AddLooseGameplayTag','Slomo'):
            self.effects.append((name,args))
            return None
        if name in ('GetAbilitySystemComponentFromActorInfo','GetOwningComponentFromActorInfo',
                    'GetWorldSubsystem','GetMotionWarpingComponentByActor','K2_GetRootComponent'):
            return name+'-object'
        if name=='K2_GetActorLocation':return (0.,0.,0.)
        if name=='AddOrUpdateWarpTargetFromComponent':return None
        raise ValueError(('unmodeled external function',name,args))
    def value(self,n):
        op=n['op']
        if 'var' in n:return self.get(n['var'])
        if 'literal' in n:return n['literal']
        if 'string' in n:return n['string']
        if 'call' in n:return self.call(n['call'],[self.value(a) for a in n['args']])
        if op in ('14','0f','5f','60'):return self.assign(n['variable'],self.value(n['value']))
        if op=='21':return n['name']
        if op=='20':return n['object']
        if op=='17':return 'self'
        if op in ('2a','0b'):return None
        if op=='52':return 'bullet' if self.case['valid_bullet'] else None
        if op=='38':
            x=self.value(n['expr'])
            return bool(x) if n['cast']==2 else float(x)
        if op in ('51','6b','6d'):return self.value(n['expr'])
        if op=='42':return self.value(n['expr']).get(n['property'].split('@')[0])
        if op in ('19','1a','12'):
            self.value(n['object']);return self.value(n['expr'])
        if op=='2f':
            v=[self.value(x) for x in n['values']]
            return v[0] if n['struct'] in ('GameplayTag','GameplayTagContainer') else v
        if op=='65':return [self.value(x) for x in n['values']]
        if op=='69':
            v=self.value(n['index'])
            return next((self.value(c['value']) for c in n['cases'] if self.value(c['match'])==v),self.value(n['default']))
        raise ValueError(('unmodeled expression',n))
    def run(self,name,inputs):
        previous=self.locals;self.locals=dict(inputs)
        nodes=self.functions[name]['expressions'];positions={n['offset']:i for i,n in enumerate(nodes)}
        stack=[];pc=0;result=None;steps=0
        while pc<len(nodes):
            steps+=1;assert steps<400,'unexpected bytecode loop'
            n=nodes[pc];op=n['op'];jump=None;stop=False
            if op=='4c':stack.append(n['jump'])
            elif op=='4e':jump=self.value(n['expr'])
            elif op=='06':jump=n['jump']
            elif op=='07':
                if not self.value(n['condition']):jump=n['jump']
            elif op=='4d':
                if stack:jump=stack.pop()
                else:stop=True
            elif op=='4f':
                if not self.value(n['expr']):
                    if stack:jump=stack.pop()
                    else:stop=True
            elif op=='04':result=self.value(n['expr']);stop=True
            elif op=='53':stop=True
            else:self.value(n)
            if stop:break
            pc=positions[jump] if jump is not None else pc+1
        self.locals=previous
        return result
    def event(self,event):
        name=next(k for k in self.functions if k.startswith('ExecuteUbergraph_'))
        self.run(name,{'EntryPoint':0xc78,'K2Node_CustomEvent_Payload':{
            'Target':'attacker','OptionalObject':'bullet','EventTag':PREFIX+event}})
        return self.effects

def verify(before,after):
    cases=[]
    for power,blue,projectile,valid,event,distance in itertools.product(
            (False,True),(False,True),(False,True),(False,True),
            ('Success','Normal','PreAttack','ContinuousDeflect'),(0.,599.,600.,601.,10000.)):
        tags=({POWER} if power else set())|({BLUE} if blue else set())
        case=dict(tags=tags,projectile=projectile,valid_bullet=valid,distance=distance)
        old=VM(before,case);new=VM(after,case)
        a=old.event(event);b=new.event(event)
        count=sum(n=='PlayTimeline' and args[0]=='counter-timeline' for n,args in b)
        if power and valid and event=='Success':assert count==1,(case,event,b)
        if not power or event!='Success' or not valid:assert a==b,(case,event,a,b)
        # Grant/refund semantics must survive even when a counter is newly enabled.
        for call in ('SuccessBuff','ModifyCharacterAttributeValue'):
            assert [(n,x) for n,x in a if n==call]==[(n,x) for n,x in b if n==call]
        cases.append(dict(power=power,blue=blue,projectile=projectile,valid_bullet=valid,
            event=event,distance=distance,counter_count=count))
    repeat=VM(after,dict(tags={POWER},projectile=True,valid_bullet=True,distance=10000.))
    repeat.event('Success');repeat.event('Success')
    assert sum(n=='ModifyCharacterAttributeValue' for n,_ in repeat.effects)==1
    assert sum(n=='PlayTimeline' and a[0]=='counter-timeline' for n,a in repeat.effects)==2
    return dict(bytecode_control_flow_cases=len(cases),
        black_success_all_distances_and_projectile_variants_counter_once=True,
        non_black_and_non_success_effects_equal_original=True,
        spirit_refund_and_fist_buff_calls_equal_original=True,
        repeated_contacts_no_duplicate_spirit_refund=True,
        game_engine_animation_and_physics_not_simulated=True)

if __name__=='__main__':
    _,before=decode_functions(ROOT/'work/gauntlet-parry-investigation/assets/GA_TieKuangQuanTao_GuardPoint.uasset')
    _,after=decode_functions(ROOT/'work/gold-alert-v169/GA_TieKuangQuanTao_GuardPoint.uasset')
    result=verify(before,after)
    (ROOT/'work/gold-alert-v169/gauntlet-flow-validation.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2))
