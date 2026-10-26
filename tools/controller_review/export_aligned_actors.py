"""Exact v3 endpoint actor transfer, with origin/eligibility explicitly retained."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/reviewer_v3'))
import boot3
import numpy as np
import torch
from stable_baselines3 import PPO
from causal_student import load_causal


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False);torch.set_num_threads(1)
    decision=json.loads((args.run/'decision.json').read_text()) if (args.run/'decision.json').exists() else None
    for pair,seed in enumerate((701,802,903)):
        source=args.run/f'training-{pair}/policy.zip';meta=json.loads((source.parent/'complete.json').read_text())
        model=PPO.load(source,device='cpu');target=load_causal(ROOT/f'docs/research/causal-interface-2026-10-26/models/{seed}')
        with torch.no_grad():
            target.mean.copy_(model.policy.features_extractor.mean);target.std.copy_(model.policy.features_extractor.std)
            for a,b in ((model.policy.mlp_extractor.policy_net[0],target.net[0]),(model.policy.mlp_extractor.policy_net[2],target.net[2]),(model.policy.action_net,target.net[4])):
                b.weight.copy_(a.weight);b.bias.copy_(a.bias)
        folder=args.output/str(seed);folder.mkdir();torch.save(target.state_dict(),folder/'student.pt')
        np.savez(folder/'normalization.npz',mean=target.mean.numpy(),std=target.std.numpy())
        origin=dict(profile='causal_query_v2',origin='execution-aligned PPO endpoint; historical worker file name only, NOT a supervised-only model',
            source_ppo_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),steps=meta['steps'],futile=meta['futile'],
            development_eligible=decision['eligible'] if decision else None,purpose='research diagnostic, not deployment approval')
        (folder/'complete.json').write_text(json.dumps(origin,indent=2)+'\n')
        x=np.random.default_rng(371+pair).normal(size=(512,20)).astype(np.float32)*target.std.numpy()+target.mean.numpy();x[:,[14,15,16,17,19]]=0.
        with torch.no_grad():a=target(torch.from_numpy(x)).argmax(1).numpy()
        b=model.predict(x,deterministic=True)[0];assert np.array_equal(a,b)
        (folder/'parity.json').write_text(json.dumps(dict(rows=len(x),action_disagreements=0))+'\n')


if __name__=='__main__':main()
