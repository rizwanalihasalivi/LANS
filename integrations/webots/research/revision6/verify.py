"""Post-run checkpoint/optimizer verification; never trains or changes criteria."""
import argparse,json,pickle
from pathlib import Path
import torch
from stable_baselines3 import PPO
from bootstrap import HERE


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    protocol=json.loads((HERE/'protocol.json').read_text());torch.set_num_threads(1);models=[]
    for arm in protocol['arms']:
        for seed in protocol['seeds']:
            folder=a.run/'training'/f'{arm}-{seed}';model=PPO.load(folder/'policy.zip',device='cpu')
            meta=json.loads((folder/'complete.json').read_text())
            assert model.num_timesteps==meta['steps']==100000 and model.seed==meta['seed']==seed
            assert model.observation_space.shape==(20,) and model.action_space.shape==(1,)
            steps=sorted({int(v['step'].item()) for v in model.policy.optimizer.state_dict()['state'].values()})
            assert steps==[5000] and model._n_updates==1000
            with (folder/'normalization.pkl').open('rb') as f:normalization=pickle.load(f)
            assert not normalization.norm_obs and normalization.norm_reward and abs(normalization.ret_rms.count-100000.0001)<1e-5
            models.append(dict(arm=arm,seed=seed,steps=model.num_timesteps,ppo_updates=model._n_updates,
                optimizer_steps=steps,reward_normalization_samples=normalization.ret_rms.count,
                final_physical_std_rad=float(.08*model.policy.log_std.exp().detach().cpu().mean())))
    decision=json.loads((a.run/'decision.json').read_text());assert decision['verified'] and decision['episodes']==648
    (a.run/'checkpoint-verification.json').write_text(json.dumps(dict(verified=True,models=models),indent=2)+'\n')
    print('All6 fixed100k checkpoints, optimizer updates and reward statistics verified.')


if __name__=='__main__':main()
