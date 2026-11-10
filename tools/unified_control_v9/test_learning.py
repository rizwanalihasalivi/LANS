import numpy as np
from tools.unified_campaign.study import make_case
from .learning import MatchedEnv,run_episode
from .control import Controller

PARAMS=dict(quality_factor=1.,guard_factor=1.,nominal_feedback=True,planner_backend='logical')

class Constant:
    def predict(self,observation,deterministic=True):return np.array([.4]),None


def test_training_and_evaluation_delay_cadence_have_identical_actual_commands(tmp_path):
    case=make_case('development',0);case.update(npc_x_shift=1.,npc_speed_scale=.9)
    trace=tmp_path/'trace.jsonl'
    env=MatchedEnv(Controller,PARAMS,trace);obs,_=env.reset(seed=42,options=dict(case=case))
    actions=[];infos=[]
    for _ in range(6):
        obs,reward,done,truncated,info=env.step(np.array([.4]));actions.append((env.pipe.applied.steering,env.pipe.applied.accel));infos.append(info)
        assert obs.shape==(17,) and np.isfinite(obs).all() and np.isfinite(reward)
    env.close()
    import json
    logged=[json.loads(line) for line in trace.read_text().splitlines()]
    assert len(logged)==6 and len(logged[0]['state_after'])==6 and len(logged[0]['observation'])==17
    _,rows=run_episode(case,'hybrid',Constant(),seconds=.3,controller_factory=Controller,controller_kwargs=PARAMS)
    np.testing.assert_allclose(actions,[(r['applied_steering'],r['applied_accel']) for r in rows],rtol=0,atol=1e-12)
    assert infos[0]['decision_proposal_age'] is None
    assert infos[1]['decision_proposal_age']==.05


def test_missing_observation_is_finite_but_does_not_submit_fabricated_observation():
    case=make_case('development',0)
    env=MatchedEnv(Controller,PARAMS);env.reset(seed=1,options=dict(case=case))
    env.pipe.inbox.latest.clear();obs=env._observation()
    assert np.array_equal(obs,np.zeros(17)) and not env.observation_valid
    _,_,_,_,info=env.step(np.array([.9]))
    assert not info['submitted'];env.close()
