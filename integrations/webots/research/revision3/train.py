"""Five-seed residual training with explicit candidate-range metadata."""
import argparse,hashlib,json,sys,time
from pathlib import Path
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv,VecNormalize
HERE=Path(__file__).resolve().parent;RESEARCH=HERE.parent
sys.path.insert(0,str(RESEARCH));sys.path.insert(0,str(HERE))
from pilot_env import PilotEnv
from mapping import RESIDUAL_SCALE_RAD
from comparison import configure_lqr
import importlib.util
spec=importlib.util.spec_from_file_location('original_progress',RESEARCH/'train.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
SOURCES=['core.py','protocol.json','environment.py','environment-v2.py','train.py','comparison.py','comparison-protocol.json','tracking.py','tracking-protocol.json','final-training-protocol.json',
         'revision3/train.py','revision3/matched_env.py','revision3/mapping.py','revision3/protocol.json','revision3/pilot_env.py','revision3/pilots.json']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--steps',type=int,required=True);p.add_argument('--candidate',required=True);p.add_argument('--selection',type=Path);args=p.parse_args()
    pilots=json.loads((HERE/'pilots.json').read_text());config=pilots['candidates'][args.candidate]
    if args.steps==pilots['full_steps']:
        assert args.selection, 'Full training requires the completed pilot selection manifest'
        selected=json.loads(args.selection.read_text());assert selected['selected_candidate']==args.candidate and selected['selected_config']==config
        assert selected['pilots_protocol_sha256']==sha(HERE/'pilots.json')
        for name,digest in selected['source_sha256'].items():assert sha(RESEARCH/name)==digest
    else:assert args.steps==pilots['pilot_steps']
    assert args.steps>0 and args.steps%1000==0
    configure_lqr();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    out=args.output;out.mkdir(parents=True,exist_ok=False);hashes={name:sha(RESEARCH/name) for name in SOURCES}
    for name in SOURCES:
        target=out/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((RESEARCH/name).read_bytes())
    start=time.time()
    env=DummyVecEnv([lambda i=i:Monitor(PilotEnv(args.seed*100+i,config),str(out/f'episodes-{i}.csv')) for i in range(8)])
    env=VecNormalize(env,norm_obs=False,norm_reward=True,clip_reward=10.)
    model=PPO('MlpPolicy',env,n_steps=125,batch_size=200,n_epochs=10,learning_rate=.0003,gamma=.99,gae_lambda=.95,
              seed=args.seed,device='cpu',policy_kwargs={'net_arch':config['net_arch'],'log_std_init':config['log_std_init']},verbose=0)
    model.learn(total_timesteps=args.steps,callback=old.Progress(out));assert model.num_timesteps==args.steps
    model.save(str(out/'policy'));env.save(str(out/'normalization.pkl'));env.close()
    assert hashes=={name:sha(RESEARCH/name) for name in SOURCES}
    meta=dict(seed=args.seed,role='residual',steps=model.num_timesteps,wall_s=time.time()-start,
              training_profile='range_matched_residual_v3',candidate=args.candidate,candidate_config=config,selection_sha256=sha(args.selection) if args.selection else None,residual_scale_rad=RESIDUAL_SCALE_RAD,action_space='normalized [-1,1]',
              deployment='use revision3.mapping adapter; never load directly through a .5-rad decoder',source_sha256=hashes,policy_sha256=sha(out/'policy.zip'))
    (out/'complete.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta),flush=True)
if __name__=='__main__':main()
