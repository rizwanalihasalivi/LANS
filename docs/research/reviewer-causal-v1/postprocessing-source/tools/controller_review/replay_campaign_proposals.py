"""Independent saved-actor and executed-reward replay; no training/selection."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/reviewer_campaign'))
import common
import numpy as np
import torch
from stable_baselines3 import PPO
from train import student_folder
from causal_student import load_causal
from supervisor import P


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    args=p.parse_args();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    checked=0;reward_ticks=0;rounding_fallbacks=0
    for pair in range(3):
        student=load_causal(student_folder(pair))
        models={arm:PPO.load(args.run/'training'/f'{arm}-{P["seeds"][pair]}'/'policy.zip',device='cpu') for arm in P['arms']}
        for arm,model in models.items():
            folder=args.run/'training'/f'{arm}-{P["seeds"][pair]}'
            meta=json.loads((folder/'complete.json').read_text())
            assert meta['protocol']==P and meta['steps']==model.num_timesteps==25000
            assert model.seed==P['seeds'][pair]
            initial=PPO.load(folder/'initial.zip',device='cpu')
            assert initial.num_timesteps==0
            extractor=model.policy.features_extractor
            assert torch.equal(extractor.mean,student.mean) and torch.equal(extractor.std,student.std)
            assert any(not torch.equal(initial.policy.state_dict()[key],value)
                       for key,value in model.policy.state_dict().items() if 'policy_net' in key or 'action_net' in key)
            assert model.policy.optimizer.state
            if arm=='finetune':
                for a,b in [(initial.policy.mlp_extractor.policy_net[0],student.net[0]),
                            (initial.policy.mlp_extractor.policy_net[2],student.net[2]),
                            (initial.policy.action_net,student.net[4])]:
                    assert torch.equal(a.weight,b.weight) and torch.equal(a.bias,b.bias)
        for file in sorted((args.run/'development'/f'pair-{pair}'/'traces').glob('*.csv.gz')):
            # Method labels do not contain path/mirror delimiters except underscore.
            method=next((name for name in P['development']['methods'] if file.name.endswith('-'+name+'.csv.gz')),None)
            if method is None:raise ValueError(file)
            with gzip.open(file,'rt') as handle:rows=list(csv.DictReader(handle))
            previous=0.
            for row in rows:
                ey=float(row['lateral_error']);ep=float(row['heading_error']);command=float(row['command'])
                reward=(-(ey/.5)**2-.2*(ep/.1)**2-.005*(command/.5)**2
                        -.001*((command-previous)/.005)**2-10*(row['failed']=='True'))
                assert abs(reward-float(row['reward']))<1e-10
                previous=command;reward_ticks+=1
            queries=[row for row in rows if row['worker_available']=='True']
            if method in ('lqr','fixed_negative','fixed_positive'):
                expected={'lqr':0.,'fixed_negative':-.04,'fixed_positive':.04}[method]
                assert all(abs(float(row['proposed_residual'])-expected)<1e-12 for row in queries)
                continue
            x=np.asarray([[float(row[f'obs{i}']) for i in range(20)] for row in queries],dtype=np.float32)
            assert np.all(x[:,[14,15,16,17,19]]==0)
            if method=='student':
                with torch.no_grad():indices=student(torch.from_numpy(x)).argmax(1).numpy()
            else:
                actor=models['scratch' if method=='scratch' else 'finetune']
                indices,_=actor.predict(x,deterministic=True)
            for row,obs,index in zip(queries,x,indices):
                residual=P['candidates_rad'][int(index)]
                if abs(residual-float(row['proposed_residual']))>=1e-8:
                    # Batch-vs-batch1 floating-point ordering can alter a near tie.
                    rounding_fallbacks+=1
                    if method=='student':
                        actual,_=student.predict(obs);residual=.08*float(actual[0])
                    else:
                        actual,_=actor.predict(obs,deterministic=True);residual=P['candidates_rad'][int(actual)]
                    assert abs(residual-float(row['proposed_residual']))<1e-8
                checked+=1
        print('verified proposal/reward pair',pair,flush=True)
    result=dict(actor_queries_replayed=checked,executed_rewards_recomputed=reward_ticks,
                batch_rounding_fallbacks=rounding_fallbacks,causal_channels_verified=True,
                actor_and_reward_replay_pass=True,not_a_training_or_selection_stage=True)
    (args.run/'development/proposal-reward-replay.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
