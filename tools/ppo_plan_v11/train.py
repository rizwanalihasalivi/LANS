"""Full-data sequence BC initialization, then genuine PPO for all fixed seeds."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import argparse,json,multiprocessing as mp,shutil
import numpy as np
from integrations.unified_lans.inference import sha
from .learning import ROOT,DATA,CONTRACT,Env,reconstruct
from .probe import dump


def snapshot(out):
    files=[*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.md'),
        ROOT/'tools/ppo_benefit_v10/core.py',ROOT/'tools/unified_control_v9/learning.py',
        *(ROOT/'integrations/unified_lans').glob('*.py'),ROOT/'tools/unified_campaign/study.py',
        ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py']
    for v in range(4,9):files.extend((ROOT/f'tools/unified_control_v{v}').glob('*.py'))
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    for p in files:
        target=out/'source'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    return hashes


def collect():
    out=DATA/'dataset';out.mkdir(exist_ok=False)
    checked=json.loads((DATA/'probe/verification.json').read_text());assert checked['passed']
    protocol=json.loads((DATA/'probe/protocol.json').read_text());features=[];labels=[];hashes={}
    for case in protocol['cases']:
        path=DATA/f'probe/{case["id"]:03d}-sequence_teacher.jsonl'
        meta=json.loads(path.with_suffix('.json').read_text());assert sha(path)==meta['raw_sha256']
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        x=reconstruct(case,rows);y=np.asarray([r['label'] for r in rows],np.float32)
        assert x.shape==(len(rows),40) and y.shape==(len(rows),8)
        features.extend(x);labels.extend(y);hashes[str(path.relative_to(ROOT))]=sha(path)
    x=np.asarray(features,np.float32);y=np.asarray(labels,np.float32);weights=np.where(np.max(abs(y),axis=1)>1e-8,10.,1.).astype(np.float32)
    np.savez_compressed(out/'dataset.npz',observations=x,actions=y,weights=weights)
    dump(out/'protocol.json',dict(contract=CONTRACT,inputs=hashes,source_hashes=snapshot(out),no_future_truth_features=True))
    dump(out/'manifest.json',dict(samples=len(x),features=40,actions=8,dataset_sha256=sha(out/'dataset.npz')))
    print('CAUSAL SEQUENCE DATASET',len(x),'samples',flush=True)


def worker(seed):
    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback
    torch.set_num_threads(1);torch.manual_seed(seed);rng=np.random.default_rng(seed)
    out=DATA/f'policies/seed-{seed}';out.mkdir(parents=True,exist_ok=False);env=Env(trace=out/'training.jsonl')
    model=PPO('MlpPolicy',env,seed=seed,device='cpu',learning_rate=1e-4,n_steps=1024,batch_size=128,n_epochs=10,
        gamma=.99,gae_lambda=.95,ent_coef=0.,target_kl=.01,policy_kwargs=dict(net_arch=dict(pi=[128,128],vf=[128,128]),log_std_init=-5.))
    data=np.load(DATA/'dataset/dataset.npz');x=torch.tensor(data['observations']);y=torch.tensor(data['actions']);weights=torch.tensor(data['weights'])
    parameters=list(model.policy.mlp_extractor.policy_net.parameters())+list(model.policy.action_net.parameters())
    optimizer=torch.optim.Adam(parameters,lr=3e-4);losses=[]
    for epoch in range(32):
        permutation=rng.permutation(len(x));loss_sum=0.
        for start in range(0,len(x),128):
            indices=permutation[start:start+128];mean=model.policy.get_distribution(x[indices]).distribution.mean
            loss=(weights[indices]*(mean-y[indices]).square().mean(dim=1)).mean()
            optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(parameters,1.);optimizer.step();loss_sum+=float(loss.detach())
        losses.append(loss_sum)
    model.policy.optimizer=torch.optim.Adam(model.policy.parameters(),lr=1e-4,eps=1e-5)
    model.save(out/'bc-policy.zip');dump(out/'bc-loss.json',losses)
    dump(out/'protocol.json',dict(seed=seed,contract=CONTRACT,bc_epochs=32,new_steps=32768,
        dataset_sha256=sha(DATA/'dataset/dataset.npz'),source_hashes=snapshot(out),no_checkpoint_selection=True))
    class Checkpoint(BaseCallback):
        def _on_step(self):
            if self.num_timesteps%4096==0:
                model.save(out/f'checkpoint-{self.num_timesteps}.zip');print('SEQUENCE PPO',seed,self.num_timesteps,'/32768',flush=True)
            return True
    try:model.learn(total_timesteps=32768,callback=Checkpoint());model.save(out/'policy.zip')
    finally:env.close()
    assert model.num_timesteps==32768
    record=dict(seed=seed,contract=CONTRACT,steps=32768,policy_sha256=sha(out/'policy.zip'),bc_policy_sha256=sha(out/'bc-policy.zip'),
        trace_sha256=sha(out/'training.jsonl'),actual_ppo_updates=model._n_updates)
    dump(out/'manifest.json',record);return record


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['collect','train']);args=parser.parse_args()
    if args.stage=='collect':collect();return
    protocol=json.loads((DATA/'dataset/protocol.json').read_text())
    for name,digest in protocol['source_hashes'].items():assert sha(ROOT/name)==digest,('Source changed before training',name)
    (DATA/'policies').mkdir(exist_ok=False)
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn')) as pool:
        result=[f.result() for f in as_completed([pool.submit(worker,s) for s in (42,43,44)])]
    dump(DATA/'policies/summary.json',sorted(result,key=lambda r:r['seed']))


if __name__=='__main__':main()
