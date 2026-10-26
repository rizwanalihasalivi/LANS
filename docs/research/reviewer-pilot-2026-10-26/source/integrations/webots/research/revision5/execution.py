"""Shared simulation-time action availability and frozen gate execution interface.

One outstanding inference request; actions sampled while busy are not submitted.
All held/pending control state is exposed for delayed-action credit assignment.
"""
import math
import numpy as np
from bootstrap import RESEARCH
from gating import Gate
from core import GAINS


def scheduled_gain(speed):
    # Continuous interpolation of the existing, unchanged speed schedule.
    return np.array([np.interp(speed,[15,20,25],[GAINS[v][i] for v in (15,20,25)]) for i in range(4)])


def matched_lqr(estimate,speed,curvature):
    gain=scheduled_gain(speed)
    vy=(1.4*speed-1650*1.2*speed**3/(2.6*80000))*curvature
    target=np.array([0.,vy,-vy/speed,speed*curvature])
    ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*speed**2)*curvature
    return float(np.clip(ff-gain@(estimate-target),-.5,.5)),gain


class Execution:
    def __init__(self):
        self.gate=Gate({'horizon_steps':20,'relative_margin':.01})
        self.packet=None;self.pending=None;self.sequence=0;self.last_command=0.

    def context(self,t):
        packet=self.packet;pending=self.pending
        return np.array([self.gate.weight,min(self.gate.good,3)/3,
            packet[2]/.08 if packet else 0.,(t-packet[1])/.1 if packet else 0.,float(packet is not None),
            pending[1][2]/.08 if pending else 0.,max(0,pending[0]-t)/.1 if pending else 0.,
            (t-pending[1][1])/.1 if pending else 0.,float(pending is not None),self.last_command/.5],dtype=np.float32)

    def step(self,t,proposed,service_ticks,baseline,estimate,actuator,speed,curvature,gain,submit_request=True):
        if not np.isfinite(proposed):raise ValueError('finite residual required')
        if service_ticks not in (0,1,2,10):raise ValueError('unsupported service-delay ticks')
        if self.pending and self.pending[0]<=t+1e-9:
            self.packet=self.pending[1];self.pending=None
        submitted=self.pending is None and submit_request
        if submitted:
            self.sequence+=1;packet=(self.sequence,t,float(np.clip(proposed,-.08,.08)))
            if service_ticks==0:self.packet=packet
            else:self.pending=(t+service_ticks*.01,packet)
        command,weight,reason,j0,j1=self.gate.choose(t,baseline,self.packet,estimate,actuator,speed,curvature,gain,'residual')
        self.last_command=command
        return command,dict(submitted=submitted,gate_weight=weight,gate_reason=reason,
            predicted_lqr_cost=j0,predicted_fused_cost=j1,
            packet_sequence=self.packet[0] if self.packet else -1,
            observation_timestamp_s=self.packet[1] if self.packet else math.nan,
            action_age_s=t-self.packet[1] if self.packet else math.nan,
            executed_packet_residual=self.packet[2] if self.packet else 0.)
