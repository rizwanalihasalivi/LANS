import numpy as np
from numba import njit
from tools.unified_control_v4.control import Controller as Previous
from tools.unified_control_v4.kernels import step,lqr,rollout


@njit(cache=True)
def project(z,plan,accel,previous,dt,stiff,gains,route,angle,rate,residual_limit,feedback_stiffness=1.):
    result=plan.copy();state=z.copy()
    for i in range(len(plan)):
        base=lqr(state,gains,int(route[0]),route[1],route[2],route[3],feedback_stiffness)
        steer=min(base+residual_limit,max(base-residual_limit,plan[i]))
        steer=min(previous+rate*dt,max(previous-rate*dt,steer));steer=min(angle,max(-angle,steer))
        result[i]=steer;state=step(state,steer,accel,dt,stiff);previous=steer
    return result


@njit(cache=True)
def baseline_plan(z,n,accel,previous,dt,stiff,gains,route,angle,rate,feedback_stiffness):
    state=z.copy();result=np.zeros(n)
    for i in range(n):
        u=lqr(state,gains,int(route[0]),route[1],route[2],route[3],feedback_stiffness)
        u=min(previous+rate*dt,max(previous-rate*dt,u));u=min(angle,max(-angle,u))
        result[i]=u;state=step(state,u,accel,dt,stiff);previous=u
    return result


@njit(cache=True)
def refine(z,initial,accel,previous,dt,horizon,stiff,gains,route,npcs,radius,buffer,uncertainty,angle,rate,limit,feedback_stiffness):
    # Two declared sweeps, four temporal blocks and both perturbation signs.
    # Every proposal uses the actual bounded acceleration, exact nonlinear
    # integration and the same constrained command projection as application.
    best=project(z,initial,accel,previous,dt,stiff,gains,route,angle,rate,limit,feedback_stiffness)
    best_value=rollout(z,best[0],accel,previous,dt,horizon,stiff,gains,route,npcs,radius,buffer,uncertainty,angle,rate,feedback_stiffness,best)[0]
    baseline=baseline_plan(z,len(best),accel,previous,dt,stiff,gains,route,angle,rate,feedback_stiffness)
    base_value=rollout(z,baseline[0],accel,previous,dt,horizon,stiff,gains,route,npcs,radius,buffer,uncertainty,angle,rate,feedback_stiffness,baseline)[0]
    if base_value<best_value:best=baseline;best_value=base_value
    n=len(best)
    for amplitude in (.01,.0025):
        for block in range(4):
            chosen=best.copy();value=best_value
            for sign in (-1.,1.):
                trial=best.copy()
                for i in range(block*n//4,(block+1)*n//4):trial[i]+=sign*amplitude
                trial=project(z,trial,accel,previous,dt,stiff,gains,route,angle,rate,limit,feedback_stiffness)
                candidate=rollout(z,trial[0],accel,previous,dt,horizon,stiff,gains,route,npcs,radius,buffer,uncertainty,angle,rate,feedback_stiffness,trial)
                if candidate[1]>=0. and candidate[0]<value-1e-10:chosen=trial;value=candidate[0]
            best=chosen;best_value=value
    return best


class Planner:
    def __init__(self,owner,linear):self.owner=owner;self.linear=linear;self.used_backup=False
    @property
    def status(self):return 'NONLINEAR_BACKUP_FROM_'+self.linear.status if self.used_backup else self.linear.status
    @property
    def failures(self):return self.linear.failures
    def plan(self,state,route,previous,cfg,stiffness,penalty):
        plan=self.linear.plan(state,route,previous,cfg,stiffness,penalty)
        self.used_backup=plan is None
        c=self.owner;now=c._decision_now;old=c.supervisor.state
        risk=c.supervisor.assess(state,c.inbox,c.expected,now,now+c.delay);c.supervisor.state=old
        acceleration=c.supervisor.acceleration(float(np.clip(.8*(c.target_speed-state[3]),-cfg.max_brake,cfg.max_accel)),risk)
        npcs=np.array([[*other,unc] for _,other,unc in risk.vehicles],float).reshape(-1,7)
        center=c.stiffness_estimate if c.adaptive else 1.
        if plan is None:plan=baseline_plan(state,round(cfg.horizon/cfg.dt),acceleration,previous,cfg.dt,center,c._gains,c._route,cfg.steering_limit,cfg.steering_rate,c.feedback_stiffness)
        return refine(state,plan,acceleration,previous,cfg.dt,cfg.horizon,center,c._gains,c._route,npcs,
                      cfg.vehicle_radius,cfg.buffer,cfg.uncertainty_rate,cfg.steering_limit,cfg.steering_rate,cfg.residual_limit,c.feedback_stiffness)


class Controller(Previous):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self._decision_now=0.
        if self.planner is not None:self.planner=Planner(self,self.planner)
    def decide(self,now,worker_failed=False):
        self._decision_now=now
        return super().decide(now,worker_failed)
