"""Strict fixed-reference quality admission with multi-model conic proposals."""
from tools.unified_control_v9.runtime import ProposalPlanner
from .pareto import Controller as Parent
from .robust_planner import Logical,Process


class Controller(Parent):
    def __init__(self,*a,planner_service_s=.05,planner_wall_stall_s=0.,planner_ttl_s=.15,planner_factor=1.,**kw):
        super().__init__(*a,planner_service_s=planner_service_s,planner_wall_stall_s=planner_wall_stall_s,planner_ttl_s=planner_ttl_s,planner_factor=planner_factor,**kw)
        if self.planner is not None:
            self.planner.close()
            backend=Logical(self,planner_service_s) if self.planner_backend=='logical' else Process(self,self.cfg,planner_factor,planner_wall_stall_s)
            self.planner=ProposalPlanner(self,backend,planner_factor,planner_ttl_s,self.planner_backend=='process')
