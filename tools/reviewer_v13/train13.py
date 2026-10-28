"""Matched legacy/physical-reward training with immutable exact-resume snapshots."""
import boot13
import json
import numpy as np
import torch
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from stable_baselines3.common.logger import configure
from credit6 import CreditPPO, CreditBuffer
from checkpoint12 import save, load, atomic_json
from train12 import Credit
from env13 import Env

P=json.loads((boot13.HERE/'protocol.json').read_text())


def bridge(model):
    f=model.policy.features_extractor
    ratio=float(f.mean[14]/f.std[14])
    with torch.no_grad():
        for layer in (model.policy.mlp_extractor.policy_net[0],model.policy.mlp_extractor.value_net[0]):
            layer.bias.sub_(ratio*layer.weight[:,14]);layer.weight[:,14].zero_()
            # Preserve unaffected Adam history. Only changed parameter components
            # lose their moment estimates; the shared scalar step is retained.
            for name,value in model.policy.optimizer.state.get(layer.weight,{}).items():
                if isinstance(value,torch.Tensor) and value.shape==layer.weight.shape:value[:,14].zero_()
            if ratio:
                for name,value in model.policy.optimizer.state.get(layer.bias,{}).items():
                    if isinstance(value,torch.Tensor) and value.shape==layer.bias.shape:value.zero_()
        f.mean[14]=0.;f.std[14]=1.


def initialize(pair,arm):
    cfg=P['training'];seed=cfg['seeds'][pair]
    old=boot13.ROOT/f'docs/research/reviewer-causal-v1/training/finetune-{(2701,2802,2903)[pair]}'
    vec=DummyVecEnv([lambda slot=slot:Env(pair,slot,seed+slot,profile='budget',reward_kind=arm,noise_base=cfg['noise_base']) for slot in range(4)])
    env=VecNormalize.load(old/'reward-normalization.pkl',vec);env.training=True;env.norm_obs=False
    with (old/'policy.zip').open('rb') as f:model=CreditPPO.load(f,env=env,device='cpu',force_reset=True)
    bridge(model);model.seed=seed;model.set_random_seed(seed)
    model.rollout_buffer=CreditBuffer(model.n_steps,model.observation_space,model.action_space,device='cpu',gamma=model.gamma,gae_lambda=model.gae_lambda,n_envs=4)
    model.audit_counts=dict(submitted=0,active=0)
    return model,env


def train(pair,arm,out,signature,publish=None):
    out.mkdir(parents=True,exist_ok=True);cfg=P['training'];total=cfg['steps_each'];checkpoints=out/'checkpoints'
    resumed=(checkpoints/'latest.json').exists()
    model,env,_=load(checkpoints,signature) if resumed else (*initialize(pair,arm),None)
    model.set_logger(configure(None,[]));callback=Credit()
    remaining=total-model.num_timesteps if resumed else total
    if remaining<0:raise ValueError('Budget exceeded')
    if remaining or not resumed:model._setup_learn(remaining,callback,reset_num_timesteps=not resumed)
    else:callback.init_callback(model)
    if not resumed:save(model,checkpoints,signature)
    while model.num_timesteps<total:
        if not model.collect_rollouts(env,callback,model.rollout_buffer,model.n_steps):raise RuntimeError('Incomplete rollout')
        model._update_current_progress_remaining(model.num_timesteps,total);model.train()
        if model.num_timesteps%cfg['checkpoint_steps']==0:
            folder=save(model,checkpoints,signature)
            stats={k:float(v) for k,v in model.logger.name_to_value.items() if np.isscalar(v)}
            row=dict(arm=arm,pair=pair,additional_steps=model.num_timesteps,**model.audit_counts,optimizer=stats,snapshot=str(folder.relative_to(out)))
            atomic_json(out/f'progress-{model.num_timesteps}.json',row);print(json.dumps(row),flush=True)
            if publish:publish(f'Save recovered PPO v13 {arm} pair {pair} at {model.num_timesteps} steps')
    atomic_json(out/'complete.json',dict(arm=arm,pair=pair,additional_steps=total,**model.audit_counts,checkpoint=json.loads((checkpoints/'latest.json').read_text())))
    env.close()
