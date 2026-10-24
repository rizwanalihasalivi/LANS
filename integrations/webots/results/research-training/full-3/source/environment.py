import numpy as np
import gymnasium as gym
from gymnasium import spaces
from core import advance, Sensor, path_values, lqr

class TrainingEnv(gym.Env):
    metadata={}
    def __init__(self, role='full', seed=0):
        self.role=role;self.initial_seed=seed
        self.action_space=spaces.Box(-1.,1.,shape=(1,),dtype=np.float32)
        self.observation_space=spaces.Box(-np.inf,np.inf,shape=(9,),dtype=np.float32)
    def reset(self,*,seed=None,options=None):
        super().reset(seed=self.initial_seed if not hasattr(self,'state') and seed is None else seed)
        self.speed=int(self.np_random.choice([15,20,25]))
        self.path=(0,float(self.np_random.uniform(.5,3)),float(self.np_random.uniform(100,180)),float(self.np_random.uniform(-np.pi,np.pi)))
        y,psi,_=path_values(0,self.path)
        self.state=np.array([0.,y+self.np_random.normal(0,.15),psi+self.np_random.normal(0,.02),0.,0.,0.])
        self.sensor=Sensor(int(self.np_random.integers(0,2**31)))
        self.steps=0;self.last_command=0.
        self.obs,self.estimate,self.kappa=self.sensor.measure(self.state,self.speed,self.path)
        return self.obs,{}
    def step(self,action):
        requested=float(np.clip(action[0],-1,1))*.5
        baseline=lqr(self.estimate,self.speed,self.kappa)
        command=float(np.clip(requested+(baseline if self.role=='residual' else 0),-.5,.5))
        self.state=advance(self.state,command,self.speed)
        self.steps+=1
        y,heading,_=path_values(self.state[0],self.path)
        ey=self.state[1]-y;ep=self.state[2]-heading
        failed=abs(ey)>2.5 or abs(ep)>.6 or not np.isfinite(self.state).all()
        reward=1.-(ey/.5)**2-.2*(ep/.1)**2-.02*(command/.1)**2-.01*((command-self.last_command)/.02)**2
        if failed:reward-=20
        self.last_command=command
        self.obs,self.estimate,self.kappa=self.sensor.measure(self.state,self.speed,self.path)
        return self.obs,float(reward),bool(failed),self.steps>=800,{'error':ey,'failed':failed}
