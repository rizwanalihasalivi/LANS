"""Match extra teacher updates without attributing supervision to PPO."""
from pathlib import Path
import json
import numpy as np
from integrations.unified_lans.inference import sha
from .core import DATA,CONTRACT,dump
from .train import snapshot


def main():
    import torch
    from stable_baselines3 import PPO
    torch.set_num_threads(1);root=DATA/'policies-continued-bc';root.mkdir(exist_ok=False)
    assert not (DATA/'anchor-evaluation/assessment.json').exists()
    dump(root/'declaration.json',dict(source_sha256=sha(__file__),protocol_sha256=sha(Path(__file__).parent/'ABLATION_PROTOCOL.md'),
        anchored_assessment_not_available=True,optimizer_steps=1280,supervised_only=True))
    data=np.load(DATA/'teacher/dataset.npz');obs=torch.tensor(data['observations']);actions=torch.tensor(data['actions']);weights=torch.tensor(data['weights'])
    result=[]
    for seed in (42,43,44):
        folder=root/f'seed-{seed}';folder.mkdir();source=DATA/f'policies/seed-{seed}/bc-policy.zip'
        model=PPO.load(source,device='cpu');assert model.num_timesteps==0
        generator=np.random.default_rng(9000+seed);losses=[]
        dump(folder/'protocol.json',dict(seed=seed,source_policy_sha256=sha(source),source_hashes=snapshot(folder),
            declaration_sha256=sha(root/'declaration.json'),teacher_sha256=sha(DATA/'teacher/dataset.npz'),supervised_only=True))
        for _ in range(1280):
            indices=generator.integers(len(obs),size=128);mean=model.policy.get_distribution(obs[indices]).distribution.mean
            loss=.5*(weights[indices]*(mean-actions[indices]).square().mean(dim=1)).mean()
            model.policy.optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.policy.parameters(),.5)
            model.policy.optimizer.step();losses.append(float(loss.detach()))
        model.save(folder/'policy.zip');dump(folder/'loss.json',losses)
        record=dict(seed=seed,contract=CONTRACT,steps=0,supervised_updates=1280,policy_sha256=sha(folder/'policy.zip'),
            bc_policy_sha256=sha(source),supervised_only=True)
        dump(folder/'manifest.json',record);result.append(record);print('CONTINUED BC',seed,'1280 supervised updates, 0 PPO steps',flush=True)
    dump(root/'summary.json',result)


if __name__=='__main__':main()
