"""Causal identifiability readiness and tracking-ranked robust admission."""
import math
import numpy as np
from numba import njit
from integrations.unified_lans.physics import Command,constrain
from tools.unified_control_v4.kernels import step,lqr,geometry
from tools.unified_control_v7.control import Controller as Previous


@njit(cache=True)
def tracking_rollout(z,first,accel,previous,dt,horizon,stiff,gains,route,npcs,radius,buffer,uncertainty_rate,steering_limit,steering_rate,feedback_stiffness=1.,plan=None):
    z=z.copy();cost=0.;margin=1e9;heading_energy=0.;rate_energy=0.
    for i in range(int(math.ceil(horizon/dt))):
        base=lqr(z,gains,int(route[0]),route[1],route[2],route[3],feedback_stiffness)
        steer=first if i==0 else base
        if i>0 and plan is not None and i<len(plan):steer=min(base+.08,max(base-.08,plan[i]))
        if i>0:steer=min(previous+steering_rate*dt,max(previous-steering_rate*dt,steer))
        steer=min(steering_limit,max(-steering_limit,steer));z=step(z,steer,accel,dt,stiff)
        y,h,_=geometry(z[0],int(route[0]),route[1],route[2],route[3])
        ey=z[1]-y;ep=math.atan2(math.sin(z[2]-h),math.cos(z[2]-h));rate=(steer-previous)/dt
        heading_energy+=dt*ep*ep;rate_energy+=dt*rate*rate
        cost+=dt*ey*ey
        margin=min(margin,1.75-abs(ey));t=(i+1)*dt
        for j in range(len(npcs)):
            n=npcs[j];vx=n[3]*math.cos(n[2])-n[4]*math.sin(n[2]);vy=n[3]*math.sin(n[2])+n[4]*math.cos(n[2])
            dx=n[0]+vx*t-z[0];dy=n[1]+vy*t-z[1]
            clearance=math.sqrt(dx*dx+dy*dy)-2*radius-buffer-n[6]-uncertainty_rate*t
            margin=min(margin,clearance)
        previous=steer
    return cost,margin,heading_energy,rate_energy


class Controller(Previous):
    def __init__(self,*args,early_id=True,tracking_only=False,**kwargs):
        self.early_id=bool(early_id);self.tracking_only=bool(tracking_only)
        super().__init__(*args,**kwargs)

    def update_model(self):
        old=self._previous_measurement;steps=self._id_steps
        super().update_model()
        if not self.early_id or not self.adaptive or old is None or self._id_steps==steps:return
        current=self._previous_measurement;dt=current.observed_s-old.observed_s
        commands=[c for start,end,c in self.history if abs(start-old.observed_s)<1e-8 and abs(end-current.observed_s)<1e-8]
        if abs(dt-self.cfg.dt)>1e-8 or len(commands)!=1:
            self.stiffness_uncertainty=.3;return
        z=np.array(old.state);observed=np.array(current.state);u=commands[0]
        predicted=step(z,u.steering,u.accel,dt,self.stiffness_estimate)
        # This simulation observes lateral velocity/yaw rate without sensor noise.
        # A tighter interval is allowed only when the measured transition itself
        # supports that same model; mismatch keeps the original broad interval.
        if np.sum((predicted[4:]-observed[4:])**2)>1e-8:
            self.stiffness_uncertainty=.3;return
        losses=self._id_scores/self._id_weight
        compatible=self._id_grid[losses<=losses.min()+1e-8]
        self.stiffness_uncertainty=max(.025,float(np.max(abs(compatible-self.stiffness_estimate))))

    def cost(self,z,first,residual,accel,vehicles,lifetime):
        if not self.tracking_only:return super().cost(z,first,residual,accel,vehicles,lifetime)
        cfg=self.cfg;center=self.stiffness_estimate if self.adaptive else 1.;width=self.stiffness_uncertainty
        models=np.array([max(.7,center-width),center,min(1.3,center+width)]) if self.adaptive else np.array([.7,1.,1.3])
        npcs=np.array([[*other,uncertainty] for _,other,uncertainty in vehicles],float).reshape(-1,7)
        args=(self.issued.steering,cfg.dt,cfg.horizon,self._gains,self._route,npcs,cfg.vehicle_radius,cfg.buffer,cfg.uncertainty_rate,cfg.steering_limit,cfg.steering_rate)
        def values(steering,plan=None):
            return np.array([tracking_rollout(z,steering,accel,args[0],args[1],args[2],s,*args[3:],self.feedback_stiffness,plan) for s in models])
        base=constrain(Command(self.baseline_fn(z,self.route),accel),self.issued,cfg)
        key=(tuple(z),accel,self.issued.steering,center,width,tuple(npcs.ravel()))
        if self._cost_reference is None or self._cost_reference[0]!=key:self._cost_reference=(key,values(base.steering))
        reference=self._cost_reference[1]
        planned=self._plan is not None and self._plan_residual is not None and abs(residual-self._plan_residual)<1e-12
        result=values(first.steering,self._plan) if planned else (reference if first.steering==base.steering else values(first.steering))
        margin=float(result[:,1].min())
        if first.steering!=base.steering or planned:
            # The ranking/dominance objective changes to lateral SSE; physical,
            # corridor, collision and per-model heading/rate guard stay intact.
            if (np.any(result[:,0]>=reference[:,0]-1e-9)
                or np.any(result[:,2]>1.21*reference[:,2]+2e-6)
                or np.any(result[:,3]>1.21*reference[:,3]+1e-5)):
                margin=min(margin,-1e-9)
        return float(result[:,0].mean()),margin
