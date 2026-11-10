import numpy as np
from integrations.unified_lans.physics import advance,Command
from .cbf_reference import scalar_qp,world_acceleration


def test_scalar_qp_satisfies_every_barrier_and_minimizes_declared_objective():
    constraints=[(2.,-.1),(-1.,.2)]
    u=scalar_qp(-.1,0.,-.3,.3,constraints)
    assert u==.05 and all(a*u+b>=-1e-12 for a,b in constraints)
    assert scalar_qp(0.,0.,-.3,.3,[(1.,-.5)]) is None
    assert scalar_qp(0.,0.,-.3,.3,[(0.,-1.)]) is None


def test_world_acceleration_matches_finite_difference_of_independent_rk4_flow():
    from integrations.unified_lans.traffic import velocity
    z=np.array([0.,.2,.04,12.,.3,.02]);u=.025;a=-1.;h=1e-6
    numerical=(velocity(advance(z,Command(u,a),h,.85))-velocity(z))/h
    np.testing.assert_allclose(world_acceleration(z,u,a,.85),numerical,rtol=2e-4,atol=2e-4)


def test_filter_has_one_rate_budget_relative_to_the_previous_tick():
    from .cbf_reference import Controller
    from tools.unified_control_v9.learning import run_episode
    from tools.unified_campaign.study import make_case
    _,rows=run_episode(make_case('development',0),'lqr',grid=False,seconds=.5,
        controller_factory=Controller,controller_kwargs=dict(mpc=False,adaptive=False))
    previous=0.
    for row in rows:
        assert abs(row['issued_steering']-previous)<=.03+1e-12
        previous=row['issued_steering']
