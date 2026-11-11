"""Continuous bounded acceleration projection from received relative geometry.

The same analytical supervisor is used by every current comparator. Missing
knowledge still brakes. This sampled/model-point guard is not a safety theorem.
"""
import math
import numpy as np
from integrations.unified_lans.physics import Command,constrain
from integrations.unified_lans.traffic import velocity
from tools.v8_reliability.cbf_reference import world_acceleration
from tools.v8_reliability.traffic_guard import FutureSupervisor,Controller as Prior,Synchronous as PriorSync


def interval(nominal,lower,upper,constraints):
    for a,b in constraints:
        if abs(a)<1e-12:
            if b<0:return None,lower,upper
        elif a>0:lower=max(lower,-b/a)
        else:upper=min(upper,-b/a)
    if lower>upper:return None,lower,upper
    return min(upper,max(lower,nominal)),lower,upper


def acceleration_constraints(ego,steering,route,vehicles,models,cfg,omega):
    vel=velocity(ego);direction=np.array([math.cos(ego[2]),math.sin(ego[2])]);constraints=[]
    y,heading,curvature=route.geometry(ego[0]);slope=math.tan(heading);second=curvature/math.cos(heading)**3
    error=ego[1]-y;edot=vel[1]-slope*vel[0]
    for stiff in models:
        free=world_acceleration(ego,steering,0.,stiff)
        e2=free[1]-slope*free[0]-second*vel[0]**2;ad=direction[1]-slope*direction[0]
        constraints.append((-2*error*ad,-2*edot**2-2*error*e2-4*omega*error*edot+omega**2*(1.75**2-error**2)))
        for _,other,unc in vehicles:
            p=ego[:2]-other[:2];rv=vel-velocity(other);radius=2*cfg.vehicle_radius+cfg.buffer+unc;g=cfg.uncertainty_rate
            hh=float(p@p-radius*radius);hd=float(2*p@rv-2*radius*g)
            constraints.append((float(2*p@direction),float(2*rv@rv+2*p@free-2*g*g+2*omega*hd+omega*omega*hh)))
    return constraints


class Supervisor(FutureSupervisor):
    def __init__(self,owner,omega):super().__init__(owner.cfg,owner.supervisor.scenario);self.owner=owner;self.omega=omega;self.context=None;self.projection=None
    def assess(self,ego,*args,**kw):
        risk=super().assess(ego,*args,**kw);self.context=(np.asarray(ego,float).copy(),risk.vehicles);return risk
    def acceleration(self,nominal,risk):
        if self.force_stop or risk.missing or self.context is None:
            self.projection=dict(status='KNOWLEDGE_BRAKE');return -self.cfg.max_brake
        c=self.owner;z,vehicles=self.context
        steer=constrain(Command(c.baseline_fn(z,c.route),nominal),c.issued,c.cfg).steering
        center=c.stiffness_estimate if c.adaptive else 1.;width=c.stiffness_uncertainty if c.adaptive else .3
        models=[max(.7,center-width),center,min(1.3,center+width)]
        constraints=acceleration_constraints(z,steer,c.route,vehicles,models,c.cfg,self.omega)
        chosen,lo,hi=interval(nominal,-c.cfg.max_brake,c.cfg.max_accel,constraints)
        self.projection=dict(status='PROJECTED' if chosen is not None else 'INFEASIBLE_FALLBACK',lower=lo,upper=hi,nominal=nominal,chosen=chosen)
        return float(chosen) if chosen is not None else super().acceleration(nominal,risk)


class Guard:
    def __init__(self,*args,barrier_frequency=2.,**kw):
        if barrier_frequency not in (1.5,2.,3.):raise ValueError('declared development frequencies only')
        super().__init__(*args,**kw);self.supervisor=Supervisor(self,barrier_frequency)
    def decide(self,*a,**kw):
        r=super().decide(*a,**kw);r['longitudinal_projection']=self.supervisor.projection;return r


class Controller(Guard,Prior):pass
class Synchronous(Guard,PriorSync):pass
