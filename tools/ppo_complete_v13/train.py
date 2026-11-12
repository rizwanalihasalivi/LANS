"""Causal teacher initialization, actor-invariant critic warmup and true PPO."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import argparse,hashlib,json,multiprocessing as mp,shutil
import numpy as np
from integrations.unified_lans.inference import sha
from .learning import ROOT,DATA,Env,CONTRACT,OBSERVATION_DIM,ACTION_DIM
from .headroom import write

SEEDS=(42,43,44);STEPS=65536
CONTROLLER_KWARGS=dict(anchor_quality_factor=None,correction_amplitude=.08)


def snapshot(out):
    files=[ROOT/'tools/ppo_complete_v13'/n for n in ('learning.py','learner.py','plans.py','safety.py','train.py','headroom.py',
        'DEVELOPMENT_PROTOCOL.md','TRAINING_PROTOCOL.md')]
    files.extend((ROOT/'integrations/unified_lans').glob('*.py'))
    files.extend([ROOT/'tools/unified_control_v9/learning.py',ROOT/'tools/unified_campaign/study.py',ROOT/'tools/ppo_benefit_v10/core.py',
        ROOT/'models/bicycle_model.py',ROOT/'controllers/lqr_controller.py'])
    for version in range(4,9):files.extend((ROOT/f'tools/unified_control_v{version}').glob('*.py'))
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    for p in files:
        target=out/'source'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    return hashes


def collect():
    source=DATA/'teacher-development72';p=json.loads((source/'protocol.json').read_text());records=json.loads((source/'summary.json').read_text())
    assert len(records)==144 and len(p['cases'])==72 and p['quality']=='anchor' and p['objective']=='mixed'
    for name,digest in p['source_hashes'].items():assert sha(source/'source'/name)==digest
    out=DATA/'dataset';out.mkdir(exist_ok=False);observations=[];labels=[];inputs={}
    for record in records:
        if record['mode']!='teacher':continue
        path=source/f'{record["case"]["id"]:03d}-teacher.jsonl';assert sha(path)==record['raw_sha256']
        inputs[str(path.relative_to(ROOT))]=sha(path)
        for line in path.open():
            row=json.loads(line);x=np.asarray(row['observation'],np.float32);y=np.asarray(row['label'],np.float32)
            assert x.shape==(55,) and y.shape==(8,) and np.isfinite(x).all() and np.isfinite(y).all() and max(abs(y))<=1
            observations.append(x);labels.append(y)
    x=np.asarray(observations,np.float32);y=np.asarray(labels,np.float32)
    weights=np.where(np.max(abs(y),axis=1)>1e-8,10.,1.).astype(np.float32)
    np.savez_compressed(out/'dataset.npz',observations=x,actions=y,weights=weights)
    write(out/'protocol.json',dict(contract=CONTRACT,source_hashes=snapshot(out),input_hashes=inputs,
        teacher_protocol_sha256=sha(source/'protocol.json'),teacher_quality_factor=1.,actor_controller_kwargs=CONTROLLER_KWARGS,
        no_legacy_weight_reinterpretation=True,no_future_truth_features=True))
    write(out/'manifest.json',dict(samples=len(x),nonzero_labels=int(np.sum(weights>1)),observation_dim=55,action_dim=8,
        dataset_sha256=sha(out/'dataset.npz'),source_teacher_failures=sum(r['failed'] for r in records if r['mode']=='teacher')))
    print('V13 CAUSAL DATASET',len(x),'teacher frames',flush=True)


def actor_digest(model):
    h=hashlib.sha256()
    for parameter in model._actor_parameters:h.update(parameter.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def critic_warmup(model,seed,out):
    import torch
    before=actor_digest(model);env=Env(trace=out/'critic-warmup.jsonl',controller_kwargs=CONTROLLER_KWARGS)
    obs_rows=[];returns=[];steps=0;failures=0
    try:
        obs,_=env.reset(seed=90000+seed)
        for episode in range(32):
            local=[];rewards=[]
            while not env.done:
                action,_=model.predict(obs,deterministic=True);local.append(obs.copy())
                obs,reward,done,truncated,row=env.step(action);assert not truncated
                rewards.append(reward);steps+=1
                if done:failures+=row['terminal_reason']=='failure'
            total=0.;values=[]
            for r in reversed(rewards):total+=r;values.append(total)
            obs_rows.extend(local);returns.extend(reversed(values))
            if episode<31:obs,_=env.reset()
    finally:env.close()
    x=torch.tensor(np.asarray(obs_rows,np.float32));target=torch.tensor(np.asarray(returns,np.float32));rng=np.random.default_rng(seed+400000)
    initial_steps=model.critic_steps;losses=[]
    for epoch in range(4):
        permutation=rng.permutation(len(x));loss_sum=0.
        for start in range(0,len(x),128):
            index=permutation[start:start+128];predicted=model.policy.predict_values(x[index]).flatten()
            loss=.5*torch.nn.functional.mse_loss(predicted,target[index]);model.critic_optimizer.zero_grad(set_to_none=True)
            loss.backward();torch.nn.utils.clip_grad_norm_(model._critic_parameters,.5,error_if_nonfinite=True)
            model.critic_optimizer.step();model.critic_steps+=1;loss_sum+=float(loss.detach())
        losses.append(loss_sum)
    assert before==actor_digest(model) and model.actor_steps==0 and model.num_timesteps==0
    model.validate_optimizer_counters()
    report=dict(episodes=32,environment_steps=steps,failures=failures,critic_updates=model.critic_steps-initial_steps,
        actor_unchanged_sha256=before,seed_namespace=90000+seed,losses=losses,trace_sha256=sha(out/'critic-warmup.jsonl'))
    write(out/'critic-warmup.json',report);return report


def worker(seed):
    import torch
    from stable_baselines3.common.callbacks import BaseCallback
    from .learner import IndependentPPO,optimizer_steps
    torch.set_num_threads(1);torch.manual_seed(seed);rng=np.random.default_rng(seed)
    out=DATA/f'policies/seed-{seed}';out.mkdir(parents=True,exist_ok=False)
    env=Env(trace=out/'training.jsonl',controller_kwargs=CONTROLLER_KWARGS)
    model=IndependentPPO('MlpPolicy',env,seed=seed,device='cpu',policy_kwargs=dict(net_arch=dict(pi=[128,128],vf=[128,128])))
    dataset=np.load(DATA/'dataset/dataset.npz');x=torch.tensor(dataset['observations']);y=torch.tensor(dataset['actions']);w=torch.tensor(dataset['weights'])
    opt=torch.optim.Adam(model._actor_parameters,lr=3e-4);losses=[]
    for epoch in range(32):
        permutation=rng.permutation(len(x));total=0.
        for start in range(0,len(x),128):
            ids=permutation[start:start+128];mean=model.policy.get_distribution(x[ids]).distribution.mean
            loss=(w[ids]*(mean-y[ids]).square().mean(dim=1)).mean();opt.zero_grad(set_to_none=True);loss.backward()
            torch.nn.utils.clip_grad_norm_(model._actor_parameters,1.);opt.step();total+=float(loss.detach())
        losses.append(total)
    assert model.actor_steps==model.critic_steps==0;model.validate_optimizer_counters();write(out/'bc-loss.json',losses)
    bc_updates=32*int(np.ceil(len(x)/128));assert optimizer_steps(opt)==bc_updates
    torch.save(opt.state_dict(),out/'bc-supervised-optimizer.pt')
    warmup=critic_warmup(model,seed,out);model.save(out/'bc-policy.zip')
    write(out/'protocol.json',dict(seed=seed,contract=CONTRACT,observation_dim=55,action_dim=8,bc_epochs=32,
        ppo_steps=STEPS,gamma=1.,controller_kwargs=CONTROLLER_KWARGS,source_hashes=snapshot(out),
        dataset_sha256=sha(DATA/'dataset/dataset.npz'),critic_warmup=warmup,no_checkpoint_selection=True))
    class Checkpoint(BaseCallback):
        def _on_step(self):
            if self.num_timesteps%16384==0:
                model.save(out/f'checkpoint-{self.num_timesteps}.zip')
                print('V13 PPO',seed,self.num_timesteps,'/65536 actor',model.actor_steps,'critic',model.critic_steps,flush=True)
            return True
    try:model.learn(total_timesteps=STEPS,callback=Checkpoint());model.save(out/'policy.zip')
    finally:env.close()
    model.validate_optimizer_counters();assert model.num_timesteps==STEPS
    write(out/'optimizer-history.json',model.train_history)
    result=dict(seed=seed,contract=CONTRACT,observation_dim=55,action_dim=8,learner_class='IndependentPPO',steps=STEPS,
        actor_steps=model.actor_steps,critic_steps=model.critic_steps,critic_warmup_steps=warmup['critic_updates'],
        critic_onpolicy_steps=model.critic_steps-warmup['critic_updates'],actor_kl_stops=model.actor_kl_stops,sb3_epoch_counter=model._n_updates,
        policy_sha256=sha(out/'policy.zip'),bc_policy_sha256=sha(out/'bc-policy.zip'),trace_sha256=sha(out/'training.jsonl'),
        controller_kwargs=CONTROLLER_KWARGS,bc_supervised_updates=bc_updates,
        bc_optimizer_sha256=sha(out/'bc-supervised-optimizer.pt'))
    write(out/'manifest.json',result);print('V13 PPO ENDPOINT',seed,json.dumps(result),flush=True);return result


def continued_worker(seed):
    import torch
    from .learner import IndependentPPO,optimizer_steps
    torch.set_num_threads(1);source=DATA/f'policies/seed-{seed}';metadata=json.loads((source/'manifest.json').read_text())
    out=DATA/f'continued-bc/seed-{seed}';out.mkdir(parents=True,exist_ok=False)
    model=IndependentPPO.load(source/'bc-policy.zip',device='cpu');assert model.num_timesteps==model.actor_steps==0
    data=np.load(DATA/'dataset/dataset.npz');x=torch.tensor(data['observations']);y=torch.tensor(data['actions']);w=torch.tensor(data['weights'])
    optimizer=torch.optim.Adam(model._actor_parameters,lr=3e-4);rng=np.random.default_rng(seed+200000);losses=[]
    for update in range(metadata['actor_steps']):
        index=rng.integers(len(x),size=128);mean=model.policy.get_distribution(x[index]).distribution.mean
        loss=(w[index]*(mean-y[index]).square().mean(dim=1)).mean();optimizer.zero_grad(set_to_none=True);loss.backward()
        torch.nn.utils.clip_grad_norm_(model._actor_parameters,1.);optimizer.step()
        if update%128==0:losses.append(dict(update=update+1,loss=float(loss.detach())))
    model.validate_optimizer_counters();assert optimizer_steps(optimizer)==metadata['actor_steps']
    torch.save(optimizer.state_dict(),out/'supervised-optimizer.pt');model.save(out/'policy.zip')
    result=dict(seed=seed,contract=CONTRACT,observation_dim=55,action_dim=8,learner_class='IndependentPPO',
        steps=0,actor_ppo_steps=0,supervised_optimizer_steps=metadata['actor_steps'],source_bc_sha256=sha(source/'bc-policy.zip'),
        policy_sha256=sha(out/'policy.zip'),supervised_optimizer_sha256=sha(out/'supervised-optimizer.pt'),
        controller_kwargs=CONTROLLER_KWARGS,source_hashes=snapshot(out))
    write(out/'manifest.json',result);write(out/'loss.json',losses);return result


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['collect','learn','continued']);args=p.parse_args()
    if args.stage=='collect':collect();return
    if args.stage=='learn':
        assert not (DATA/'validation').exists() and not (DATA/'final').exists()
        protocol=json.loads((DATA/'dataset/protocol.json').read_text())
        for name,digest in protocol['source_hashes'].items():assert sha(ROOT/name)==digest,('Source changed after data collection',name)
        folder=DATA/'policies';folder.mkdir(exist_ok=False)
        write(folder/'declaration.json',dict(protocol_sha256=sha(Path(__file__).parent/'TRAINING_PROTOCOL.md'),
            source_sha256=sha(__file__),seeds=SEEDS,steps_per_seed=STEPS,fresh_evaluation_not_opened=True))
        fn=worker
    else:
        assert len(json.loads((DATA/'policies/summary.json').read_text()))==3
        folder=DATA/'continued-bc';folder.mkdir(exist_ok=False);fn=continued_worker
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn')) as pool:
        records=[f.result() for f in as_completed([pool.submit(fn,s) for s in SEEDS])]
    write(folder/'summary.json',sorted(records,key=lambda r:r['seed']))


if __name__=='__main__':main()
