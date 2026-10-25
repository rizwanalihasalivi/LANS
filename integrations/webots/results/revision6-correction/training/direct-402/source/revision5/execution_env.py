"""Execution-aware interface repair, with explicit history and optional randomization.

No claim of improved PPO performance: interface is validated with small smoke
runs only. New 20-component observations are incompatible with old policies.
"""
import sys,math
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from bootstrap import RESEARCH
sys.path.append(str(RESEARCH/'revision4'))
from execution import Execution,matched_lqr
from comparison import configure_lqr
from core import path_values,GAINS,Sensor
from plant import advance
from reward_model import relative_bonus


class ExecutionEnv(gym.Env):
    def __init__(self,seed=0,randomize=False,service_ticks=None):
        # Reset distribution is inherited; original sources remain frozen.
        super().__init__()
        configure_lqr()
        self.initial_seed=seed;self.randomize=randomize
        self.action_space=spaces.Box(-1.,1.,shape=(1,),dtype=np.float32)
        self.observation_space=spaces.Box(-np.inf,np.inf,shape=(20,),dtype=np.float32)
        self.fixed_service_ticks=service_ticks

    def observation(self):
        return np.concatenate([self.obs,self.execution.context(self.steps*.01),[self.service_ticks/10]]).astype(np.float32)

    def reset(self,*,seed=None,options=None):
        fresh=not hasattr(self,'state');actual_seed=self.initial_seed if fresh and seed is None else seed
        super().reset(seed=actual_seed)
        if fresh or seed is not None:self.domain_rng=np.random.default_rng(int(actual_seed)+70000000)
        self.speed=int(self.np_random.choice([15,20,25]))
        kind=0;amplitude=float(self.np_random.uniform(.5,3));wavelength=float(self.np_random.uniform(100,180));phase=float(self.np_random.uniform(-np.pi,np.pi))
        self.mu=.9;self.stiffness=1.;self.noise=1.;self.delay=0;self.path_capped=False;self.randomized=False
        if self.randomize and self.domain_rng.random()>=.25:
            self.randomized=True;self.mu=float(self.domain_rng.uniform(.6,.9));self.stiffness=float(self.domain_rng.uniform(.65,1.))
            self.noise=float(self.domain_rng.uniform(1.,2.));self.delay=int(self.domain_rng.integers(0,2))
            cap=.8*self.mu*9.81/(self.speed**2*(2*math.pi/wavelength)**2)
            self.path_capped=amplitude>cap;amplitude=min(amplitude,cap)
        self.path=(kind,amplitude,wavelength,phase)
        y,heading,_=path_values(0,self.path)
        self.state=np.array([0.,y+self.np_random.normal(0,.15),heading+self.np_random.normal(0,.02),0.,0.,0.])
        self.sensor=Sensor(int(self.np_random.integers(0,2**31)),self.noise,self.delay)
        self.steps=0;self.last_command=0.;self.active=0;self.bonus_sum=0.
        self.obs,self.estimate,self.kappa=self.sensor.measure(self.state,self.speed,self.path)
        self.execution=Execution()
        self.service_ticks=int(self.domain_rng.choice([0,1,2,10])) if self.fixed_service_ticks is None else self.fixed_service_ticks
        return self.observation(),{}

    def step(self,action):
        value=np.asarray(action).reshape(-1)
        if value.size!=1 or not np.isfinite(value).all():raise ValueError('one finite action required')
        proposed=.08*float(np.clip(value[0],-1,1));t=self.steps*.01
        # Actor, baseline and gate receive the same measured speed, not hidden scheduled speed.
        speed=max(5.,float(self.obs[4])*25)
        baseline,gain=matched_lqr(self.estimate,speed,self.kappa)
        command,info=self.execution.step(t,proposed,self.service_ticks,baseline,self.estimate,self.state[5],speed,self.kappa,gain)
        bonus,j0,j1=relative_bonus(self.state,command,baseline,self.speed,self.path,self.mu,self.stiffness,GAINS[self.speed])
        previous=self.last_command;old_actuator=self.state[5]
        self.state=advance(self.state,command,self.speed,self.mu,self.stiffness);self.steps+=1
        y,h,_=path_values(self.state[0],self.path);ey=self.state[1]-y;ep=self.state[2]-h
        failed=abs(ey)>2.5 or abs(ep)>.6 or not np.isfinite(self.state).all()
        tracking=math.exp(-(ey/.5)**2-.2*(ep/.1)**2)
        effort=-.005*(command/.5)**2;change=-.001*((command-previous)/.5)**2;survival=.05-10*failed
        reward=tracking+effort+change+survival+bonus
        self.last_command=command
        info.update(error=ey,proposed_residual_rad=proposed,baseline_rad=baseline,command_rad=command,
            actuator_before_rad=old_actuator,actuator_after_rad=self.state[5],controller_speed_mps=speed,
            command_time_s=t,state_time_s=self.steps*.01,reward_tracking=tracking,reward_effort=effort,
            reward_change=change,reward_survival=survival,reward_relative=bonus,
            realized_lqr_cost=j0,realized_fused_cost=j1,mu=self.mu,stiffness=self.stiffness,
            sensor_noise=self.noise,sensor_delay_ticks=self.delay,service_ticks=self.service_ticks)
        self.obs,self.estimate,self.kappa=self.sensor.measure(self.state,self.speed,self.path)
        return self.observation(),float(reward),bool(failed),self.steps>=800,info
