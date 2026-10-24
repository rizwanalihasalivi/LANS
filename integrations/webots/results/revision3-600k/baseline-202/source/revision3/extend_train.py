"""Equal-budget 100k→300k continuation with optimizer and reward normalization."""
import argparse,hashlib,importlib.util,json,sys,time
from pathlib import Path
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv,VecNormalize
HERE=Path(__file__).resolve().parent;RESEARCH=HERE.parent
sys.path[:0]=[str(HERE),str(RESEARCH)]
from pilot_env import PilotEnv
from comparison import configure_lqr
spec=importlib.util.spec_from_file_location('original_progress',RESEARCH/'train.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--initial',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    prior=json.loads((args.initial/'complete.json').read_text());protocol=json.loads((HERE/'extension.json').read_text())
    assert prior['steps']==100000 and prior['candidate'] in protocol['top_two'] and prior['seed'] in protocol['training_seeds']
    assert sha(args.initial/'policy.zip')==prior['policy_sha256']
    for n,d in prior['source_sha256'].items():assert sha(RESEARCH/n)==d
    configure_lqr();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    out=args.output;out.mkdir(parents=True,exist_ok=False)
    files=list(prior['source_sha256'])+['revision3/extend_train.py','revision3/extension.json']
    sources={n:sha(RESEARCH/n) for n in files}
    for n in sources:
        target=out/'source'/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((RESEARCH/n).read_bytes())
    config=prior['candidate_config'];seed=prior['seed'];start=time.time()
    env=DummyVecEnv([lambda i=i:Monitor(PilotEnv(1000000+seed*100+i,config),str(out/f'episodes-{i}.csv')) for i in range(8)])
    env=VecNormalize.load(args.initial/'normalization.pkl',env);env.training=True;env.norm_reward=True
    model=PPO.load(args.initial/'policy.zip',env=env,device='cpu');assert model.num_timesteps==100000
    model.learn(total_timesteps=200000,reset_num_timesteps=False,callback=old.Progress(out));assert model.num_timesteps==300000
    model.save(out/'policy');env.save(out/'normalization.pkl');env.close()
    assert sources=={n:sha(RESEARCH/n) for n in sources}
    meta=dict(prior,steps=300000,additional_steps=200000,wall_s=time.time()-start,source_sha256=sources,policy_sha256=sha(out/'policy.zip'),initial_policy_sha256=prior['policy_sha256'],initial_normalization_sha256=sha(args.initial/'normalization.pkl'),continuation=protocol['continuation'])
    (out/'complete.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(dict(candidate=prior['candidate'],seed=seed,steps=300000)),flush=True)
if __name__=='__main__':main()
