"""Same admission arithmetic and budgets with allocation-free rollout internals."""
import numpy as np
from integrations.unified_lans.physics import Command,constrain
from tools.v8_reliability.traffic_guard import Controller as Published
from .longitudinal import Controller as Continuous
from .fast_kernels import rollout


class Cost:
    def cost(self,z,first,residual,accel,vehicles,lifetime):
        if self.tracking_only:return super().cost(z,first,residual,accel,vehicles,lifetime)
        planned=self._plan is not None and self._plan_residual is not None and abs(residual-self._plan_residual)<1e-12
        key=(tuple(z),first.steering,accel,self.issued.steering,self.stiffness_estimate,self.stiffness_uncertainty,self.feedback_stiffness,
            tuple((name,tuple(other),unc) for name,other,unc in vehicles),tuple(self._plan) if planned else None,self.secondary_factor)
        if key in self._candidate_cache:self.cache_hits+=1;return self._candidate_cache[key]
        cfg=self.cfg;center=self.stiffness_estimate if self.adaptive else 1.;width=self.stiffness_uncertainty
        models=np.array([max(.7,center-width),center,min(1.3,center+width)]) if self.adaptive else np.array([.7,1.,1.3])
        npcs=np.array([[*other,unc] for _,other,unc in vehicles],float).reshape(-1,7)
        args=(self.issued.steering,cfg.dt,cfg.horizon,self._gains,self._route,npcs,cfg.vehicle_radius,cfg.buffer,cfg.uncertainty_rate,cfg.steering_limit,cfg.steering_rate)
        def values(u,plan=None):return np.array([rollout(z,u,accel,args[0],args[1],args[2],s,*args[3:],self.feedback_stiffness,plan) for s in models])
        base=constrain(Command(self.baseline_fn(z,self.route),accel),self.issued,cfg)
        reference_key=(tuple(z),accel,self.issued.steering,center,width,tuple(npcs.ravel()))
        if self._cost_reference is None or self._cost_reference[0]!=reference_key:self._cost_reference=(reference_key,values(base.steering))
        reference=self._cost_reference[1];result=values(first.steering,self._plan) if planned else reference if first.steering==base.steering else values(first.steering)
        margin=float(result[:,1].min())
        if first.steering!=base.steering or planned:
            if (np.any(result[:,0]>=reference[:,0]-1e-9) or np.any(result[:,2]>self.secondary_factor**2*reference[:,2]+2e-6)
                or np.any(result[:,3]>self.secondary_factor**2*reference[:,3]+1e-5)):margin=min(margin,-1e-9)
        answer=float(result[:,0].mean()),margin;self._candidate_cache[key]=answer;return answer


class EquivalentController(Cost,Published):pass
class Controller(Cost,Continuous):pass
