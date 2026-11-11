import math
import numpy as np
import pytest
from integrations.unified_lans.physics import Config,Route,Command,advance
from integrations.unified_lans.traffic import Packet,velocity
from .longitudinal import interval,acceleration_constraints,Controller


def test_projection_selects_closest_feasible_acceleration():
    a,lo,hi=interval(2.,-6.,2.5,[(2.,2.),(-1.,.4)])
    assert a==.4 and lo==-1. and hi==.4
    assert interval(0.,-6.,2.5,[(1.,-3.)])[0] is None


def test_acceleration_barrier_matches_independent_second_difference():
    z=np.array([1.,.2,.01,12.,.05,.01]);other=np.array([25.,-10.,math.pi/2,7.,0.,0.]);cfg=Config();omega=2.
    con=acceleration_constraints(z,.015,Route('straight'),(('p',other,.02),),[1.],cfg,omega)[1]
    def h(t,accel):
        state=advance(z,Command(.015,accel),t,1.)
        p=state[:2]-(other[:2]+velocity(other)*t);radius=4.6+.5+.02+.6*t
        return float(p@p-radius*radius)
    for accel in (-2.,1.):
        eps=1e-3;hh=h(0.,accel);h1=h(eps,accel);h2=h(2*eps,accel);h3=h(3*eps,accel)
        hd=(-3*hh+4*h1-h2)/(2*eps);hdd=(2*hh-5*h1+4*h2-h3)/eps**2
        assert con[0]*accel+con[1]==pytest.approx(hdd+2*omega*hd+omega**2*hh,abs=.05)


@pytest.mark.parametrize('missing',['ego','peer'])
def test_source_failure_still_brakes(missing):
    c=Controller(Route('straight'),cfg=Config(horizon=2.),penalty=16.,mpc=False);c.expected={'p'}
    if missing!='ego':c.inbox.ingest(Packet('ego',0,0.,(0.,.3,0.,12.,0.,0.)),0.)
    if missing!='peer':c.inbox.ingest(Packet('p',0,0.,(30.,0.,0.,8.,0.,0.)),0.)
    r=c.decide(0.);assert r['issued_accel']==-6. and r['recovery'] is None
