"""Exercise actual contact event names, native timeline lookup and reentry."""
import itertools,json
from gauntlet_counter_v169 import ROOT,decode_functions
from verify_gauntlet_counter_v169 import VM,POWER,BLUE,PREFIX
from parse_fx import FXParser

SKILL='Bullet.SkillType.PowerAttack'
class ContactVM(VM):
    def call(self,name,args):
        if name=='GetTimelineByName':
            assert args==['Couter'];return 'counter-timeline'
        if name=='IsPlayingTimeline':return self.state.get('CounterActive',False)
        result=super().call(name,args)
        if name=='PlayTimeline' and args[0]=='counter-timeline':self.state['CounterActive']=True
        return result

def verify(before,after):
    count=0
    for kind,blue,projectile,valid,event,distance,missing_timeline in itertools.product(
            ('none','feature','skill','both'),(False,True),(False,True),(False,True),
            ('Success','Normal','ContinuousDeflect','PreAttack'),(0.,600.,601.,10000.),(False,True)):
        tags=({POWER} if kind in ('feature','both') else set())|({SKILL} if kind in ('skill','both') else set())|({BLUE} if blue else set())
        case=dict(tags=tags,projectile=projectile,valid_bullet=valid,distance=distance)
        a=ContactVM(before,case);b=ContactVM(after,case)
        if missing_timeline:a.state['Couter']=None;b.state['Couter']=None
        x=a.event(event);y=b.event(event)
        counters=[args for name,args in y if name=='PlayTimeline' and args[0]=='counter-timeline']
        if kind!='none' and valid and event!='PreAttack':assert len(counters)==1,(case,event,y)
        if kind=='none' or not valid or event=='PreAttack':assert x==y,(case,event)
        for name in ['SuccessBuff','ModifyCharacterAttributeValue']:
            assert [z for z in x if z[0]==name]==[z for z in y if z[0]==name]
        count+=1
    # Read the actual six inline frame event properties, including continuous guard.
    q=FXParser(ROOT/'work/gauntlet-parry-investigation/assets/GA_TieKuangQuanTao_GuardPoint.uasset')
    events=[]
    for i in range(17,23):
        q.p=q.exports()[i]['start'];v=q.obj('GAA_DeflectFrame_C')
        event=v['Impact Event']['TagName'];assert event.startswith(PREFIX)
        vm=ContactVM(after,dict(tags={POWER},projectile=False,valid_bullet=True,distance=10000.))
        vm.state['Couter']=None
        vm.event(event.removeprefix(PREFIX))
        assert sum(n=='PlayTimeline' and a[0]=='counter-timeline' for n,a in vm.effects)==1
        events.append(dict(inline_export=i,impact_event=event,counter_triggered=True))
    vm=ContactVM(after,dict(tags={POWER},projectile=True,valid_bullet=True,distance=10000.))
    vm.event('Normal');vm.event('ContinuousDeflect');vm.event('Success')
    assert sum(n=='PlayTimeline' and a[0]=='counter-timeline' for n,a in vm.effects)==1
    assert sum(n=='ModifyCharacterAttributeValue' for n,a in vm.effects)==1
    return dict(contact_control_flow_cases=count,actual_inline_frames=events,
        missing_cached_timeline_resolved_by_native_lookup=True,
        normal_and_continuous_black_contacts_now_counter=True,
        original_nonblack_and_preattack_behavior_preserved=True,
        active_counter_not_restarted=True,refund_not_repeated=True,
        actual_engine_trigger_not_yet_verified=True)

if __name__=='__main__':
    _,a=decode_functions(ROOT/'work/gauntlet-parry-investigation/assets/GA_TieKuangQuanTao_GuardPoint.uasset')
    _,b=decode_functions(ROOT/'work/gold-alert-v1610/GA_TieKuangQuanTao_GuardPoint.uasset')
    proof=verify(a,b);(ROOT/'work/gold-alert-v1610/contact-flow-validation.json').write_text(json.dumps(proof,indent=2))
    print(json.dumps(proof,indent=2))
