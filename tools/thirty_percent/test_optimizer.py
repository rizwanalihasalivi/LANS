import numpy as np
from integrations.unified_lans.physics import Command,Route,advance
from tools.unified_control_v4.control import gain_table,ScheduledLQR
from tools.thirty_percent.optimizer import rollout,Objective


def test_zero_residual_reproduces_constrained_lqr_and_independent_physics():
    state=np.array([0.,.25,.01,12.,0.,0.]);initial=state.copy();accels=np.full(20,-.5)
    npcs=np.array([[[40.+i*.4,0.,0.,8.,0.,0.]] for i in range(20)])
    values,states,steers,bases=rollout(np.zeros(20),initial,accels,npcs,.8,gain_table(16.,1.),np.array([0.,1.,0.,1.]))
    control=ScheduledLQR(16.);previous=0.
    for i in range(20):
        base=control(state,Route('straight'));u=min(.5,max(-.5,min(previous+.03,max(previous-.03,base))))
        assert abs(base-bases[i])<1e-12 and abs(u-steers[i])<1e-12
        state=advance(state,Command(u,accels[i]),.05,.8)
        np.testing.assert_allclose(state,states[i],rtol=0,atol=1e-12);previous=u


def test_optimizer_derivative_matches_an_independent_directional_difference():
    initial=np.array([0.,.1,.005,10.,0.,0.]);accels=np.zeros(20);npcs=np.full((20,1,6),0.);npcs[:,:,0]=100.
    args=(initial,accels,npcs,1.,gain_table(16.,1.),np.array([0.,1.,0.,1.]))
    reference=rollout(np.zeros(20),*args)[0];objective=Objective(*args,reference,True)
    x=np.full(20,.05);direction=np.sin(np.arange(20));eps=1e-6
    central=(objective.fun(x+eps*direction)-objective.fun(x-eps*direction))/(2*eps)
    np.testing.assert_allclose(objective.grad(x)@direction,central,rtol=3e-3,atol=2e-5)
