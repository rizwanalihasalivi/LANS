"""Original v8 proposal law with causal committed-prefix service alignment."""
import time
from tools.unified_control_v4.control import gain_table
from .fast_cost import Controller as Parent
from .committed import Planner


class Controller(Parent):
    def __init__(self,*a,feedback_weight=1.,**kw):
        if feedback_weight not in (0.,.5,1.):raise ValueError('declared development feedback arms only')
        self.feedback_weight=feedback_weight;super().__init__(*a,**kw)
        if self.planner is not None:
            p=self.planner;self.planner=Planner(self,p.backend,p.factor,p.ttl_s,p.process_mode)
    def update_model(self):
        super().update_model()
        if self.adaptive:
            identified=round(self.stiffness_estimate*20)/20
            self.feedback_stiffness=round((1.+self.feedback_weight*(identified-1.))*20)/20
            self.baseline_fn.stiffness=self.feedback_stiffness;self._gains=gain_table(self.baseline_fn.penalty,self.feedback_stiffness)
    def decide(self,now,worker_failed=False):
        start=time.perf_counter();result=super().decide(now,worker_failed);submitted=False
        if self.planner is not None and not worker_failed:submitted=self.planner.submit_after_issue(now)
        result.update(planner_committed_prefix=True,planner_submitted_after_issue=submitted,feedback_weight=self.feedback_weight,planner_busy=self.planner.backend.busy if self.planner else False,complete_decision_ms=1000*(time.perf_counter()-start));return result
