import math
import numpy as np
from integrations.unified_lans.physics import Route,Config,Command,advance,constrain
from integrations.unified_lans.traffic import Packet
from tools.unified_campaign.study import Clock,StudyRoute
from tools.unified_control_v4.control import ScheduledLQR
from tools.unified_control_v4.kernels import rollout
from tools.unified_control_v8.control import Controller,tracking_rollout


def observe_transition(stiffness=.83,steering=.03,noise=0.):
    controller=Controller(Route('straight'),cfg=Config(horizon=2.),clock=Clock(),
                          penalty=16.,adaptive=True,mpc=False,early_id=True)
    initial=np.array([0.,.3,0.,12.,0.,0.]);command=Command(steering,0.)
    controller.inbox.ingest(Packet('ego',0,0.,tuple(initial)),0.);controller.update_model()
    after=advance(initial,command,.05,stiffness);after[4]+=noise
    controller.history=[(0.,.05,command)]
    controller.inbox.ingest(Packet('ego',1,.05,tuple(after)),.05);controller.update_model()
    return controller


def test_early_identification_contains_off_grid_truth_without_six_sample_wait():
    for stiffness in [.83,.987,1.173]:
        c=observe_transition(stiffness)
        assert c._id_steps==1 and .025<=c.stiffness_uncertainty<.3
        assert abs(c.stiffness_estimate-stiffness)<=c.stiffness_uncertainty


def test_boundary_grid_mismatch_remains_conservative():
    for stiffness in [.71,1.29]:
        c=observe_transition(stiffness)
        assert c._id_steps==1 and c.stiffness_uncertainty==.3
        assert abs(c.stiffness_estimate-stiffness)<=c.stiffness_uncertainty


def test_zero_excitation_and_inconsistent_observation_keep_broad_uncertainty():
    zero=observe_transition(steering=0.)
    assert zero._id_steps==0 and zero.stiffness_uncertainty==.3
    for noise in [.01,.3]:
        mismatch=observe_transition(noise=noise)
        assert mismatch.stiffness_uncertainty==.3


def test_tracking_kernel_matches_independent_physics_and_original_quality_margins():
    route=StudyRoute('sine',-1.,3.,.9);y,h,_=route.geometry(0.)
    z=np.array([0.,y+.27,h-.01,12.,0.,0.]);c=Controller(route,cfg=Config(horizon=1.),penalty=16.,mpc=False)
    cfg=c.cfg;n=20;plan=np.linspace(-.03,.02,n);accel=-1.;previous=0.
    npcs=np.array([[25.,3.,0.,8.,0.,0.,.1]])
    args=(z,plan[0],accel,previous,cfg.dt,cfg.horizon,.83,c._gains,c._route,npcs,
          cfg.vehicle_radius,cfg.buffer,cfg.uncertainty_rate,cfg.steering_limit,cfg.steering_rate,1.,plan)
    new=tracking_rollout(*args);old=rollout(*args)
    np.testing.assert_allclose(new[1:],old[1:],rtol=0,atol=1e-12)
    state=z.copy();last=Command(previous,accel);sse=0.;baseline=ScheduledLQR(16.)
    for i in range(n):
        steering=plan[0] if i==0 else np.clip(plan[i],baseline(state,route)-.08,baseline(state,route)+.08)
        command=constrain(Command(steering,accel),last,cfg)
        state=advance(state,command,cfg.dt,.83);sse+=cfg.dt*(state[1]-route.geometry(state[0])[0])**2
        last=command
    assert math.isclose(new[0],sse,rel_tol=0,abs_tol=1e-12)
