"""Exact actor export for independent workers; PPO remains the trained source."""
import common
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
from supervisor import P
from train import student_folder
from causal_student import load_causal


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--training',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    for pair,seed in enumerate(P['student_seeds']):
        source=args.training/f'finetune-{P["seeds"][pair]}'/'policy.zip'
        model=PPO.load(source,device='cpu')
        target=load_causal(student_folder(pair))
        with torch.no_grad():
            for a,b in [(model.policy.mlp_extractor.policy_net[0],target.net[0]),
                        (model.policy.mlp_extractor.policy_net[2],target.net[2]),
                        (model.policy.action_net,target.net[4])]:
                b.weight.copy_(a.weight);b.bias.copy_(a.bias)
        folder=args.output/str(seed);folder.mkdir()
        torch.save(target.state_dict(),folder/'student.pt')
        np.savez(folder/'normalization.npz',mean=target.mean.numpy(),std=target.std.numpy())
        (folder/'complete.json').write_text(json.dumps(dict(profile='causal_query_v2',
            origin='25k PPO actor exact export, NOT supervised-only student',
            ppo_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),steps=25000,
            profile_compatibility='Existing CPU worker architecture only; provenance identifies PPO'),indent=2)+'\n')
        saved=load_causal(folder)
        rng=np.random.default_rng(27+pair)
        x=(rng.normal(size=(512,20)).astype(np.float32)*target.std.numpy()+target.mean.numpy())
        x[:,[14,15,16,17,19]]=0.
        for obs in x:
            action,_=model.predict(obs,deterministic=True)
            residual,_=saved.predict(obs)
            assert abs(P['candidates_rad'][int(action)]-.08*float(residual[0]))<1e-8
        (folder/'parity.json').write_text(json.dumps(dict(rows=512,action_disagreements=0))+'\n')


if __name__=='__main__':main()
