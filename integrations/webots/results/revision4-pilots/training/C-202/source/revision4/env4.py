"""Four controlled residual-learning arms; frozen gate executes inside B/D."""
import json,math
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from bootstrap import HERE
from core import Sensor,GAINS,path_values
from plant import advance
from tracking import tracking_lqr
from gating import Gate
from mapping import legacy_units
from reward_model import relative_bonus
PROTOCOL=json.loads((HERE/'protocol.json').read_text())

class ResearchEnv(gym.Env):
    def __init__(self,arm,seed=0):
        self.arm=arm;self.options=PROTOCOL['arms'][arm];self.initial_seed=seed
        self.action_space=spaces.Box(-1.,1.,shape=(1,),dtype=np.float32)
        self.observation_space=spaces.Box(-np.inf,np.inf,shape=(9,),dtype=np.float32)
    def reset(self,*,seed=None,options=None):
        fresh=not hasattr(self,'state');actual_seed=self.initial_seed if fresh and seed is None else seed
        super().reset(seed=actual_seed)
        if fresh or seed is not None:self.domain_rng=np.random.default_rng(int(actual_seed)+70000000)
        self.speed=int(self.np_random.choice([15,20,25]))
        kind=0;amplitude=float(self.np_random.uniform(.5,3));wavelength=float(self.np_random.uniform(100,180));phase=float(self.np_random.uniform(-np.pi,np.pi))
        self.mu=.9;self.stiffness=1.;self.noise=1.;self.delay=0;self.path_capped=False;self.randomized=False
        if self.options['domain_randomization'] and self.domain_rng.random()>=.25:
            self.randomized=True;self.mu=float(self.domain_rng.uniform(.6,.9));self.stiffness=float(self.domain_rng.uniform(.65,1.))
            self.noise=float(self.domain_rng.uniform(1.,2.));self.delay=int(self.domain_rng.integers(0,2))
            cap=.8*self.mu*9.81/(self.speed**2*(2*math.pi/wavelength)**2)
            self.path_capped=amplitude>cap;amplitude=min(amplitude,cap)
        self.path=(kind,amplitude,wavelength,phase)
        y,heading,_=path_values(0,self.path)
        self.state=np.array([0.,y+self.np_random.normal(0,.15),heading+self.np_random.normal(0,.02),0.,0.,0.])
        self.sensor=Sensor(int(self.np_random.integers(0,2**31)),self.noise,self.delay)
        self.steps=0;self.last_command=0.;self.gate=Gate({'horizon_steps':20,'relative_margin':.01});self.active=0;self.bonus_sum=0.
        self.obs,self.estimate,self.kappa=self.sensor.measure(self.state,self.speed,self.path)
        return self.obs,{}
    def step(self,action):
        requested=float(legacy_units(action)[0])*.5
        baseline=tracking_lqr(self.estimate,self.speed,self.kappa);weight=1.;reason='ungated'
        command=float(np.clip(baseline+requested,-.5,.5))
        if self.options['gate']:
            t=self.steps*.01
            command,weight,reason,_,_=self.gate.choose(t,baseline,(self.steps+1,t,requested),self.estimate,self.state[5],self.speed,self.kappa,GAINS[self.speed],'residual')
        bonus=j0=j1=0.
        if self.options['relative_reward']:bonus,j0,j1=relative_bonus(self.state,command,baseline,self.speed,self.path,self.mu,self.stiffness,GAINS[self.speed])
        if command==baseline:assert bonus==0.
        previous=self.last_command;self.state=advance(self.state,command,self.speed,self.mu,self.stiffness);self.steps+=1
        y,heading,_=path_values(self.state[0],self.path);ey=self.state[1]-y;ep=self.state[2]-heading
        failed=abs(ey)>2.5 or abs(ep)>.6 or not np.isfinite(self.state).all()
        reward=math.exp(-(ey/.5)**2-.2*(ep/.1)**2)+.05-.005*(command/.5)**2-.001*((command-previous)/.5)**2
        if failed:reward-=10.
        reward+=bonus;self.last_command=command;self.active+=int(weight>0);self.bonus_sum+=bonus
        self.obs,self.estimate,self.kappa=self.sensor.measure(self.state,self.speed,self.path)
        info=dict(error=ey,failed=failed,baseline=baseline,command=command,requested_residual=requested,gate_weight=weight,gate_reason=reason,relative_bonus=bonus,lqr_cost=j0,executed_cost=j1,episode_gate_fraction=self.active/self.steps,episode_mean_bonus=self.bonus_sum/self.steps,mu=self.mu,stiffness=self.stiffness,sensor_noise=self.noise,sensor_delay=self.delay,path_capped=int(self.path_capped))
        return self.obs,float(reward),bool(failed),self.steps>=800,info
