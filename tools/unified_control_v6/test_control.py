import numpy as np
from integrations.unified_lans.physics import Route, Config
from tools.unified_campaign.study import Clock
from tools.unified_control_v5.control import project
from tools.unified_control_v4.kernels import rollout, step, lqr
from tools.unified_control_v6.control import Controller, refine


def test_per_knot_refinement_keeps_legal_commands_and_nonincreasing_objective():
    c=Controller(Route('sine'),penalty=16.,clock=Clock())
    z=np.array([0.,.2,.01,12.,0.,0.]);initial=np.zeros(20);npcs=np.empty((0,7))
    seed=project(z,initial,-3.,0.,.05,1.,c._gains,c._route,.5,.6,.08)
    result=refine(z,initial,seed,-3.,0.,.05,1.,1.,c._gains,c._route,npcs,2.3,.5,.6,.5,.6,.08,1.)
    assert np.max(np.abs(np.diff(np.r_[0.,result])))<=.03+1e-12
    assert np.max(abs(result))<=.5
    state=z.copy()
    for u in result:
        baseline=lqr(state,c._gains,int(c._route[0]),*c._route[1:])
        # Projection can prioritize physical slew over nominal residual when
        # both sets do not intersect; this is the existing actuator convention.
        state=step(state,u,-3.,.05,1.)
    args=(-3.,0.,.05,1.,1.,c._gains,c._route,npcs,2.3,.5,.6,.5,.6,1.)
    assert rollout(z,result[0],*args,result)[0]<=rollout(z,seed[0],*args,seed)[0]+1e-12


def test_warm_plan_is_owned_per_controller_and_has_finite_lifetime():
    cfg=Config(horizon=1.)
    a=Controller(Route('straight'),cfg=cfg,penalty=16.,mpc=True,clock=Clock())
    b=Controller(Route('straight'),cfg=cfg,penalty=16.,mpc=True,clock=Clock())
    assert a.planner.warm is None and b.planner.warm is None
    a.planner.warm=np.ones(20)
    assert b.planner.warm is None
