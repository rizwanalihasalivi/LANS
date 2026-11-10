"""Publication-validation candidates with explicit quality and feedback choices."""
import numpy as np
from integrations.unified_lans.physics import Command,constrain
from tools.unified_control_v4.kernels import rollout
from tools.unified_control_v4.control import gain_table
from .runtime import RuntimeController


class Controller(RuntimeController):
    def __init__(self,*args,guard_factor=1.,nominal_feedback=False,**kwargs):
        if not 1.<=guard_factor<=1.1:raise ValueError('quality guard must be within [1,1.1]')
        self.guard_factor=float(guard_factor);self.nominal_feedback=bool(nominal_feedback)
        super().__init__(*args,**kwargs)

    def update_model(self):
        super().update_model()
        if self.nominal_feedback:
            self.feedback_stiffness=1.;self.baseline_fn.stiffness=1.
            self._gains=gain_table(self.baseline_fn.penalty,1.)

    def cost(self,z,first,residual,accel,vehicles,lifetime):
        cfg=self.cfg;center=self.stiffness_estimate if self.adaptive else 1.;width=self.stiffness_uncertainty
        models=np.array([max(.7,center-width),center,min(1.3,center+width)]) if self.adaptive else np.array([.7,1.,1.3])
        npcs=np.array([[*other,uncertainty] for _,other,uncertainty in vehicles],float).reshape(-1,7)
        args=(self.issued.steering,cfg.dt,cfg.horizon,self._gains,self._route,npcs,cfg.vehicle_radius,cfg.buffer,cfg.uncertainty_rate,cfg.steering_limit,cfg.steering_rate)
        def values(steering,plan=None):
            return np.array([rollout(z,steering,accel,args[0],args[1],args[2],s,*args[3:],self.feedback_stiffness,plan) for s in models])
        base=constrain(Command(self.baseline_fn(z,self.route),accel),self.issued,cfg)
        key=(tuple(z),accel,self.issued.steering,center,width,tuple(npcs.ravel()))
        if self._cost_reference is None or self._cost_reference[0]!=key:self._cost_reference=(key,values(base.steering))
        reference=self._cost_reference[1]
        planned=self._plan is not None and self._plan_residual is not None and abs(residual-self._plan_residual)<1e-12
        result=values(first.steering,self._plan) if planned else (reference if first.steering==base.steering else values(first.steering))
        margin=float(result[:,1].min())
        if first.steering!=base.steering or planned:
            # Preserve the mixed cost and physical guards; test a declared stricter quality factor.
            if (np.any(result[:,0]>=reference[:,0]-1e-9)
                or np.any(result[:,2]>self.guard_factor**2*reference[:,2]+2e-6)
                or np.any(result[:,3]>self.guard_factor**2*reference[:,3]+1e-5)):
                margin=min(margin,-1e-9)
        return float(result[:,0].mean()),margin
