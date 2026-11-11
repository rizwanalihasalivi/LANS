import numpy as np
import pytest
from tools.unified_control_v4.kernels import step as previous_step,rollout as previous_rollout
from tools.unified_control_v4.control import gain_table
from tools.v8_reliability.traffic_guard import Controller as Previous
from tools.unified_control_v9.learning import run_episode
from .fast_kernels import step,rollout
from .fast_cost import EquivalentController


def test_scalar_rk4_matches_frozen_array_rk4_over_low_and_high_speed():
    rng=np.random.default_rng(101121)
    for i in range(300):
        z=np.array([rng.uniform(-20,100),rng.uniform(-2,2),rng.uniform(-3.1,3.1),rng.uniform(0,24),rng.uniform(-.5,.5),rng.uniform(-.5,.5)])
        u,a,s=rng.uniform(-.5,.5),rng.uniform(-6,2.5),rng.uniform(.7,1.3);dt=(.005,.05,.1)[i%3]
        np.testing.assert_allclose(step(z,u,a,dt,s),previous_step(z,u,a,dt,s),rtol=0,atol=2e-13)


@pytest.mark.parametrize('planned',[False,True])
def test_rollout_matches_every_frozen_score_and_margin(planned):
    rng=np.random.default_rng(101122);g=gain_table(16.,1.)
    for kind in range(3):
        for i in range(12):
            z=np.array([rng.uniform(0,30),rng.uniform(-.4,.4),rng.uniform(-.02,.02),rng.uniform(4,20),rng.uniform(-.1,.1),rng.uniform(-.05,.05)])
            n=np.array([[32.,0.,0.,8.,0.,0.,.03]]);route=np.array([kind,(-1.)**i,1.,.9]);plan=np.linspace(-.02,.02,40) if planned else None
            args=(z,.02,-1.,-.01,.05,2.,.8,g,route,n,2.3,.5,.6,.5,.6,1.,plan)
            np.testing.assert_allclose(rollout(*args),previous_rollout(*args),rtol=0,atol=2e-10)


def test_changed_kernel_preserves_closed_loop_decisions_and_commands():
    c=dict(id=0,scenario='merge',mirror=1,speed=12.,stiffness=.8,lateral=.3,heading=.005,phase=1.,amplitude=.9,network='nominal',delay=.1,network_seed=31)
    kwargs=dict(quality_factor=1.1,secondary_factor=1.075,early_id=True,tracking_only=False,adaptive=True,mpc=False)
    a,ra=run_episode(c,'hybrid',controller_factory=Previous,controller_kwargs=kwargs)
    b,rb=run_episode(c,'hybrid',controller_factory=EquivalentController,controller_kwargs=kwargs)
    assert len(ra)==len(rb)
    for x,y in zip(ra,rb):
        assert x['source']==y['source'] and x['issued_steering']==y['issued_steering'] and x['issued_accel']==y['issued_accel']
    assert a['rmse_m']==b['rmse_m']
