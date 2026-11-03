"""Ego bicycle, independent NPC truth and delayed/lost V2V delivery harness."""
import math
import numpy as np
from .physics import Route, errors
from .traffic import Packet


def initial(scenario, lateral=.2):
    route=Route('sine' if scenario=='curved' else ('lane_change' if scenario=='merge' else 'straight'))
    y,h,_=route.geometry(0.)
    ego=np.array([0.,y+lateral,h,12.,0.,0.])
    if scenario=='following':npcs={'lead':np.array([32.,0.,0.,7.,0.,0.])}
    elif scenario=='crossing':npcs={'cross':np.array([30.,-20.,math.pi/2,8.,0.,0.])}
    elif scenario=='merge':npcs={'merge':np.array([35.,3.5,0.,8.,0.,0.])}
    elif scenario=='curved':npcs={'lead':np.array([42.,route.geometry(42.)[0],0.,10.,0.,0.])}
    else:raise ValueError('unknown scenario')
    return route,ego,npcs


def move_npcs(npcs, dt, route, scenario):
    for z in npcs.values():
        z[0]+=z[3]*math.cos(z[2])*dt;z[1]+=z[3]*math.sin(z[2])*dt
        if scenario=='curved':z[1],z[2],_=route.geometry(z[0])


class Network:
    def __init__(self, seed=1, profile='nominal'):
        if profile not in ('nominal','delayed','loss','reordered','blackout','ego_blackout'):
            raise ValueError('unknown network profile')
        self.rng=np.random.default_rng(seed);self.profile=profile;self.pending=[];self.sequence=0
        self.sent=0;self.dropped=0

    def emit(self, now, ego, npcs, inbox):
        self.sequence+=1
        # Ego and each neighbor retain separate original measurement timestamps.
        for name,z in [('ego',ego),*npcs.items()]:
            self.sent+=1
            drop=(self.profile=='ego_blackout' and name=='ego' and now>=1.)
            if name!='ego':
                drop|=(self.profile=='blackout' and now>=1.)
                drop|=(self.profile=='loss' and self.rng.random()<.3)
            if drop:self.dropped+=1;continue
            delay=0.
            if name!='ego':
                if self.profile=='delayed':delay=float(self.rng.choice([.05,.1,.25,.5]))
                elif self.profile=='reordered':delay=.2 if self.sequence%2 else 0.
            self.pending.append((now+delay,Packet(name,self.sequence,now,tuple(z))))
        arrived=[p for due,p in self.pending if due<=now+1e-9]
        self.pending=[(due,p) for due,p in self.pending if due>now+1e-9]
        for p in arrived:inbox.ingest(p,now)


def truth_metrics(ego, npcs, route, cfg):
    e,_=errors(ego,route)
    clearance=min((float(np.linalg.norm(z[:2]-ego[:2])-2*cfg.vehicle_radius) for z in npcs.values()),default=math.inf)
    return dict(error=float(e[0]),heading_error=float(e[2]),true_clearance=clearance,
                collision=clearance<=0,corridor_exceeded=abs(e[0])>1.75,
                speed=float(ego[3]),x=float(ego[0]),y=float(ego[1]))
