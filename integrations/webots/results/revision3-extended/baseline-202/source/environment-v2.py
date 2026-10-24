"""Positive survival reward removes the early-termination incentive in the pilot reward."""
import math
from environment import TrainingEnv
from core import path_values

class SurvivalEnv(TrainingEnv):
    def step(self,action):
        previous=self.last_command
        observation,_,terminated,truncated,info=super().step(action)
        _,reference_heading,_=path_values(self.state[0],self.path)
        ey=info['error'];heading=self.state[2]-reference_heading
        reward=math.exp(-(ey/.5)**2-.2*(heading/.1)**2)+.05
        reward-=.005*(self.last_command/.5)**2+.001*((self.last_command-previous)/.5)**2
        if terminated:reward-=10.
        return observation,float(reward),terminated,truncated,info
