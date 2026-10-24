"""Audit corrected smoke artifacts and normalization/action parity."""
import csv,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
from stable_baselines3 import PPO
from controllers.policy_bundle import PolicyBundle
from envs.residual_path_env import ResidualPathEnv

root=Path(__file__).resolve().parents[2]/'integrations/webots/results/controller-remediation'
bundle=PolicyBundle(root/'root-smoke');model=PPO.load(root/'root-smoke/policy.zip')
assert model.num_timesteps==1000
assert bundle.normalizer.obs_rms.count>1000
obs,_=ResidualPathEnv().reset(seed=52)
a,_=bundle.predict(obs);b,_=model.predict(bundle.normalizer.normalize_obs(obs),deterministic=True)
np.testing.assert_array_equal(a,b)
rows=list(csv.DictReader((root/'root-comparison/episodes.csv').open()))
assert len(rows)==36
paired={(r['seed'],r['speed'],r['delay_ms'],r['method']):r for r in rows}
assert len(paired)==36
for seed in ('101','202'):
 for speed in ('15','20','25'):
  for delay in ('0','20','100'):
   assert paired[seed,speed,delay,'lqr']['penalized_rmse']==paired[seed,speed,'0','lqr']['penalized_rmse']
  assert paired[seed,speed,'100','residual']['penalized_rmse']==paired[seed,speed,'100','lqr']['penalized_rmse']
transitions=list(csv.DictReader((root/'execution-smoke/transitions.csv').open()))
assert len(transitions)==1000
for r in transitions:
 assert abs(float(r['command_rad']))<=.5
 assert abs(float(r['actuator_after_rad'])-float(r['actuator_before_rad']))<=.003500001
 if r['gate_weight']=='0.0':assert float(r['reward_relative'])==0
 if float(r['action_age_s'])>=.05:assert float(r['command_rad'])==float(r['baseline_rad'])
model2=PPO.load(root/'execution-smoke/policy.zip');assert model2.num_timesteps==1000
assert model2.observation_space.shape==(20,)
logs=list(csv.DictReader((root/'execution-smoke/progress.csv').open()))
for key in ('train/approx_kl','train/entropy_loss','train/explained_variance'):
 assert any(row.get(key) not in ('',None) for row in logs)
tests=json.loads((root/'test-results.json').read_text());assert all(r['exit_code']==0 for r in tests)
result=dict(verified=True,root_training_steps=1000,execution_training_steps=1000,root_episodes=36,
    root_survived=sum(r['survived']=='True' for r in rows),normalization_prediction_parity=True,
    severe_delay_fallback_exact=True,execution_transition_count=len(transitions),test_commands=len(tests))
(root/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
