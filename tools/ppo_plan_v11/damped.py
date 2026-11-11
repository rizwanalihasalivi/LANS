"""Actor-step damping for actual PPO updates, without teacher gradients."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import json,multiprocessing as mp
from integrations.unified_lans.inference import sha
from .learning import DATA,CONTRACT,Env
from .train import snapshot
from .probe import dump


def optimizer_steps(model):
    state=model.policy.optimizer.state_dict()['state']
    steps=[int(value['step']) for value in state.values() if 'step' in value]
    return max(steps,default=0)


def install_damping(model,factor=.01):
    import torch
    actor=list(model.policy.mlp_extractor.policy_net.parameters())+list(model.policy.action_net.parameters())+[model.policy.log_std]
    saved=[];counts=[0]
    def before(optimizer,args,kwargs):saved[:]=[p.detach().clone() for p in actor]
    def after(optimizer,args,kwargs):
        with torch.no_grad():
            for parameter,previous in zip(actor,saved):parameter.copy_(previous+factor*(parameter-previous))
        counts[0]+=1
    return (model.policy.optimizer.register_step_pre_hook(before),model.policy.optimizer.register_step_post_hook(after)),counts


def worker(seed):
    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback
    torch.set_num_threads(1);out=DATA/f'policies-damped/seed-{seed}';out.mkdir(parents=True,exist_ok=False)
    env=Env(trace=out/'training.jsonl');source=DATA/f'policies/seed-{seed}/bc-policy.zip'
    model=PPO.load(source,env=env,seed=seed,device='cpu');assert model.num_timesteps==0 and optimizer_steps(model)==0
    handles,counts=install_damping(model)
    dump(out/'protocol.json',dict(seed=seed,contract=CONTRACT,new_steps=32768,actor_step_factor=.01,
        source_bc_sha256=sha(source),declaration_sha256=sha(Path(__file__).parent/'DAMPED_PROTOCOL.md'),source_hashes=snapshot(out)))
    class Checkpoint(BaseCallback):
        def _on_step(self):
            if self.num_timesteps%4096==0:
                model.save(out/f'checkpoint-{self.num_timesteps}.zip');print('DAMPED PPO',seed,self.num_timesteps,'/32768','Adam steps',counts[0],flush=True)
            return True
    try:
        model.learn(total_timesteps=32768,callback=Checkpoint())
        for handle in handles:handle.remove()
        model.save(out/'policy.zip')
    finally:env.close()
    assert model.num_timesteps==32768 and counts[0]==optimizer_steps(model)
    record=dict(seed=seed,contract=CONTRACT,steps=32768,optimizer_steps=counts[0],sb3_epoch_counter=model._n_updates,
        policy_sha256=sha(out/'policy.zip'),source_bc_sha256=sha(source),trace_sha256=sha(out/'training.jsonl'))
    dump(out/'manifest.json',record);return record


def main():
    root=DATA/'policies-damped';root.mkdir(exist_ok=False)
    assert not (DATA/'evaluation/assessment.json').exists(),'Register before the original prospective assessment exists'
    dump(root/'declaration.json',dict(source_sha256=sha(__file__),protocol_sha256=sha(Path(__file__).parent/'DAMPED_PROTOCOL.md'),
        original_assessment_not_available=True,old_optimizer_steps=[33,33,32],reference_protocol_sha256=sha(DATA/'evaluation/protocol.json')))
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn')) as pool:
        records=[f.result() for f in as_completed([pool.submit(worker,s) for s in (42,43,44)])]
    dump(root/'summary.json',sorted(records,key=lambda r:r['seed']))


if __name__=='__main__':main()
