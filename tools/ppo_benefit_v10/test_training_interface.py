from stable_baselines3 import PPO
from .train import TrainingEnv


def test_real_rollout_logging_and_optimizer_update_work_with_raw_episode_ids(tmp_path):
    trace=tmp_path/'trace.jsonl';env=TrainingEnv(trace=trace)
    try:
        model=PPO('MlpPolicy',env,n_steps=8,batch_size=4,n_epochs=1,seed=42,device='cpu')
        model.learn(total_timesteps=16)
        assert model.num_timesteps==16 and model._n_updates==2
        assert model.policy.optimizer.state_dict()['state']
    finally:env.close()
    import json
    rows=[json.loads(line) for line in trace.read_text().splitlines()]
    assert len(rows)==16 and all(isinstance(r['episode'],int) for r in rows)
