"""Discrete residual wrapper with the original execution/reward path unchanged."""
import json
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from bootstrap import HERE,RESEARCH
from execution_env import ExecutionEnv
from execution import Execution
from core import Sensor,path_values
P=json.loads((HERE/'protocol.json').read_text());G=json.loads((RESEARCH/'revision6/protocol.json').read_text())


class TrainingEnv(ExecutionEnv):
    def __init__(self,pair,slot,seed,credit=False):
        super().__init__(seed=seed,randomize=False,service_ticks=0)
        self.action_space=spaces.Discrete(5);self.pair=pair;self.slot=slot;self.episode_index=-1;self.credit=credit
    def reset(self,*,seed=None,options=None):
        fresh=not hasattr(self,'state');actual=self.initial_seed if fresh and seed is None else seed
        gym.Env.reset(self,seed=actual)
        self.episode_index=0 if fresh or seed is not None else self.episode_index+1
        self.speed=int(self.np_random.choice(G['speeds']));self.path_name=list(G['paths'])[int(self.np_random.integers(0,2))]
        self.region=list(G['scenarios'])[int(self.np_random.integers(0,6))];case=G['scenarios'][self.region]
        self.path=tuple(float(x) for x in G['paths'][self.path_name]);self.mu=case['mu'];self.stiffness=case['stiffness']
        self.noise=case['noise'];self.delay=case['sensor_delay_steps'];self.service_ticks=case['service_ticks']
        self.noise_id=920000000+self.pair*1000000+self.slot*10000+self.episode_index
        y,h,_=path_values(0,self.path);self.state=np.array([0.,y+.15,h+.01,0.,0.,0.])
        self.sensor=Sensor(self.noise_id,self.noise,self.delay);self.execution=Execution()
        self.steps=0;self.last_command=0.;self.active=0;self.bonus_sum=0.
        self.horizon=int(np.ceil((220/self.speed+2)/.01));self.obs,self.estimate,self.kappa=self.sensor.measure(self.state,self.speed,self.path)
        return self.observation(),dict(noise_id=self.noise_id)
    def step(self,action):
        value=np.asarray(action)
        if value.size!=1 or not np.isfinite(value).all() or float(value.item())!=int(value.item()) or not 0<=int(value.item())<5:
            raise ValueError('one categorical action in0..4 required')
        index=int(value.item());mapped=np.array([P['candidates_rad'][index]/.08],dtype=np.float32)
        from credit10 import proposal_credit
        available=self.execution.pending is None or self.execution.pending[0]<=self.steps*.01+1e-9
        bonus,j0,j1,applied,_=proposal_credit(self,.08*float(mapped[0])) if self.credit else (0.,0.,0.,0,available)
        obs,reward,failed,_,info=super().step(mapped)
        old_reward=reward
        if self.credit:reward=bonus-10.*failed
        info.update(action_class=index,noise_id=self.noise_id,training_region=self.region,path_name=self.path_name,
            decision_eligible=available,credit_bonus=bonus,credit_zero_cost=j0,credit_proposal_cost=j1,
            credit_predicted_applied_ticks=applied,original_reward=old_reward,training_reward=reward)
        return obs,reward,failed,self.steps>=self.horizon,info
