import json
import numpy as np
from stable_baselines3 import PPO
from tools.unified_control_v4.calibrate import cases
from .learning import Env,reconstruct


def test_reconstructed_queries_match_actual_queries_without_next_truth():
    env=Env();case=cases()[0];env.reset(seed=42,options=dict(case=case));rows=[]
    try:
        for i in range(6):
            _,_,_,_,row=env.step(np.linspace(-.1,.1,8));rows.append(row)
        rebuilt=reconstruct(case,rows)
        np.testing.assert_allclose(rebuilt,np.asarray([r['observation'] for r in rows]),rtol=0,atol=1e-7)
        # Future ego truth is deliberately corrupted: query reconstruction must
        # use received state_before and actual applied history, not state_after.
        for row in rows:row['state_after']=np.full(6,999.)
        np.testing.assert_array_equal(reconstruct(case,rows),rebuilt)
    finally:env.close()


def test_genuine_ppo_optimizer_steps_and_serialized_sequence_trace(tmp_path):
    path=tmp_path/'trace.jsonl';env=Env(trace=path)
    try:
        model=PPO('MlpPolicy',env,n_steps=8,batch_size=4,n_epochs=1,seed=42,device='cpu')
        model.learn(total_timesteps=16)
        assert model.num_timesteps==16 and model._n_updates==2 and model.policy.optimizer.state_dict()['state']
    finally:env.close()
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows)==16 and len(rows[0]['observation'])==40 and len(rows[0]['label'])==8
