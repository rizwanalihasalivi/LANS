import math
import numpy as np
import pytest
from integrations.unified_lans.physics import Route,Config,Command,advance,constrain
from integrations.unified_lans.traffic import Packet
from tools.unified_campaign.study import Clock,StudyRoute
from tools.unified_control_v9.baselines import Controller,steering,LF,LR,WHEELBASE,predict_geometric


def test_stanley_straight_road_uses_front_axle_error_and_heading_sign():
    route=np.array([0.,1.,0.,1.]);z=np.array([0.,.3,.02,12.,0.,0.]);gain=1.
    expected=-.02+math.atan2(-gain*(.3+LF*math.sin(.02)),12.)
    assert steering(z,route,0,gain)==pytest.approx(expected,abs=1e-12)


def test_pure_pursuit_straight_road_matches_circle_geometry():
    route=np.array([0.,1.,0.,1.]);z=np.array([0.,.3,0.,12.,0.,0.]);lookahead=2.+.3*12
    expected=math.atan2(-2*WHEELBASE*.3,lookahead**2)
    assert steering(z,route,1,.3)==pytest.approx(expected,abs=1e-8)


@pytest.mark.parametrize('method,parameter',[(0,1.),(1,.3)])
def test_geometric_controllers_preserve_mirror_symmetry_and_finite_stop(method,parameter):
    z=np.array([7.,.4,.03,12.,.2,-.01]);mirror=z*np.array([1.,-1.,-1.,1.,-1.,-1.])
    a=steering(z,np.array([1.,1.,3.,.9]),method,parameter)
    b=steering(mirror,np.array([1.,-1.,3.,.9]),method,parameter)
    assert a==pytest.approx(-b,abs=1e-12)
    z[3]=0.;assert math.isfinite(steering(z,np.array([0.,1.,0.,1.]),method,parameter))


@pytest.mark.parametrize('method,parameter',[('stanley',1.),('pure_pursuit',.3)])
def test_common_delay_freshness_and_bounded_braking_are_preserved(method,parameter):
    clock=Clock();cfg=Config(horizon=2.)
    c=Controller(Route('straight'),cfg=cfg,delay=.1,clock=clock,method=method,parameter=parameter)
    z=np.array([0.,.3,0.,12.,0.,0.]);c.inbox.ingest(Packet('ego',0,0.,tuple(z)),0.)
    first=c.decide(0.);assert abs(first['issued_steering'])<=.03 and first['issued_accel']==0.
    c.apply(0.,z);assert c.applied==Command()
    c.apply(.05,z);assert c.applied==Command()
    c.apply(.1,z);assert c.applied.steering==pytest.approx(first['issued_steering'])
    # A genuinely unavailable reconstruction forces the common held-brake path.
    clock.now=3.;result=c.decide(3.)
    assert result['source']=='hold_brake' and result['issued_accel']==-6.


def test_geometric_prediction_rolls_out_its_own_law_with_independent_plant():
    c=Controller(StudyRoute('sine',-1.,3.,.9),cfg=Config(horizon=.5),method='pure_pursuit',parameter=.3)
    y,h,_=c.route.geometry(0.);z=np.array([0.,y+.3,h-.01,12.,0.,0.]);accel=-.5;cfg=c.cfg
    first=constrain(Command(c.geometric_command(z,c.route),accel),Command(),cfg)
    actual=predict_geometric(z,first.steering,accel,0.,cfg.dt,cfg.horizon,.83,c._route,
        np.empty((0,7)),cfg.vehicle_radius,cfg.buffer,cfg.uncertainty_rate,.5,.6,1,.3)
    total=0.;margin=1e9;previous=Command();state=z.copy()
    for i in range(10):
        u=first if i==0 else constrain(Command(c.geometric_command(state,c.route),accel),previous,cfg)
        state=advance(state,u,.05,.83);ref,heading,_=c.route.geometry(state[0])
        ey=state[1]-ref;ep=math.atan2(math.sin(state[2]-heading),math.cos(state[2]-heading))
        total+=.05*(8*ey**2+2*ep**2+.03*u.steering**2+.02*((u.steering-previous.steering)/.05)**2)
        margin=min(margin,1.75-abs(ey));previous=u
    np.testing.assert_allclose(actual,[total,margin],rtol=0,atol=1e-12)


def test_invalid_method_and_nonfinite_gain_rejected():
    with pytest.raises(ValueError):Controller(Route(),method='invented')
    with pytest.raises(ValueError):Controller(Route(),parameter=math.nan)
