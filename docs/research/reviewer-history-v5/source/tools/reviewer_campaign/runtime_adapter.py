"""Same supervisor behind the historical real-worker/native gate call signature."""
import common
import math
from supervisor import Controller


class PredictiveGateAdapter:
    def __init__(self, config):
        self.ctrl = Controller('predictive')

    @property
    def weight(self):return self.ctrl.weight

    @property
    def good(self):return self.ctrl.good

    def reset(self, baseline, reason, j0=math.nan, j1=math.nan):
        self.ctrl.weight=0.
        self.ctrl.good=0
        self.ctrl.last_command=baseline
        return baseline,0.,reason,j0,j1

    def choose(self,t,baseline,packet,estimate,actuator,speed,curvature,gain,role):
        if role != 'residual':raise ValueError('residual role required')
        self.ctrl.packet=packet
        command,reason=self.ctrl.choose(t,baseline,estimate,actuator,speed,curvature,gain)
        j0,j1=self.ctrl.last_costs
        return command,self.ctrl.weight,('earned' if reason=='accepted' else reason),j0,j1
