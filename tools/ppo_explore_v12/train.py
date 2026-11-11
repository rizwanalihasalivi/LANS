"""Prospectively budgeted PPO on controllable delays, with wider exploration."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import json,multiprocessing as mp,shutil
import gymnasium as gym
import numpy as np
from integrations.unified_lans.inference import sha
from tools.ppo_plan_v11.learning import Env as FrozenEnv,ROOT,DATA as V11,CONTRACT
from tools.ppo_plan_v11.damped import install_damping,optimizer_steps
from tools.ppo_plan_v11.probe import dump
from tools.ppo_plan_v11.train import snapshot as frozen_snapshot

DATA=ROOT/'results/ppo-explore-v12';SEEDS=(42,43,44)


def curriculum(rng):
    case=dict(stage='ppo_exploration_training',scenario=str(rng.choice(['following','merge','crossing','curved'])),
        speed=float(rng.choice([8.,12.,16.])),delay=float(rng.choice([0.,.05])),mirror=int(rng.choice([-1,1])),
        stiffness=float(rng.uniform(.75,1.25)),lateral=float(rng.uniform(.15,.45)),heading=float(rng.uniform(-.02,.02)),
        phase=float(rng.uniform(10,28)),amplitude=float(rng.uniform(.9,1.3)),npc_x_shift=float(rng.uniform(-5,5)),
        npc_speed_scale=float(rng.uniform(.75,1.25)),network='nominal',network_seed=int(rng.integers(1_200_000_000,1_900_000_000)))
    case['lateral']*=case['mirror'];return case


class Env(FrozenEnv):
    def reset(self,*,seed=None,options=None):
        gym.Env.reset(self,seed=seed)
        if not options or 'case' not in options:
            options=dict(case=curriculum(self.np_random))
        return super().reset(seed=None,options=options)


def snapshot(out):
    hashes=frozen_snapshot(out)
    for p in [*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.md')]:
        name=str(p.relative_to(ROOT));hashes[name]=sha(p);target=out/'source'/name
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    return hashes


def configure(model):
    import torch
    if model.observation_space.shape!=(40,) or model.action_space.shape!=(8,):
        raise ValueError('frozen forty-feature/eight-knot policy required')
    with torch.no_grad():model.policy.log_std.fill_(-2.5)
    return install_damping(model,.1)


def worker(seed):
    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback
    torch.set_num_threads(1);out=DATA/f'policies/seed-{seed}';out.mkdir(parents=True,exist_ok=False)
    source=V11/f'policies/seed-{seed}/bc-policy.zip';env=Env(trace=out/'training.jsonl')
    model=PPO.load(source,env=env,seed=seed,device='cpu')
    assert model.num_timesteps==0 and optimizer_steps(model)==0
    assert (model.learning_rate,model.n_steps,model.batch_size,model.n_epochs,model.target_kl)==(1e-4,1024,128,10,.01)
    handles,counts=configure(model)
    model.save(out/'initial-exploration-policy.zip')
    dump(out/'protocol.json',dict(seed=seed,contract=CONTRACT,new_steps=65536,initial_log_std=-2.5,actor_step_factor=.1,
        source_bc_sha256=sha(source),declaration_sha256=sha(Path(__file__).parent/'PROTOCOL.md'),source_hashes=snapshot(out)))
    class Checkpoint(BaseCallback):
        def _on_step(self):
            if self.num_timesteps%16384==0:
                model.save(out/f'checkpoint-{self.num_timesteps}.zip')
                print('EXPLORATION PPO',seed,self.num_timesteps,'/65536','Adam steps',counts[0],flush=True)
            return True
    try:
        model.learn(total_timesteps=65536,callback=Checkpoint())
        for handle in handles:handle.remove()
        model.save(out/'policy.zip')
    finally:env.close()
    assert model.num_timesteps==65536 and counts[0]==optimizer_steps(model)
    record=dict(seed=seed,contract=CONTRACT,steps=65536,optimizer_steps=counts[0],sb3_epoch_counter=model._n_updates,
        policy_sha256=sha(out/'policy.zip'),source_bc_sha256=sha(source),trace_sha256=sha(out/'training.jsonl'),
        initial_policy_sha256=sha(out/'initial-exploration-policy.zip'))
    dump(out/'manifest.json',record);return record


def main():
    root=DATA/'policies';root.mkdir(parents=True,exist_ok=False)
    assert not (DATA/'evaluation').exists()
    dump(root/'declaration.json',dict(source_sha256=sha(__file__),protocol_sha256=sha(Path(__file__).parent/'PROTOCOL.md'),
        diagnostic_v11_assessment_sha256=sha(V11/'damped-evaluation/assessment.json'),
        fresh_evaluation_not_opened=True,seeds=list(SEEDS),steps_per_seed=65536))
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn')) as pool:
        records=[f.result() for f in as_completed([pool.submit(worker,s) for s in SEEDS])]
    dump(root/'summary.json',sorted(records,key=lambda r:r['seed']))


if __name__=='__main__':main()
