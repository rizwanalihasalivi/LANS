"""Matched training arms: only direct versus gated action execution changes."""
import numpy as np
from bootstrap import RESEARCH
from execution_env import ExecutionEnv
from execution import Execution


class DirectExecution(Execution):
    def step(self,t,proposed,service_ticks,baseline,estimate,actuator,speed,curvature,gain):
        if service_ticks != 0:raise ValueError('direct training control is synchronous')
        if not np.isfinite(proposed):raise ValueError('finite residual required')
        self.sequence+=1
        self.packet=(self.sequence,t,float(np.clip(proposed,-.08,.08)))
        self.gate.weight=1.;self.gate.good=3
        command=float(np.clip(baseline+self.packet[2],-.5,.5));self.last_command=command
        return command,dict(submitted=True,gate_weight=1.,gate_reason='direct_training',
            predicted_lqr_cost=np.nan,predicted_fused_cost=np.nan,packet_sequence=self.sequence,
            observation_timestamp_s=t,action_age_s=0.,executed_packet_residual=self.packet[2])


class PilotEnv(ExecutionEnv):
    def __init__(self,arm,seed):
        if arm not in ('direct','execution'):raise ValueError(arm)
        super().__init__(seed=seed,randomize=False,service_ticks=0)
        self.arm=arm

    def reset(self,**kwargs):
        _,info=super().reset(**kwargs)
        if self.arm=='direct':self.execution=DirectExecution()
        return self.observation(),info
