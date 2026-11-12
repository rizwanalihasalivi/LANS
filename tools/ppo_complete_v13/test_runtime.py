import json,time
from types import SimpleNamespace
import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pytest
from .runtime import PolicyWorker,RuntimeAction,fresh,load_policy,owner_tick,sha

CONTRACT='v13-current-anchor55-correction8-finite120-v1'


class TinyEnv(gym.Env):
    def __init__(self):
        self.observation_space=spaces.Box(-5.,5.,(55,),np.float32)
        self.action_space=spaces.Box(-1.,1.,(8,),np.float32);self.tick=0
    def reset(self,*,seed=None,options=None):
        super().reset(seed=seed);self.tick=0;return np.zeros(55,np.float32),{}
    def step(self,action):
        self.tick+=1
        return np.full(55,self.tick/10,np.float32),float(1-np.sum(action**2)),self.tick==2,False,{}


@pytest.fixture(scope='module')
def folder(tmp_path_factory):
    import torch
    from .learner import IndependentPPO
    torch.set_num_threads(1);path=tmp_path_factory.mktemp('v13-runtime')
    env=TinyEnv();model=IndependentPPO('MlpPolicy',env,n_steps=8,batch_size=4,n_epochs=1,seed=42,device='cpu')
    model.save(path/'bc-policy.zip');model.learn(total_timesteps=16);model.save(path/'policy.zip');env.close()
    record=dict(contract=CONTRACT,observation_dim=55,action_dim=8,learner_class='IndependentPPO',
        policy_sha256=sha(path/'policy.zip'),bc_policy_sha256=sha(path/'bc-policy.zip'))
    (path/'manifest.json').write_text(json.dumps(record));return path


def reply_within(worker,seconds=5.):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        reply=worker.poll()
        if reply is not None:return reply
        assert not worker.failed,worker.error
        time.sleep(.001)
    raise AssertionError('Functional worker reply did not arrive')


def test_custom_learner_load_and_contract_checks(folder):
    model=load_policy(folder,CONTRACT,55)
    assert model.actor_steps>0 and model.critic_steps>0
    initial=load_policy(folder,CONTRACT,55,bc=True)
    assert initial.actor_steps==initial.critic_steps==0
    with pytest.raises(ValueError,match='contract'):load_policy(folder,'wrong-contract',55)
    with pytest.raises(ValueError,match='dimensions'):load_policy(folder,CONTRACT,40)


def test_actual_worker_preserves_old_frame_and_limits_pending(folder):
    query=np.linspace(-.5,.5,55,dtype=np.float32)
    expected=load_policy(folder,CONTRACT,55).predict(query,deterministic=True)[0]
    with PolicyWorker(folder,CONTRACT,55) as worker:
        source_wall=time.monotonic()-.2
        assert worker.submit(query,1.,1.04,source_wall)
        assert not worker.submit(query,1.,1.04,source_wall)
        reply=reply_within(worker)
        assert reply.observed_s==1. and reply.submitted_s==1.04 and reply.wall_observed==source_wall
        assert reply.wall_submitted>reply.wall_observed and reply.prediction_ms>=0
        np.testing.assert_allclose(reply.action,expected,rtol=0,atol=1e-7)
        assert not fresh(reply,1.04,.1,time.monotonic()),'old source wall must never be refreshed at dispatch'
        with pytest.raises(ValueError):worker.submit(np.zeros(54),1.,1.04,time.monotonic())
        with pytest.raises(ValueError):worker.submit(np.full(55,np.nan),1.,1.04,time.monotonic())
        with pytest.raises(ValueError):worker.submit(np.zeros(55),1.1,1.04,time.monotonic())


def test_strict_actuation_age_rejects_next_tick_even_if_identity_matches():
    action=RuntimeAction(1,0.,0.,100.,100.001,100.002,100.003,(0.,)*8)
    assert fresh(action,0.,.1,100.01)
    assert not fresh(action,.05,.1,100.05)
    assert not fresh(action,0.,.1,100.05)


def test_worker_exit_is_observed_without_blocking(folder):
    worker=PolicyWorker(folder,CONTRACT,55)
    try:
        worker.process.terminate();worker.process.join(timeout=2.)
        assert worker.poll() is None and worker.failed
        assert not worker.submit(np.zeros(55),0.,0.,time.monotonic())
    finally:worker.close()


def test_owner_timing_includes_slow_prepare_instead_of_hiding_it():
    class SlowOwner:
        delay=.1;cfg=SimpleNamespace(proposal_ttl=.15)
        def prepare(self,now):
            time.sleep(.06);return SimpleNamespace(observed_s=now)
        def finish(self,context,proposal,deadline_wall=None):
            assert proposal is None
            return dict(source='lqr',sequence_plan_selected=False)
    row,_,reply=owner_tick(SlowOwner(),0.,lambda c:None,None)
    assert reply is None and row['owner_response_miss']
    assert row['complete_decision_ms']>=60 and row['owner_prepare_ms']>=60
    assert not row['runtime_selected']
