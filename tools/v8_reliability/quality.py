"""Optional tighter secondary budgets around the original v8 mixed objective."""
import numpy as np
from integrations.unified_lans.physics import Command,constrain
from tools.unified_control_v4.kernels import rollout


def cost(c,z,first,residual,accel,vehicles,lifetime):
    cfg=c.cfg;center=c.stiffness_estimate if c.adaptive else 1.;width=c.stiffness_uncertainty
    models=np.array([max(.7,center-width),center,min(1.3,center+width)]) if c.adaptive else np.array([.7,1.,1.3])
    npcs=np.array([[*other,uncertainty] for _,other,uncertainty in vehicles],float).reshape(-1,7)
    args=(c.issued.steering,cfg.dt,cfg.horizon,c._gains,c._route,npcs,cfg.vehicle_radius,cfg.buffer,cfg.uncertainty_rate,cfg.steering_limit,cfg.steering_rate)
    def values(steering,plan=None):
        return np.array([rollout(z,steering,accel,args[0],args[1],args[2],s,*args[3:],c.feedback_stiffness,plan) for s in models])
    base=constrain(Command(c.baseline_fn(z,c.route),accel),c.issued,cfg)
    key=(tuple(z),accel,c.issued.steering,center,width,tuple(npcs.ravel()))
    if c._cost_reference is None or c._cost_reference[0]!=key:c._cost_reference=(key,values(base.steering))
    reference=c._cost_reference[1]
    planned=c._plan is not None and c._plan_residual is not None and abs(residual-c._plan_residual)<1e-12
    result=values(first.steering,c._plan) if planned else (reference if first.steering==base.steering else values(first.steering))
    margin=float(result[:,1].min())
    if first.steering!=base.steering or planned:
        if (np.any(result[:,0]>=reference[:,0]-1e-9)
            or np.any(result[:,2]>c.secondary_factor**2*reference[:,2]+2e-6)
            or np.any(result[:,3]>c.secondary_factor**2*reference[:,3]+1e-5)):
            margin=min(margin,-1e-9)
    return float(result[:,0].mean()),margin
