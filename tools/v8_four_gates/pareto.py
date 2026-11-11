"""Nominal R16 backup, adaptive planning and strict predicted quality dominance."""
from dataclasses import replace
import numpy as np
from integrations.unified_lans.physics import Config,Command,constrain
from tools.unified_control_v4.control import gain_table
from .longitudinal import Controller as Parent
from .pareto_kernels import rollout


class Controller(Parent):
    def __init__(self,route,scenario='following',cfg=None,delay=0.,*,planning_horizon=2.,planner_factor=1.,**kw):
        if planning_horizon not in (2.,3.) or planner_factor not in (1.,.995):raise ValueError('declared development arms only')
        kw['quality_factor']=1.;kw['secondary_factor']=1.;kw['tracking_only']=False
        super().__init__(route,scenario,replace(cfg or Config(),horizon=planning_horizon),delay,**kw)
        self._nominal_gains=gain_table(self.baseline_fn.penalty,1.);self._model_gains=self._gains;self._model_feedback=self.feedback_stiffness
        self._gains=self._nominal_gains;self.feedback_stiffness=1.;self.baseline_fn.stiffness=1.
        if self.planner is not None:
            self.planner.factor=planner_factor;original=self.planner.plan
            def adaptive_plan(*a,**k):
                self._gains=self._model_gains;self.feedback_stiffness=self._model_feedback
                try:return original(*a,**k)
                finally:self._gains=self._nominal_gains;self.feedback_stiffness=1.
            self.planner.plan=adaptive_plan

    def update_model(self):
        self._gains=self._model_gains;self.feedback_stiffness=self._model_feedback;self.baseline_fn.stiffness=self._model_feedback
        try:
            super().update_model();self._model_gains=self._gains;self._model_feedback=self.feedback_stiffness
        finally:self._gains=self._nominal_gains;self.feedback_stiffness=1.;self.baseline_fn.stiffness=1.

    def cost(self,z,first,residual,accel,vehicles,lifetime):
        planned=self._plan is not None and self._plan_residual is not None and abs(residual-self._plan_residual)<1e-12
        key=(tuple(z),first.steering,accel,self.issued.steering,self.stiffness_estimate,self.stiffness_uncertainty,
            tuple((n,tuple(o),u) for n,o,u in vehicles),tuple(self._plan) if planned else None)
        if key in self._candidate_cache:self.cache_hits+=1;return self._candidate_cache[key]
        cfg=self.cfg;center=self.stiffness_estimate if self.adaptive else 1.;width=self.stiffness_uncertainty
        models=[max(.7,center-width),center,min(1.3,center+width)] if self.adaptive else [.7,1.,1.3]
        npcs=np.array([[*other,unc] for _,other,unc in vehicles],float).reshape(-1,7)
        def values(u,plan=None):
            return np.array([rollout(z,u,accel,self.issued.steering,cfg.dt,cfg.horizon,s,self._nominal_gains,self._route,npcs,
                cfg.vehicle_radius,cfg.buffer,cfg.uncertainty_rate,cfg.steering_limit,cfg.steering_rate,1.,plan) for s in models])
        base=constrain(Command(self.baseline_fn(z,self.route),accel),self.issued,cfg)
        refkey=(tuple(z),accel,self.issued.steering,center,width,tuple(npcs.ravel()))
        if self._cost_reference is None or self._cost_reference[0]!=refkey:self._cost_reference=(refkey,values(base.steering))
        reference=self._cost_reference[1];result=values(first.steering,self._plan) if planned else reference if first.steering==base.steering else values(first.steering)
        margin=float(result[:,1].min())
        if first.steering!=base.steering or planned:
            if (np.any(result[:,0]>=reference[:,0]-1e-9) or np.any(result[:,2]>reference[:,2]+1e-12) or np.any(result[:,3]>reference[:,3]+1e-12)):margin=min(margin,-1e-9)
        answer=float(result[:,0].mean()),margin;self._candidate_cache[key]=answer;return answer

    def decide(self,*a,**k):
        r=super().decide(*a,**k);r.update(quality_reference='fixed_nominal_R16',objective='lateral_SSE',model_feedback=self._model_feedback,prediction_horizon=self.cfg.horizon);return r
