import boot3
import argparse
import csv
import itertools
import json
import torch
from stable_baselines3 import PPO
from causal_student import load_causal
import experiment
from aligned import AlignedEnv,P


def main():
    p=argparse.ArgumentParser();p.add_argument('--pair',type=int,required=True,choices=range(3));p.add_argument('--run',type=boot3.Path,required=True)
    args=p.parse_args();pair=args.pair;out=args.run/f'pair-{pair}';out.mkdir(parents=True,exist_ok=False);(out/'traces').mkdir()
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    models={'student':load_causal(boot3.ROOT/f'docs/research/causal-interface-2026-10-26/models/{P["training"]["student_seeds"][pair]}'),
        'oldppo':PPO.load(boot3.ROOT/f'docs/research/reviewer-causal-v1/training/finetune-{(2701,2802,2903)[pair]}/policy.zip',device='cpu'),
        'ppo':PPO.load(args.run/f'training-{pair}/policy.zip',device='cpu')}
    experiment.FollowupEnv=lambda profile,case:AlignedEnv(case=case,baseline=profile=='lqr')
    grid=P['development'];rows=[]
    with (out/'episodes.csv').open('w',newline='') as f:
        writer=None
        for speed,path,sign,scenario in itertools.product(grid['speeds'],grid['paths'],grid['mirrors'],grid['scenarios']):
            noise=grid['noise_base']+pair*100000+speed*1000+grid['paths'].index(path)*100+grid['scenarios'].index(scenario)*10
            for source in grid['sources']:
                name=f'{speed}-{path}-{sign}-{scenario}-{source}'
                alias='none' if source=='lqr' else ('ppo' if source=='oldppo' else source)
                row=experiment.episode('lqr' if source=='lqr' else 'aligned',alias,models.get(source),
                    (speed,path,sign,scenario,noise),out/'traces'/f'{name}.csv.gz')
                row=dict(pair=pair,speed=speed,path=path,mirror=sign,scenario=scenario,source=source,noise_id=noise,**row)
                if writer is None:writer=csv.DictWriter(f,fieldnames=row,lineterminator='\n');writer.writeheader()
                writer.writerow(row);f.flush();rows.append(row)
            print(pair,path,sign,scenario,len(rows),flush=True)
    (out/'complete.json').write_text(json.dumps(dict(episodes=len(rows)),indent=2)+'\n')


if __name__=='__main__':main()
