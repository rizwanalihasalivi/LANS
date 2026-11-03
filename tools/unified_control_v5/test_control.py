import numpy as np
from tools.unified_control_v5.control import refine,project,Controller
from integrations.unified_lans.physics import Route,Config,Command
from tools.unified_campaign.study import Clock
from tools.unified_control_v4.kernels import rollout


def test_nonlinear_plan_refinement_preserves_constraints_and_objective():
    c=Controller(Route('sine'),penalty=16.,clock=Clock())
    z=np.array([0.,.2,.01,12.,0.,0.]);initial=np.zeros(20);npcs=np.empty((0,7));cfg=Config(horizon=1.)
    seed=project(z,initial,-3.,0.,.05,1.,c._gains,c._route,.5,.6,.08)
    result=refine(z,initial,-3.,0.,.05,1.,1.,c._gains,c._route,npcs,2.3,.5,.6,.5,.6,.08,1.)
    assert np.max(np.abs(np.diff(np.r_[0.,result])))<=.03+1e-12
    assert np.max(abs(result))<=.5
    old=rollout(z,seed[0],-3.,0.,.05,1.,1.,c._gains,c._route,npcs,2.3,.5,.6,.5,.6,1.,seed)
    new=rollout(z,result[0],-3.,0.,.05,1.,1.,c._gains,c._route,npcs,2.3,.5,.6,.5,.6,1.,result)
    assert new[0]<=old[0]+1e-12
