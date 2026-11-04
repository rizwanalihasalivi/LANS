"""Unchanged traffic/noise definitions with genuinely new seeds and longer runs."""
from integrations.connected_v2v.robustness.scenarios import PROFILES,SPEEDS,radar_scan
from integrations.connected_v2v.robustness.scenarios import Scene as PriorScene
from .geometry import CircularRoad
from .pacing import pace_goal
import numpy as np

NATIVE_CASES=tuple(PROFILES)
DEV_SEEDS=(6101,6113,6121,7069)
VALIDATION_SEEDS=(9001,9011,9013,9029,9041,9043,9049,9059,9067,9091)


class Scene(PriorScene):
    def __init__(self,*args):
        super().__init__(*args)
        self.road=CircularRoad(self.profile.radius)
        self.leader_history={0:super().states(0.)['leader']}

    def states(self,t):
        result=super().states(t)
        tick=round(t/.05)
        if tick not in self.leader_history:raise ValueError('leader dynamics must advance causally')
        result['leader']=self.leader_history[tick].copy()
        return result

    def advance_leader(self,node,now):
        tick=round(now/.05);own=self.leader_history[tick]
        goal,info=pace_goal(node,own,now,self.road,self.speed)
        s,_,v,_=self.road.canonical(own)
        acceleration=max(-2.5,min(2.5,.8*(goal-v)))
        nxt=max(self.speed-4.,min(self.speed,v+acceleration*.05))
        station=s+.025*(v+nxt);heading=station/self.road.radius if self.road.radius else 0.
        self.leader_history[tick+1]=np.array([*self.road.position(station),heading,nxt,0.,nxt/self.road.radius if self.road.radius else 0.])
        return dict(command_accel=acceleration,goal_speed=goal,**info)
