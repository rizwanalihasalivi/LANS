"""Exact300k checkpoint continuation to600k; explicit optimizer/statistics audit."""
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
optimizer_steps=lambda model:sorted({int(v['step'].item()) for v in model.policy.optimizer.state_dict()['state'].values()})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--initial',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    protocol=json.loads((HERE/'confirmation.json').read_text());prior=json.loads((args.initial/'complete.json').read_text())
    assert prior['candidate']=='baseline' and prior['seed'] in protocol['seeds'] and prior['steps']==300000 and prior['residual_scale_rad']==.08
    assert sha(args.initial/'policy.zip')==prior['policy_sha256']
    for n,d in prior['source_sha256'].items():assert sha(RESEARCH/n)==d
    configure_lqr();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    out=args.output;out.mkdir(parents=True,exist_ok=False)
    files=list(prior['source_sha256'])+['revision3/confirm_train.py','revision3/confirmation.json']
    sources={n:sha(RESEARCH/n) for n in files}
    for n in sources:
        target=out/'source'/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((RESEARCH/n).read_bytes())
    seed=prior['seed'];start=time.time()
    env=DummyVecEnv([lambda i=i:Monitor(PilotEnv(seed+i,prior['candidate_config']),str(out/f'episodes-{i}.csv')) for i in range(8)])
    env=VecNormalize.load(args.initial/'normalization.pkl',env);env.training=True;env.norm_reward=True
    model=PPO.load(args.initial/'policy.zip',env=env,device='cpu');assert model.num_timesteps==300000
    before_optimizer=optimizer_steps(model);before_norm=float(env.ret_rms.count);reset_seeds=list(env.venv._seeds)
    assert reset_seeds==[seed+i for i in range(8)] and before_optimizer==[15000]
    (out/'resume.json').write_text(json.dumps(dict(initial_policy_sha256=sha(args.initial/'policy.zip'),initial_normalization_sha256=sha(args.initial/'normalization.pkl'),initial_steps=model.num_timesteps,optimizer_steps=before_optimizer,normalization_count=before_norm,effective_reset_seeds=reset_seeds),indent=2)+'\n')
    model.learn(total_timesteps=300000,reset_num_timesteps=False,callback=old.Progress(out));assert model.num_timesteps==600000
    after_optimizer=optimizer_steps(model);after_norm=float(env.ret_rms.count)
    assert after_optimizer==[30000] and abs(after_norm-before_norm-300000)<1e-6
    model.save(out/'policy');env.save(out/'normalization.pkl');env.close()
    assert sources=={n:sha(RESEARCH/n) for n in sources}
    meta=dict(prior,steps=600000,additional_steps=300000,wall_s=time.time()-start,source_sha256=sources,policy_sha256=sha(out/'policy.zip'),initial_policy_sha256=sha(args.initial/'policy.zip'),initial_normalization_sha256=sha(args.initial/'normalization.pkl'),continuation=protocol['continuation'],optimizer_steps_before=before_optimizer,optimizer_steps_after=after_optimizer,normalization_count_before=before_norm,normalization_count_after=after_norm)
    (out/'complete.json').write_text(json.dumps(meta,indent=2)+'\n');print(f'Baseline seed{seed}: verified600k total steps',flush=True)
if __name__=='__main__':main()
