"""Numerically equivalent fused projection/scoring: simulate each trial once."""
import math
import numpy as np
from numba import njit
from tools.unified_control_v4.kernels import lqr,step,geometry
from tools.unified_control_v5.control import baseline_plan
from .control import Controller as Original,Planner as OriginalPlanner


@njit(cache=True)
def evaluate(z,plan,accel,previous,dt,stiff,gains,route,npcs,radius,buffer,uncertainty,angle,rate,limit,feedback):
    result=plan.copy();state=z.copy();cost=0.;margin=1e9
    for i in range(len(plan)):
        base=lqr(state,gains,int(route[0]),route[1],route[2],route[3],feedback)
        steer=min(base+limit,max(base-limit,plan[i]))
        steer=min(previous+rate*dt,max(previous-rate*dt,steer));steer=min(angle,max(-angle,steer))
        result[i]=steer;state=step(state,steer,accel,dt,stiff)
        y,h,_=geometry(state[0],int(route[0]),route[1],route[2],route[3])
        ey=state[1]-y;ep=math.atan2(math.sin(state[2]-h),math.cos(state[2]-h));slew=(steer-previous)/dt
        cost+=dt*(8*ey*ey+2*ep*ep+.03*steer*steer+.02*slew*slew)
        margin=min(margin,1.75-abs(ey));t=(i+1)*dt
        for j in range(len(npcs)):
            n=npcs[j];vx=n[3]*math.cos(n[2])-n[4]*math.sin(n[2]);vy=n[3]*math.sin(n[2])+n[4]*math.cos(n[2])
            dx=n[0]+vx*t-state[0];dy=n[1]+vy*t-state[1]
            margin=min(margin,math.sqrt(dx*dx+dy*dy)-2*radius-buffer-n[6]-uncertainty*t)
        previous=steer
    return result,cost,margin


@njit(cache=True)
def refine(z,initial,warm,accel,previous,dt,horizon,stiff,gains,route,npcs,radius,buffer,uncertainty,angle,rate,limit,feedback):
    args=(accel,previous,dt,stiff,gains,route,npcs,radius,buffer,uncertainty,angle,rate,limit,feedback)
    best,score,_=evaluate(z,initial,*args)
    baseline=baseline_plan(z,len(best),accel,previous,dt,stiff,gains,route,angle,rate,feedback)
    for seed in (baseline,warm):
        candidate,value,margin=evaluate(z,seed,*args)
        if margin>=0. and value<score:best=candidate;score=value
    for amplitude in (.01,.0025,.000625):
        for index in range(len(best)):
            chosen=best.copy();value=score
            for sign in (-1.,1.):
                trial=best.copy();trial[index]+=sign*amplitude
                trial,cost,margin=evaluate(z,trial,*args)
                if margin>=0. and cost<value-1e-10:chosen=trial;value=cost
            best=chosen;score=value
    return best


class Planner(OriginalPlanner):
    def plan(self,state,route,previous,cfg,stiffness,penalty):
        initial=self.linear.plan(state,route,previous,cfg,stiffness,penalty)
        self.used_backup=initial is None
        c=self.owner;now=c._decision_now;old=c.supervisor.state
        risk=c.supervisor.assess(state,c.inbox,c.expected,now,now+c.delay);c.supervisor.state=old
        accel=c.supervisor.acceleration(float(np.clip(.8*(c.target_speed-state[3]),-cfg.max_brake,cfg.max_accel)),risk)
        npcs=np.array([[*other,unc] for _,other,unc in risk.vehicles],float).reshape(-1,7)
        center=c.stiffness_estimate if c.adaptive else 1.
        if initial is None:
            initial=baseline_plan(state,round(cfg.horizon/cfg.dt),accel,previous,cfg.dt,center,c._gains,c._route,cfg.steering_limit,cfg.steering_rate,c.feedback_stiffness)
        warm=initial if self.warm is None else self.warm
        plan=refine(state,initial,warm,accel,previous,cfg.dt,cfg.horizon,center,c._gains,c._route,npcs,
                    cfg.vehicle_radius,cfg.buffer,cfg.uncertainty_rate,cfg.steering_limit,cfg.steering_rate,cfg.residual_limit,c.feedback_stiffness)
        self.warm=np.r_[plan[1:],plan[-1]]
        return plan


class Controller(Original):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.planner is not None:self.planner=Planner(self,self.planner.linear)
