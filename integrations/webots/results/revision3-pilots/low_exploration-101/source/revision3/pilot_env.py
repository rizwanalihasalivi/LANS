"""Predeclared reward candidates; action units/dynamics remain shared and fixed."""
import math
from matched_env import MatchedResidualEnv
from core import path_values

class PilotEnv(MatchedResidualEnv):
    def __init__(self,seed,config):super().__init__(seed);self.config=config
    def step(self,action):
        previous=self.last_command
        observation,reward,terminated,truncated,info=super().step(action)
        if self.config['ey_scale']!=.5 or self.config['heading_scale']!=.1:
            _,heading,_=path_values(self.state[0],self.path)
            reward=math.exp(-(info['error']/self.config['ey_scale'])**2-.2*((self.state[2]-heading)/self.config['heading_scale'])**2)+.05
            reward-=.005*(self.last_command/.5)**2+.001*((self.last_command-previous)/.5)**2
            if terminated:reward-=10.
        return observation,float(reward),terminated,truncated,info
