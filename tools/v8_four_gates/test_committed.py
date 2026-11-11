import numpy as np
import pytest
from tools.unified_control_v9.learning import setup as make_fixture
from .committed import Controller,Planner


class Capture:
    busy=False;failed=False
    def submit(self,request,now):self.request=request;self.busy=True;return True
    def close(self):pass


@pytest.mark.parametrize('delay',[0.,.1])
def test_request_starts_after_the_actually_committed_fifo_prefix(delay):
    case=dict(id=0,scenario='curved',mirror=1,speed=12.,stiffness=1.,delay=delay,lateral=.3,heading=.005,phase=1.,amplitude=.9,network='nominal',network_seed=31)
    c,clock,ego,npcs,net=make_fixture(case,'lqr',Controller,dict(adaptive=False,mpc=False,barrier_frequency=3.),grid=False)
    net.emit(0.,ego,npcs,c.inbox);c.decide(0.);backend=Capture();p=Planner(c,backend,1.,.15,False)
    assert p.submit_after_issue(0.)
    request=backend.request
    for i in range(round(delay/.05)+1):ego=c.apply(i*.05,ego,1.)
    np.testing.assert_allclose(request.state,ego,rtol=0,atol=2e-13)
    assert request.previous==c.issued.steering and request.application_s==pytest.approx(delay+.05)
    assert request.observed_s==0. and request.wall_submitted==0.
    # Prediction never renews observation age: delay100ms+service50ms is
    # exactly the old150ms boundary and remains ineligible.
    assert p.fresh(request,.05,.05)==(delay==0.)


def test_submission_rejects_missing_fresh_observations():
    case=dict(id=0,scenario='following',mirror=1,speed=12.,stiffness=1.,delay=0.,lateral=.3,heading=.005,phase=1.,amplitude=.9,network='nominal',network_seed=31)
    c,clock,ego,npcs,net=make_fixture(case,'lqr',Controller,dict(adaptive=False,mpc=False),grid=False)
    p=Planner(c,Capture(),1.,.15,False)
    assert not p.submit_after_issue(0.)
