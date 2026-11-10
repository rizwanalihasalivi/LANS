"""Teacher-retention PPO arm, declared from training diagnostics only."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import json,multiprocessing as mp,shutil
import numpy as np
from integrations.unified_lans.inference import sha
from .core import ROOT,DATA,CONTRACT,dump
from .train import TrainingEnv,snapshot


def install_anchor(model,observations,actions,weights,seed):
    import torch
    generator=np.random.default_rng(9000+seed);losses=[]
    def hook(optimizer,args,kwargs):
        indices=generator.integers(len(observations),size=128)
        mean=model.policy.get_distribution(observations[indices]).distribution.mean
        loss=.5*(weights[indices]*(mean-actions[indices]).square().mean(dim=1)).mean()
        loss.backward();torch.nn.utils.clip_grad_norm_(model.policy.parameters(),.5)
        losses.append(float(loss.detach()))
    return model.policy.optimizer.register_step_pre_hook(hook),losses


def worker(seed):
    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback
    torch.set_num_threads(1)
    folder=DATA/f'policies-anchor/seed-{seed}';folder.mkdir(parents=True,exist_ok=False)
    env=TrainingEnv(trace=folder/'training.jsonl');source=DATA/f'policies/seed-{seed}/bc-policy.zip'
    model=PPO.load(source,env=env,seed=seed,device='cpu');assert model.num_timesteps==0
    data=np.load(DATA/'teacher/dataset.npz')
    handle,losses=install_anchor(model,torch.tensor(data['observations']),torch.tensor(data['actions']),torch.tensor(data['weights']),seed)
    dump(folder/'protocol.json',dict(seed=seed,contract=CONTRACT,new_steps=16384,source_policy_sha256=sha(source),
        dataset_sha256=sha(DATA/'teacher/dataset.npz'),anchor_coefficient=.5,batch_size=128,
        declaration_sha256=sha(Path(__file__).parent/'ANCHOR_PROTOCOL.md'),source_hashes=snapshot(folder)))
    shutil.copyfile(Path(__file__).parent/'ANCHOR_PROTOCOL.md',folder/'ANCHOR_PROTOCOL.md')
    class Checkpoint(BaseCallback):
        def _on_step(self):
            if self.num_timesteps%2048==0:
                model.save(folder/f'checkpoint-{self.num_timesteps}.zip');print('ANCHORED PPO',seed,self.num_timesteps,'/16384',flush=True)
            return True
    try:
        model.learn(total_timesteps=16384,callback=Checkpoint());handle.remove();model.save(folder/'policy.zip')
    finally:env.close()
    assert model.num_timesteps==16384 and losses
    dump(folder/'anchor-loss.json',losses)
    record=dict(seed=seed,contract=CONTRACT,steps=16384,policy_sha256=sha(folder/'policy.zip'),
        bc_policy_sha256=sha(source),trace_sha256=sha(folder/'training.jsonl'),anchor_steps=len(losses))
    dump(folder/'manifest.json',record);return record


def main():
    root=DATA/'policies-anchor';root.mkdir(exist_ok=False)
    declaration=Path(__file__).parent/'ANCHOR_PROTOCOL.md'
    assert not (DATA/'evaluation/assessment.json').exists(),'Declare this arm before prospective assessment is available'
    dump(root/'declaration.json',dict(protocol_sha256=sha(declaration),source_sha256=sha(Path(__file__)),
        diagnostics_sha256=sha(DATA/'training-diagnostics.json'),original_assessment_not_available=True,
        reference_protocol_sha256=sha(DATA/'evaluation/protocol.json')))
    with ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('spawn')) as pool:
        result=[f.result() for f in as_completed([pool.submit(worker,s) for s in (42,43,44)])]
    dump(root/'summary.json',sorted(result,key=lambda r:r['seed']))


if __name__=='__main__':main()
