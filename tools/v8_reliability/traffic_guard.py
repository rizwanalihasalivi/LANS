"""V2 development: consistent future uncertainty and finite occupancy tails.

V1 confirmation is preserved. These changes are analytical supervision, never
PPO training or a universal safety guarantee. All current baselines must share
them before a V2 comparison is interpreted.
"""
import math
import numpy as np
from integrations.unified_lans.traffic import Risk,extrapolate,velocity,Supervisor
from .control import Controller as V1,Synchronous as SyncV1
from .cbf_reference import Controller as CBFV1


def expanding_contact(ego,other,radius,growth):
    p=np.asarray(other[:2])-ego[:2];v=velocity(other)-velocity(ego)
    c=float(p@p-radius*radius)
    if c<=0:return 0.
    a=float(v@v-growth*growth);b=float(2*(p@v-radius*growth))
    if abs(a)<1e-12:return -c/b if b<0 else math.inf
    d=b*b-4*a*c
    if d<0:return math.inf
    roots=[t for t in ((-b-math.sqrt(d))/(2*a),(-b+math.sqrt(d))/(2*a)) if t>=0.]
    return min(roots,default=math.inf)


def occupancy_contact(ego,other,radius,growth):
    ve,vn=velocity(ego),velocity(other);matrix=np.column_stack((ve,-vn))
    if abs(np.linalg.det(matrix))<1e-6:return math.inf
    te,tn=np.linalg.solve(matrix,np.asarray(other[:2])-ego[:2]);lower=0.;upper=math.inf
    for center,speed in [(te,float(np.linalg.norm(ve))),(tn,float(np.linalg.norm(vn)))]:
        lower=max(lower,(speed*center-radius)/(speed+growth))
        coefficient=speed-growth;bound=speed*center+radius
        if coefficient>0:upper=min(upper,bound/coefficient)
        elif coefficient<0:lower=max(lower,bound/coefficient)
        elif bound<0:return math.inf
    return float(lower) if lower<=upper else math.inf


class FutureSupervisor(Supervisor):
    def __init__(self,cfg,scenario):super().__init__(cfg,scenario);self.force_stop=False
    def assess(self,ego,inbox,expected,now,application_s):
        vehicles=[];missing=[];ages=[];critical='';minimum=math.inf;clearance=math.inf
        for name in sorted(expected):
            packet=inbox.latest.get(name)
            if packet is None or now-packet.observed_s>self.cfg.traffic_ttl+1e-9:missing.append(name);continue
            age=max(0.,application_s-packet.observed_s);ages.append(age);other=extrapolate(packet.state,age)
            unc=self.cfg.uncertainty_rate*age;radius=2*self.cfg.vehicle_radius+self.cfg.buffer+unc
            distance=float(np.linalg.norm(other[:2]-ego[:2])-radius)
            contact=min(expanding_contact(ego,other,radius,self.cfg.uncertainty_rate),occupancy_contact(ego,other,radius,self.cfg.uncertainty_rate))
            if (contact,distance)<(minimum,clearance):minimum=contact;critical=name
            clearance=min(clearance,distance);vehicles.append((name,other,unc))
        danger,warning=self.THRESHOLDS[self.scenario]
        if self.force_stop or missing or clearance<=0 or minimum<=danger+(.4 if self.state=='DANGER' else 0.):self.state='DANGER'
        elif minimum<=warning+(.4 if self.state!='SAFE' else 0.):self.state='WARNING'
        else:self.state='SAFE'
        return Risk(self.state,minimum,clearance,critical,max(ages,default=0.),tuple(missing),tuple(vehicles))


class Guard:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.supervisor=FutureSupervisor(self.cfg,self.supervisor.scenario)


class Controller(Guard,V1):pass
class Synchronous(Guard,SyncV1):pass
class CBF(Guard,CBFV1):pass
