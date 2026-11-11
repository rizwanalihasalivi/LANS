"""Check the changed curriculum and actual PPO training, with frozen physics."""
import json
import numpy as np
from tools.ppo_plan_v11.learning import Env as FrozenEnv
from .train import Env,curriculum,configure,optimizer_steps


def test_curriculum_and_fixed_case_physics():
    rng=np.random.default_rng(42);cases=[curriculum(rng) for _ in range(200)]
    duplicate=np.random.default_rng(42);assert cases==[curriculum(duplicate) for _ in range(200)]
    assert {c['delay'] for c in cases}=={0.,.05}
    assert {c['speed'] for c in cases}=={8.,12.,16.}
    assert all(c['lateral']*c['mirror']>0 and 10<=c['phase']<=28 for c in cases)
    case=next(c for c in cases if c['delay']==.05)
    old=FrozenEnv();new=Env()
    try:
        a,_=old.reset(seed=19,options={'case':case});b,_=new.reset(seed=19,options={'case':case});np.testing.assert_array_equal(a,b)
        for action in np.random.default_rng(18).uniform(-.5,.5,(8,8)):
            a=old.step(action);b=new.step(action);np.testing.assert_array_equal(a[0],b[0]);assert a[1:4]==b[1:4]
            for key in ('state_after','shadow_after','observation','label'):np.testing.assert_array_equal(a[4][key],b[4][key])
    finally:old.close();new.close()


def test_wider_exploration_preserves_mean_and_learns(tmp_path):
    import torch
    from stable_baselines3 import PPO
    torch.set_num_threads(1)
    path=tmp_path/'trace.jsonl';env=Env(trace=path)
    model=PPO('MlpPolicy',env,n_steps=8,batch_size=4,n_epochs=1,seed=42,device='cpu',learning_rate=1e-4,
        policy_kwargs=dict(log_std_init=-5.))
    obs,_=env.reset(seed=42);before=model.predict(obs,deterministic=True)[0]
    handles,counts=configure(model)
    np.testing.assert_array_equal(before,model.predict(obs,deterministic=True)[0])
    assert np.allclose(model.policy.log_std.detach().numpy(),-2.5)
    try:model.learn(total_timesteps=16)
    finally:
        for handle in handles:handle.remove()
        env.close()
    assert model.num_timesteps==16 and counts[0]==optimizer_steps(model)>0
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows)==16 and all(r['case']['delay'] in (0.,.05) for r in rows)
    assert all(np.isfinite(r['reward']) and len(r['label'])==8 for r in rows)
