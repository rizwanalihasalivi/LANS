"""Finite development-only PPO training and deterministic calibration.

PPO requests are synchronous during training. Reward describes the actual selected,
delayed and applied closed-loop command, including rejection by the supervisor.
This is submitted-proposal credit, not a claim of executed-action-only gradients.
"""
from dataclasses import asdict
import json
from pathlib import Path
import platform
import shutil
import time
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from .controller import Pipeline, Proposal
from .physics import Command, Config, Route, baseline, constrain
from .simulation import initial, move_npcs, Network, truth_metrics
from .inference import CONTRACT, FEATURES, sha


class TrainingEnv(gym.Env):
    def __init__(self):
        super().__init__();self.cfg=Config()
        self.observation_space=spaces.Box(-5.,5.,(17,),np.float32)
        self.action_space=spaces.Box(-1.,1.,(1,),np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.scenario=str(self.np_random.choice(['following','merge','crossing','curved']))
        route,self.ego,self.npcs=initial(self.scenario,float(self.np_random.uniform(-.4,.4)))
        delay=float(self.np_random.choice([0.,.05,.1]))
        self.pipe=Pipeline(route,self.scenario,self.cfg,delay,mode='ppo')
        self.pipe.expected=set(self.npcs);self.network=Network();self.now=0.;self.tick=0;self.sequence=0
        self.network.emit(0.,self.ego,self.npcs,self.pipe.inbox)
        self.stiffness=float(self.np_random.uniform(.85,1.15))
        self.done=False
        return self.pipe.features(0.),{}

    def step(self, action):
        if self.done:raise RuntimeError('reset required')
        a=np.asarray(action).reshape(-1)
        if a.shape!=(1,) or not np.isfinite(a).all():raise ValueError('finite scalar proposal required')
        self.sequence+=1
        p=Proposal(self.sequence,self.now,self.now,.08*float(np.clip(a[0],-1,1)),time.monotonic())
        assert self.pipe.accept(p,self.now)
        previous=self.pipe.applied
        decision=self.pipe.decide(self.now)
        self.ego=self.pipe.apply(self.now,self.ego,self.stiffness)
        move_npcs(self.npcs,self.cfg.dt,self.pipe.route,self.scenario)
        metrics=truth_metrics(self.ego,self.npcs,self.pipe.route,self.cfg)
        rate=(self.pipe.applied.steering-previous.steering)/self.cfg.dt
        reward=1.-2*metrics['error']**2-.5*metrics['heading_error']**2-.02*rate**2
        reward-=.002*self.pipe.applied.accel**2
        terminated=metrics['collision'] or abs(metrics['error'])>2.5
        reward-=20*terminated
        self.tick+=1;self.now=self.tick*self.cfg.dt
        self.network.emit(self.now,self.ego,self.npcs,self.pipe.inbox)
        self.done=bool(terminated or self.tick>=80)
        return self.pipe.features(self.now),float(reward),bool(terminated),self.tick>=80,dict(**metrics,selected=decision['source'])


def train(output, seeds=(42,43,44), steps=2048):
    import torch
    from stable_baselines3 import PPO
    import stable_baselines3
    torch.set_num_threads(1)
    destination=Path(output);destination.mkdir(parents=True,exist_ok=False)
    snapshot=destination/'source';snapshot.mkdir()
    for p in Path(__file__).parent.glob('*.py'):shutil.copyfile(p,snapshot/p.name)
    source_hashes={p.name:sha(p) for p in snapshot.glob('*.py')}
    for seed in seeds:
        env=TrainingEnv()
        model=PPO('MlpPolicy',env,seed=seed,device='cpu',n_steps=128,batch_size=64,n_epochs=3,
                  policy_kwargs=dict(net_arch=[32,32]),learning_rate=3e-4,verbose=0)
        model.learn(total_timesteps=steps)
        folder=destination/f'seed-{seed}';folder.mkdir()
        model.save(folder/'policy.zip')
        manifest=dict(contract=CONTRACT,features=FEATURES,scale_rad=.08,policy_sha256=sha(folder/'policy.zip'),
                      seed=seed,steps=int(model.num_timesteps),config=asdict(env.cfg),
                      purpose='integration_training_only_not_scientific_confirmation',
                      training_credit='submitted proposal; reward from actual gated/FIFO-applied transition',
                      source_hashes=source_hashes,
                      versions=dict(python=platform.python_version(),sb3=stable_baselines3.__version__,torch=torch.__version__))
        (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
        env.close()
        print(f'TRAINED seed={seed}, steps={model.num_timesteps}, bundle={folder}',flush=True)


def calibrate(path):
    target=Path(path)
    if target.exists():raise FileExistsError(target)
    rows=[]
    for ky in (0.,.01,.02,.04):
        for kp in (0.,.02,.08):
            total=0.
            for kind in ('straight','sine','lane_change'):
                route=Route(kind);pipe=Pipeline(route)
                for ey in (-.4,.4):
                    for ep in (-.03,.03):
                        y,h,_=route.geometry(25.)
                        z=np.array([25.,y+ey,h+ep,12.,0.,0.])
                        residual=float(np.clip(-ky*ey-kp*ep,-.08,.08))
                        first=constrain(Command(baseline(z,route)+residual,0.),Command(),pipe.cfg)
                        value,_=pipe.cost(z,first,residual,0.,(),pipe.cfg.horizon)
                        total+=value
            rows.append(dict(ky=ky,kpsi=kp,cost=total))
    selected=min(rows,key=lambda r:(r['cost'],r['ky']+r['kpsi']))
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(dict(selected=selected,candidates=rows,
        scope='fixed finite nominal development grid; not a global optimum; no evaluation data used'),indent=2))
    return selected['ky'],selected['kpsi']
