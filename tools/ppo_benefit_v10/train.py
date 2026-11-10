"""Fixed causal teacher collection and all-seed PPO training endpoints."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import argparse,ast,json,multiprocessing as mp,shutil
import numpy as np
from integrations.unified_lans.inference import sha
from tools.unified_control_v9.learning import training_case
from .core import ROOT,DATA,CONTRACT,Env,teacher,dump


class TrainingEnv(Env):
    def step(self,action):
        obs,reward,terminated,truncated,info=super().step(action)
        # SB3 reserves info['episode'] for Monitor statistics. The raw trace
        # retains our integer episode id; only this library-facing view changes.
        return obs,reward,terminated,truncated,{k:v for k,v in info.items() if k!='episode'}


def snapshot(out):
    files=[*Path(__file__).parent.glob('*.py'),Path(__file__).parent/'PROTOCOL.md',
        *(ROOT/'integrations/unified_lans').glob('*.py'),ROOT/'tools/unified_campaign/study.py',
        ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py',ROOT/'tools/unified_control_v9/learning.py']
    for v in range(4,9):files.extend((ROOT/f'tools/unified_control_v{v}').glob('*.py'))
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    for p in files:
        dest=out/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    return hashes


def collect():
    folder=DATA/'teacher';folder.mkdir(parents=True,exist_ok=False)
    rng=np.random.default_rng(524113);cases=[dict(training_case(rng),id=i,stage='ppo_benefit_training_teacher') for i in range(64)]
    dump(folder/'protocol.json',dict(cases=cases,source_hashes=snapshot(folder),contract=CONTRACT,training_only=True))
    features=[];labels=[];weights=[];rows=[];episodes=[]
    env=Env(trace=folder/'transitions.jsonl')
    try:
        for case in cases:
            obs,_=env.reset(seed=524113,options=dict(case=case));rr=[]
            for tick in range(120):
                action,info=teacher(env.pipe,tick*.05)
                features.append(obs.copy());labels.append([action]);weights.append(10. if abs(action)>1e-8 else 1.)
                rows.append(dict(case_id=case['id'],tick=tick,action=action,teacher=info))
                obs,reward,done,truncated,row=env.step([action]);rr.append(row)
                if done or truncated:break
            episodes.append(dict(case=case,ticks=len(rr),failed=bool(done),ppo_ticks=sum(r['decision']['source']=='ppo' for r in rr)))
            print('TEACHER',case['id']+1,'/64',len(features),'labels',flush=True)
    finally:env.close()
    np.savez_compressed(folder/'dataset.npz',observations=np.asarray(features,np.float32),actions=np.asarray(labels,np.float32),weights=np.asarray(weights,np.float32))
    dump(folder/'labels.json',rows);dump(folder/'summary.json',episodes)
    dump(folder/'manifest.json',dict(samples=len(labels),nonzero_labels=sum(abs(a[0])>1e-8 for a in labels),
        dataset_sha256=sha(folder/'dataset.npz'),trace_sha256=sha(folder/'transitions.jsonl'),failures=sum(r['failed'] for r in episodes)))


def initialize(seed,env):
    import torch
    from stable_baselines3 import PPO
    torch.set_num_threads(1);torch.manual_seed(seed)
    origin=ROOT/f'results/python-campaign-v2/policies/seed-{seed}/policy.zip'
    old=PPO.load(origin,device='cpu')
    model=PPO('MlpPolicy',env,seed=seed,device='cpu',learning_rate=1e-4,n_steps=1024,batch_size=128,
        n_epochs=10,gamma=.99,gae_lambda=.95,ent_coef=0.,policy_kwargs=dict(net_arch=old.policy.net_arch,log_std_init=-2.5))
    target=model.policy.state_dict();source=old.policy.state_dict();transferred=[]
    for key,value in target.items():
        if key=='log_std':continue
        if key in source and source[key].shape==value.shape:
            target[key]=source[key].clone();transferred.append(key)
        elif key.endswith('0.weight') and key in source and value.shape[1]==30 and source[key].shape[1]==17:
            target[key]=torch.zeros_like(value);target[key][:,:17]=source[key];transferred.append(key+':first17')
    model.policy.load_state_dict(target)
    with torch.no_grad():model.policy.value_net.weight.zero_();model.policy.value_net.bias.zero_()
    return model,origin,transferred


def train(seed):
    import torch
    from stable_baselines3.common.callbacks import BaseCallback
    torch.set_num_threads(1);torch.manual_seed(seed);rng=np.random.default_rng(seed)
    folder=DATA/'policies'/f'seed-{seed}';folder.mkdir(parents=True,exist_ok=False)
    env=TrainingEnv(trace=folder/'training.jsonl');model,origin,transferred=initialize(seed,env)
    dataset=DATA/'teacher/dataset.npz';data=np.load(dataset)
    observations=torch.tensor(data['observations']);actions=torch.tensor(data['actions']);weights=torch.tensor(data['weights'])
    actor_params=list(model.policy.mlp_extractor.policy_net.parameters())+list(model.policy.action_net.parameters())
    optimizer=torch.optim.Adam(actor_params,lr=3e-4);losses=[]
    for epoch in range(32):
        total=0.;permutation=rng.permutation(len(observations))
        for start in range(0,len(observations),128):
            indices=permutation[start:start+128]
            o=observations[indices];target_action=actions[indices];w=weights[indices]
            mean=model.policy.get_distribution(o).distribution.mean
            loss=(w*(mean-target_action).square().mean(dim=1)).mean()
            optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(actor_params,1.);optimizer.step();total+=float(loss.detach())
        losses.append(total);print('BC',seed,epoch+1,'/32',total,flush=True)
    # The changed feature/reward contract deliberately starts a new optimizer.
    model.policy.optimizer=torch.optim.Adam(model.policy.parameters(),lr=1e-4,eps=1e-5)
    model.save(folder/'bc-policy.zip');dump(folder/'bc-loss.json',losses)
    dump(folder/'protocol.json',dict(seed=seed,contract=CONTRACT,bc_epochs=32,new_ppo_steps=16384,
        source_policy_sha256=sha(origin),dataset_sha256=sha(dataset),transferred=transferred,
        optimizer_reset=True,source_hashes=snapshot(folder),no_endpoint_selection=True))
    class Checkpoint(BaseCallback):
        def _on_step(self):
            if self.num_timesteps%2048==0:
                model.save(folder/f'checkpoint-{self.num_timesteps}.zip');print('PPO',seed,self.num_timesteps,'/16384',flush=True)
            return True
    try:model.learn(total_timesteps=16384,callback=Checkpoint());model.save(folder/'policy.zip')
    finally:env.close()
    assert model.num_timesteps==16384
    manifest=dict(seed=seed,contract=CONTRACT,steps=16384,policy_sha256=sha(folder/'policy.zip'),
        bc_policy_sha256=sha(folder/'bc-policy.zip'),trace_sha256=sha(folder/'training.jsonl'))
    dump(folder/'manifest.json',manifest);return manifest


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['collect','train']);args=parser.parse_args()
    if args.stage=='collect':collect();return
    teacher_folder=DATA/'teacher';protocol=json.loads((teacher_folder/'protocol.json').read_text())
    for name,digest in protocol['source_hashes'].items():
        if name==str(Path(__file__).relative_to(ROOT)):
            # The failed actor-width initialization did not affect labels. Pin
            # the original collector and prove its AST remains identical.
            def collector(path):return next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='collect')
            assert ast.dump(collector(teacher_folder/'source'/name))==ast.dump(collector(Path(__file__)))
        else:assert sha(ROOT/name)==digest,('Source changed after labels',name)
    (DATA/'policies').mkdir(exist_ok=False)
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn')) as pool:
        result=[f.result() for f in as_completed([pool.submit(train,s) for s in (42,43,44)])]
    dump(DATA/'policies/summary.json',sorted(result,key=lambda r:r['seed']))


if __name__=='__main__':main()
