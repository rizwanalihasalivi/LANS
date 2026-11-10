"""Cached unchanged v8 steering admission with explicit longitudinal recourse."""
import time
from integrations.unified_lans.physics import Command
from tools.unified_control_v9.runtime import RuntimeController as Prior
from tools.unified_control_v8.control import Controller as V8
from .recovery import choose
from .quality import cost as quality_cost


class Cached:
    def __init__(self,*args,recovery=True,secondary_factor=1.10,**kwargs):
        if not 1.<=secondary_factor<=1.10:raise ValueError('secondary guard may only tighten v8 limits')
        self.secondary_factor=float(secondary_factor)
        super().__init__(*args,**kwargs)
        self.recovery_enabled=recovery;self._candidate_cache={};self.cache_hits=0

    def cost(self,z,first,residual,accel,vehicles,lifetime):
        planned=self._plan is not None and self._plan_residual is not None and abs(residual-self._plan_residual)<1e-12
        key=(tuple(z),first.steering,accel,self.issued.steering,self.stiffness_estimate,
             self.stiffness_uncertainty,self.feedback_stiffness,
             tuple((name,tuple(other),unc) for name,other,unc in vehicles),
             tuple(self._plan) if planned else None,self.secondary_factor)
        if key not in self._candidate_cache:
            self._candidate_cache[key]=(super().cost(z,first,residual,accel,vehicles,lifetime)
                if self.secondary_factor==1.10 else quality_cost(self,z,first,residual,accel,vehicles,lifetime))
        else:self.cache_hits+=1
        return self._candidate_cache[key]

    def decide(self,now,worker_failed=False):
        started=time.perf_counter()
        self._candidate_cache={};self.cache_hits=0
        result=super().decide(now,worker_failed)
        recourse=None
        if self.recovery_enabled and result['reason']=='no_feasible_prediction' and not result['ego_backup'] and not result['missing']:
            z=self.forecast(now)
            nominal=max(-self.cfg.max_brake,min(self.cfg.max_accel,.8*(self.target_speed-z[3])))
            recourse=choose(self,now,self.issued,nominal)
            if recourse is not None and recourse['selected']['accel']!=self.issued.accel:
                command=Command(self.issued.steering,recourse['selected']['accel'])
                self.pending[-1]=(now+self.delay,command);self.issued=command
                result.update(source='recovery_lqr',residual=0.,issued_accel=command.accel,
                    reason='longitudinal_recourse',planned_candidate_selected=False)
        result.update(recovery=recourse,candidate_cache_hits=self.cache_hits)
        result['complete_decision_ms']=1000*(time.perf_counter()-started)
        return result


class Controller(Cached,Prior):
    """V8 conic/early-ID law with asynchronous execution and cached admission."""


class Synchronous(Cached,V8):
    """Numerically equivalent cached v8 reference, plus common safety recourse."""
