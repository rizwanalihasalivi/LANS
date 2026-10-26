"""Equal-budget A/B/C/D pilot training; on-policy synchronous gate transitions."""
import argparse,hashlib,importlib.util,json,sys,time
from pathlib import Path
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv,VecNormalize
from bootstrap import HERE,RESEARCH
from comparison import configure_lqr
from env4 import ResearchEnv,PROTOCOL
spec=importlib.util.spec_from_file_location('original_progress',RESEARCH/'train.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
SOURCES=['core.py','protocol.json','comparison.py','comparison-protocol.json','tracking.py','tracking-protocol.json','train.py',
         'revision2/plant.py','revision2/gating.py','revision3/mapping.py',
         'revision4/bootstrap.py','revision4/protocol.json','revision4/reward_model.py','revision4/env4.py','revision4/train4.py']

def main():
    p=argparse.ArgumentParser();p.add_argument('--arm',choices=list(PROTOCOL['arms']),required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--smoke',action='store_true');p.add_argument('--initial',type=Path);args=p.parse_args()
    configure_lqr();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    out=args.output;out.mkdir(parents=True,exist_ok=False);sources={n:sha(RESEARCH/n) for n in SOURCES}
    for n in SOURCES:
        target=out/'source'/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((RESEARCH/n).read_bytes())
    env=DummyVecEnv([lambda i=i:Monitor(ResearchEnv(args.arm,args.seed+i),str(out/f'episodes-{i}.csv'),info_keywords=('episode_gate_fraction','episode_mean_bonus','mu','stiffness','sensor_noise','sensor_delay','path_capped')) for i in range(8)])
    start=time.time();initial_sha=None;initial_steps=0
    if args.initial:
        assert not args.smoke
        prior=json.loads((args.initial/'complete.json').read_text());assert prior['steps']==100000 and prior['arm']==args.arm and prior['seed']==args.seed
        assert sha(args.initial/'policy.zip')==prior['policy_sha256'];initial_sha=prior['policy_sha256'];initial_steps=100000
        for n,d in prior['source_sha256'].items():assert sha(RESEARCH/n)==d
        env=VecNormalize.load(args.initial/'normalization.pkl',env);env.training=True;env.norm_reward=True
        model=PPO.load(args.initial/'policy.zip',env=env,device='cpu');assert model.num_timesteps==100000
        additional=200000
    else:
        env=VecNormalize(env,norm_obs=False,norm_reward=True,clip_reward=10.)
        model=PPO('MlpPolicy',env,n_steps=125,batch_size=200,n_epochs=10,learning_rate=.0003,gamma=.99,gae_lambda=.95,seed=args.seed,device='cpu',policy_kwargs={'net_arch':[64,64],'log_std_init':-2.},verbose=0)
        additional=1000 if args.smoke else 100000
    model.learn(total_timesteps=additional,reset_num_timesteps=not bool(args.initial),callback=old.Progress(out));assert model.num_timesteps==initial_steps+additional
    model.save(out/'policy');env.save(out/'normalization.pkl');env.close()
    assert sources=={n:sha(RESEARCH/n) for n in sources}
    meta=dict(arm=args.arm,seed=args.seed,steps=model.num_timesteps,additional_steps=additional,initial_policy_sha256=initial_sha,residual_scale_rad=.08,training_mode=PROTOCOL['arms'][args.arm],source_sha256=sources,policy_sha256=sha(out/'policy.zip'),wall_s=time.time()-start,profile='gate_relative_v4',synchronous_training=True)
    (out/'complete.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(dict(arm=args.arm,seed=args.seed,steps=model.num_timesteps)),flush=True)
if __name__=='__main__':main()
