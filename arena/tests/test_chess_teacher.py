"""Teacher distillation uses real chess while remaining ineligible for PG RL."""
import asyncio
from copy import deepcopy

import pytest
import blink_arena.engine
from jev_chess_rl import play_teacher, verify_teacher, verify, verify_evaluation


class Teacher:
    async def policy_action(self, record, episode_id, ordinal):
        action = {1:'e7e5', 3:'d8h4'}[ordinal]
        return action, {'forced':False, 'origin':'teacher', 'teacher_model':'fixture-teacher',
                        'served_model':'fixture-teacher', 'on_policy':False}

    async def qwen(self, kind, seed, ordinal, record):
        return {0:'f2f3', 2:'g2g4'}[ordinal], {'forced':False}


def result():
    job={'kind':'chess','seed':0,'side':1,'mode':'qwen3.8-max','episode_id':'teacher-fixture'}
    return job, asyncio.run(play_teacher(Teacher(),job))


def test_native_teacher_checkmate_and_exact_replay():
    job,(initial,final,trace,outcome,extra)=result()
    assert outcome=='win' and final['termination']=='checkmate'
    assert extra['teacher_distillation'] and extra['reward_export_prohibited']
    assert extra['policy_origin']=='teacher' and extra['on_policy'] is False
    assert extra['teacher_policy_requests']==2 and 'student_policy_requests' not in extra
    assert verify_teacher(job,initial,final,extra,trace)
    for verifier in (verify,verify_evaluation):
        with pytest.raises(ValueError):verifier(job,initial,final,extra,trace)


@pytest.mark.parametrize('corruption',['actor','action','policy','final'])
def test_teacher_replay_rejects_tampering(corruption):
    job,(initial,final,trace,outcome,extra)=result()
    if corruption=='actor':extra['events'][1]['actor']=0
    elif corruption=='action':trace[0]['action']='a7a6'
    elif corruption=='policy':extra['events'][1]['policy']['served_model']='another-model'
    else:final=deepcopy(final);final['termination']='resignation'
    with pytest.raises(ValueError):verify_teacher(job,initial,final,extra,trace)
