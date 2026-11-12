"""Shared causal brake-or-clear guardian with original physical safety bounds.

The old supervisor's unconditional full braking can stop inside a crossing
vehicle's occupancy tube.  This wrapper retains that fallback and searches a
small, declared set of legal finite acceleration bursts only when the fallback
has no robust collision/corridor margin.  Every comparator uses this guardian.
"""
import math,time
import numpy as np
from numba import njit
from integrations.unified_lans.physics import Command,constrain
from tools.unified_control_v4.kernels import lqr,step,geometry
from tools.unified_control_v8.control import Controller as Base


@njit(cache=True)
def profile_rollout(state,first,previous,burst_accel,burst_s,target,dt,horizon,
                    cost_horizon,model,gains,route,feedback,npcs,radius,buffer,
                    uncertainty_rate,steering_limit,steering_rate,max_accel,max_brake):
    """Closed-loop bounded LQR plus finite burst, then original speed tracking."""
    z=state.copy();margin=1e9;cost=0.;heading=0.;rate_energy=0.;maximum_speed=z[3]
    for i in range(int(math.ceil(horizon/dt))):
        steer=first if i==0 else lqr(z,gains,int(route[0]),route[1],route[2],route[3],feedback)
        steer=min(steering_limit,max(-steering_limit,min(previous+steering_rate*dt,max(previous-steering_rate*dt,steer))))
        accel=burst_accel if i*dt<burst_s-1e-9 else min(max_accel,max(-max_brake,.8*(target-z[3])))
        z=step(z,steer,accel,dt,model);maximum_speed=max(maximum_speed,z[3])
        y,h,_=geometry(z[0],int(route[0]),route[1],route[2],route[3])
        ey=z[1]-y;ep=math.atan2(math.sin(z[2]-h),math.cos(z[2]-h));rate=(steer-previous)/dt
        if i*dt<cost_horizon-1e-9:
            cost+=dt*(8*ey*ey+2*ep*ep+.03*steer*steer+.02*rate*rate)
            heading+=dt*ep*ep;rate_energy+=dt*rate*rate
        margin=min(margin,1.75-abs(ey));t=(i+1)*dt
        for j in range(len(npcs)):
            n=npcs[j];vx=n[3]*math.cos(n[2])-n[4]*math.sin(n[2]);vy=n[3]*math.sin(n[2])+n[4]*math.cos(n[2])
            dx=n[0]+vx*t-z[0];dy=n[1]+vy*t-z[1]
            clearance=math.sqrt(dx*dx+dy*dy)-2*radius-buffer-n[6]-uncertainty_rate*t
            margin=min(margin,clearance)
        previous=steer
    return cost,margin,heading,rate_energy,maximum_speed


class Controller(Base):
    """Identical analytical repair for LQR, MPC, BC and every learned actor."""
    BURSTS=(0.,.25,.5,.75,1.)

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._clear_until=-math.inf
        self._clear_active=False

    def _safety_scores(self,z,previous,first,accel,burst_s,vehicles,horizon):
        center=self.stiffness_estimate if self.adaptive else 1.;width=self.stiffness_uncertainty
        models=(max(.7,center-width),center,min(1.3,center+width)) if self.adaptive else (.7,1.,1.3)
        npcs=np.asarray([[*other,unc] for _,other,unc in vehicles],float).reshape(-1,7)
        c=self.cfg
        return np.asarray([profile_rollout(z,first,previous.steering,accel,burst_s,self.target_speed,c.dt,horizon,
            c.horizon,m,self._gains,self._route,self.feedback_stiffness,npcs,c.vehicle_radius,c.buffer,
            c.uncertainty_rate,c.steering_limit,c.steering_rate,c.max_accel,c.max_brake) for m in models])

    def decide(self,now,worker_failed=False):
        start=time.perf_counter();result=self._guarded_decide(now,worker_failed)
        result['analytical_decision_ms']=result.get('complete_decision_ms',result.get('control_ms',0.))
        result['complete_decision_ms']=1000*(time.perf_counter()-start)
        result['safety_decision_ms']=result['complete_decision_ms']-result['analytical_decision_ms']
        return result

    def _guarded_decide(self,now,worker_failed=False):
        previous=self.issued;result=super().decide(now,worker_failed)
        result.update(safety_active=False,safety_strategy='unchanged',safety_margin=None,
            safety_burst_remaining_s=0.,safety_horizon_s=None,safety_predicted_max_speed=None)
        packet=self.inbox.latest.get('ego')
        if packet is None or now-packet.observed_s>self.cfg.ego_ttl+1e-9 or result.get('missing'):
            self._clear_active=False;self._clear_until=-math.inf
            result.update(safety_active=True,safety_strategy='stale_brake')
            return result
        z=self.forecast(now)
        if z is None:return result
        old=self.supervisor.state;risk=self.supervisor.assess(z,self.inbox,self.expected,now,now+self.delay);self.supervisor.state=old
        if risk.missing:return result
        # Covers a full legal stop with an additional half-second occupancy tail.
        required=max(self.cfg.horizon,z[3]/self.cfg.max_brake+.5)
        if required>5.:
            # This is a bounded-compute guardian, not a new physical speed cap.
            self._clear_active=False;self._clear_until=-math.inf
            command=constrain(Command(self.baseline_fn(z,self.route),-self.cfg.max_brake),previous,self.cfg)
            self.pending[-1]=(now+self.delay,command);self.issued=command
            result.update(original_costs=result['costs'],original_eligible=result['eligible'],
                costs={},eligible={'safety_brake':False},source='safety_brake',reason='guardian_horizon_exceeded',
                issued_steering=command.steering,issued_accel=command.accel,
                safety_active=True,safety_strategy='unverified_speed_brake')
            return result
        horizon=required
        first=constrain(Command(self.baseline_fn(z,self.route),0.),previous,self.cfg).steering
        brake=self._safety_scores(z,previous,first,-self.cfg.max_brake,horizon,risk.vehicles,horizon)
        brake_margin=float(brake[:,1].min())
        trigger=risk.state=='DANGER' or result.get('reason')=='no_feasible_prediction'
        if not self._clear_active and (not trigger or brake_margin>=0.):return result
        if self._clear_active and risk.state=='SAFE' and brake_margin>=0.:
            self._clear_active=False;self._clear_until=-math.inf
            return result
        remaining=max(0.,self._clear_until-now) if self._clear_active else 0.
        profiles=[remaining] if self._clear_active else list(self.BURSTS)
        chosen=None;chosen_s=None
        for duration in profiles:
            scores=self._safety_scores(z,previous,first,self.cfg.max_accel,duration,risk.vehicles,horizon)
            if float(scores[:,1].min())>=0.:
                chosen=scores;chosen_s=duration;break
        if chosen is None and self._clear_active:
            # New received evidence may invalidate the stored clearance profile.
            # Re-certify a fresh bounded burst rather than blindly retain it.
            for duration in self.BURSTS:
                scores=self._safety_scores(z,previous,first,self.cfg.max_accel,duration,risk.vehicles,horizon)
                if float(scores[:,1].min())>=0.:
                    chosen=scores;chosen_s=duration;self._clear_until=now+duration;break
        if chosen is None:
            self._clear_active=False;self._clear_until=-math.inf
            command=constrain(Command(first,-self.cfg.max_brake),previous,self.cfg)
            self.pending[-1]=(now+self.delay,command);self.issued=command
            result.update(original_costs=result['costs'],original_eligible=result['eligible'],
                source='safety_brake',reason='no_verified_clearance',residual=0.,
                costs={'safety_brake':float(brake[:,0].mean())},eligible={'safety_brake':False},
                issued_steering=command.steering,issued_accel=command.accel,
                safety_active=True,safety_strategy='no_verified_clearance',safety_margin=brake_margin,
                safety_horizon_s=horizon,safety_predicted_max_speed=float(brake[:,4].max()))
            return result
        if not self._clear_active:self._clear_until=now+chosen_s
        self._clear_active=True
        accel=self.cfg.max_accel if chosen_s>1e-9 else float(np.clip(.8*(self.target_speed-z[3]),-self.cfg.max_brake,self.cfg.max_accel))
        command=constrain(Command(first,accel),previous,self.cfg)
        assert self.pending and abs(self.pending[-1][0]-(now+self.delay))<1e-8
        self.pending[-1]=(now+self.delay,command);self.issued=command
        result.update(original_costs=result['costs'],original_eligible=result['eligible'],
            source='safety_clear',residual=0.,reason='robust_brake_infeasible_clearance_verified',
            costs={'safety_clear':float(chosen[:,0].mean())},eligible={'safety_clear':True},
            issued_steering=command.steering,issued_accel=command.accel,
            planned_candidate_selected=False,safety_active=True,safety_strategy='clear_conflict',
            safety_margin=float(chosen[:,1].min()),safety_burst_remaining_s=chosen_s,
            safety_horizon_s=horizon,safety_predicted_max_speed=float(chosen[:,4].max()),
            safety_brake_margin=brake_margin)
        return result
