"""Verify budgets, changed actor parameters, normalization and export provenance."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/reviewer_v3'))
import boot3
import torch
from stable_baselines3 import PPO


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args();torch.set_num_threads(1);rows=[]
    for pair in range(3):
        folder=args.run/f'training-{pair}';meta=json.loads((folder/'complete.json').read_text())
        initial=PPO.load(folder/'initial.zip',device='cpu');final=PPO.load(folder/'policy.zip',device='cpu')
        assert final.num_timesteps==meta['steps']==100000 and not meta['futile']
        a=initial.policy.state_dict();b=final.policy.state_dict();keys=[k for k in a if 'policy_net' in k or 'action_net' in k]
        changed=[k for k in keys if not torch.equal(a[k],b[k])];assert changed
        assert torch.equal(initial.policy.features_extractor.mean,final.policy.features_extractor.mean)
        assert torch.equal(initial.policy.features_extractor.std,final.policy.features_extractor.std)
        digest=hashlib.sha256((folder/'policy.zip').read_bytes()).hexdigest()
        export=args.run/f'export/{(701,802,903)[pair]}/complete.json'
        if export.exists():assert json.loads(export.read_text())['source_ppo_sha256']==digest
        rows.append(dict(pair=pair,seed=meta['seed'],steps=meta['steps'],changed_actor_tensors=changed,
            frozen_observation_normalization_verified=True,endpoint_sha256=digest))
    (args.run/'training-verification.json').write_text(json.dumps(dict(total_steps=sum(r['steps'] for r in rows),pilots=rows),indent=2)+'\n')
    print('Verified',sum(r['steps'] for r in rows),'steps across3changed actors')


if __name__=='__main__':main()
