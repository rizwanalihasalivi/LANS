"""Matched six-state adaptation of a delay-shifted CBF command guard.

Mechanism reference: Kalaria et al., arXiv:2208.13856v1, Plan B/Appendix.
This scalar-steering QP is a LANS-model adaptation, NOT their full lag-aware
steering/pedal sequence controller, tube-MPC implementation or safety theorem.
No original paper result or guarantee is inherited. See CBF_PROTOCOL.md.
"""
import math,time
import numpy as np
from integrations.unified_lans.physics import Command
from integrations.unified_lans.traffic import velocity
from tools.unified_control_v4.kernels import derivative
from .control import Synchronous


def world_acceleration(z,steering,accel,stiffness):
    dz=derivative(np.asarray(z,float),steering,accel,stiffness)
    h,v,vy,r=z[2],z[3],z[4],z[5];c,s=math.cos(h),math.sin(h)
    return np.array([dz[3]*c-v*s*r-dz[4]*s-vy*c*r,
                     dz[3]*s+v*c*r+dz[4]*c-vy*s*r])


def inequalities(z,route,accel,models,vehicles,cfg,omega):
    """Return A*delta+B>=0 for relative-degree-two lane/circle barriers."""
    q,heading,curvature=route.geometry(z[0]);slope=math.tan(heading)
    second=curvature/math.cos(heading)**3
    vel=velocity(z);error=z[1]-q;edot=vel[1]-slope*vel[0]
    constraints=[]
    for stiff in models:
        a0=world_acceleration(z,0.,accel,stiff);ad=world_acceleration(z,1.,accel,stiff)-a0
        h=1.75**2-error**2;hd=-2*error*edot
        e20=a0[1]-slope*a0[0]-second*vel[0]**2
        e2d=ad[1]-slope*ad[0]
        constraints.append((-2*error*e2d,-2*edot**2-2*error*e20+2*omega*hd+omega**2*h))
        for _,other,unc in vehicles:
            p=z[:2]-other[:2];relative=vel-velocity(other)
            radius=2*cfg.vehicle_radius+cfg.buffer+unc;dr=cfg.uncertainty_rate
            h=float(p@p-radius**2);hd=float(2*p@relative-2*radius*dr)
            constraints.append((float(2*p@ad),float(2*relative@relative+2*p@a0-2*dr**2+2*omega*hd+omega**2*h)))
    return constraints


def scalar_qp(desired,previous,lower,upper,constraints,smoothing=.001):
    """Exact minimizer of (u-desired)^2+smoothing*(u-previous)^2 on an interval."""
    for a,b in constraints:
        if abs(a)<1e-12:
            if b<0:return None
        elif a>0:lower=max(lower,-b/a)
        else:upper=min(upper,-b/a)
    if lower>upper:return None
    return min(upper,max(lower,(desired+smoothing*previous)/(1+smoothing)))


class Controller(Synchronous):
    def __init__(self,*args,omega=2.,**kwargs):
        if omega not in (1.,2.,4.):raise ValueError('use the three declared training-only CBF candidates')
        kwargs.update(mpc=False,deterministic_grid=())
        super().__init__(*args,**kwargs);self.omega=omega

    def decide(self,now,worker_failed=False):
        started=time.perf_counter();previous=self.issued
        result=super().decide(now,worker_failed)
        if result['ego_backup'] or result['missing'] or worker_failed or result['source']=='recovery_lqr':
            result['cbf_status']='KNOWLEDGE_FALLBACK';return result
        z=self.forecast(now);old=self.supervisor.state
        risk=self.supervisor.assess(z,self.inbox,self.expected,now,now+self.delay);self.supervisor.state=old
        cfg=self.cfg;base=self.baseline_fn(z,self.route)
        lower=max(-cfg.steering_limit,previous.steering-cfg.steering_rate*cfg.dt,base-cfg.residual_limit)
        upper=min(cfg.steering_limit,previous.steering+cfg.steering_rate*cfg.dt,base+cfg.residual_limit)
        center=self.stiffness_estimate if self.adaptive else 1.
        width=self.stiffness_uncertainty if self.adaptive else .3
        models=[max(.7,center-width),center,min(1.3,center+width)]
        constraints=inequalities(z,self.route,self.issued.accel,models,risk.vehicles,cfg,self.omega)
        u=scalar_qp(base,previous.steering,lower,upper,constraints)
        result.update(cbf_status='INFEASIBLE' if u is None else 'SOLVED',cbf_omega=self.omega,
            cbf_constraints=[list(c) for c in constraints],cbf_not_a_terminal_safety_certificate=True)
        if u is not None:
            self.issued=Command(float(u),self.issued.accel);self.pending[-1]=(now+self.delay,self.issued)
            result.update(source='cbf_lqr',residual=float(u-base),issued_steering=float(u),planned_candidate_selected=False)
        result['complete_decision_ms']=1000*(time.perf_counter()-started)
        return result
