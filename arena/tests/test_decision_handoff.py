"""A handoff conceals the next hand, not the completed model's probabilities."""
from copy import deepcopy
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import blink_arena  # Install the packaged legacy engine module paths.
import jev_demo_showcases as facade


@pytest.mark.parametrize('kind', ['doudizhu','texas_holdem','zha_jin_hua','property_tycoon','uno','liars_dice'])
def test_completed_decisions_survive_private_handoff_without_input_echo(kind):
    measured=[]
    async def predict(record,qid):
        options=record['questions'][qid]['criteria']
        action=next((a for a in ['call','check','buy','skip','next','roll'] if a in options),next(iter(options)))
        result={'value':action,'latency_seconds':.125,'model':'unit-model',
                'distribution':[{'value':a,'probability':1/len(options)} for a in options],
                'model_input':{'schema_input':deepcopy(record)}}
        measured.append(deepcopy(result));return result
    app=FastAPI();facade.install(app,'',lambda seq:None,predict,None)
    with TestClient(app) as client:
        s=client.post('/api/showcases/new',json={'kind':kind,'seed':42,'duel':True,'opponent':'human','view_seat':0}).json()
        seen_handoff=False;calls=0
        for _ in range(14):
            if s['world'].get('outcome'):break
            if s['world'].get('handoff'):
                r=client.post('/api/showcases/reveal',json={'session_id':s['session_id'],'revision':s['revision']})
                assert r.status_code==200,r.text
                s=r.json()
            count=len(measured)
            r=client.post('/api/showcases/step',json={'session_id':s['session_id'],'revision':s['revision'],'model':True})
            assert r.status_code==200,r.text
            s=r.json()
            if len(measured)>count:
                calls+=1
                assert s['result']=={k:v for k,v in measured[-1].items() if k!='model_input'}
                assert 'model_input' in measured[-1]  # No mutation of provider evidence.
                assert s['decision_timing']=={'latency_seconds':.125}
                assert s['previous_input'] is None
                if s['world'].get('handoff'):
                    seen_handoff=True
                    assert s['input'] is None and s['choices']=={}
            else:
                assert s['forced'] and s['result'] is None and s['decision_timing'] is None
            if calls>=2 and (seen_handoff or kind=='property_tycoon'):break
        assert calls>=2
        if kind!='property_tycoon':assert seen_handoff


def test_sealed_actions_still_hide_the_entire_decision():
    result={'value':'secret-bid','distribution':[{'value':'secret-bid','probability':1}],
            'model_input':{'private':'input'}}
    assert facade.display_decision_result(result,private=True,sealed=True) is None
    assert facade.display_decision_result(None,private=True) is None
    assert facade.display_decision_result(result) is result
