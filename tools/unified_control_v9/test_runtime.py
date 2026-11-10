from dataclasses import replace
import time
import numpy as np
import pytest
from integrations.unified_lans.physics import Config,Route,Command,advance
from integrations.unified_lans.traffic import Packet
from tools.unified_campaign.study import Clock
from tools.unified_control_v5.control import project
from tools.unified_control_v9.runtime import RuntimeController,LogicalPlanner,AsyncPlanner,Response


def controller(**kwargs):
    return RuntimeController(Route('straight'),cfg=Config(horizon=.5),clock=Clock(),
        penalty=16.,adaptive=True,mpc=True,**kwargs)


def fake_solution(request):
    return Response(request.key,'Solved',tuple(np.linspace(-.03,.03,round(request.cfg.horizon/request.cfg.dt))),0.)


def seed(c):
    state=np.array([0.,.3,0.,12.,0.,0.]);c.inbox.ingest(Packet('ego',0,0.,tuple(state)),0.)
    c.planner.backend.solver=fake_solution
    c.decide(0.)
    return state,c.planner.backend.pending[1]


def test_logical_service_does_not_admit_future_response_and_is_single_request():
    c=controller();_,request=seed(c);backend=c.planner.backend
    assert backend.busy and c.planner.accepted==0
    assert backend.poll(.049) is None
    assert not backend.submit(replace(request,sequence=2),.01)
    original,response=backend.poll(.05)
    assert original==request and response.key==request.key and not backend.busy
    c.close()


def test_shifted_plan_is_reprojected_using_current_state_and_limits():
    c=controller();_,request=seed(c)
    c._decision_now=.05
    state=np.array([.6,-.3,-.01,12.,0.,0.])
    c.inbox.ingest(Packet('ego',1,.05,tuple(state)),.05)
    plan=c.planner.plan(state,c.route,0.,c.cfg,1.,16.)
    assert c.planner.shift==1 and c.planner.used_request==request
    assert len(plan)==10 and c.planner.accepted==1
    reprojection=project(state,plan,0.,0.,.05,1.,c._gains,c._route,.5,.6,.08,c.feedback_stiffness)
    np.testing.assert_allclose(plan,reprojection,rtol=0,atol=1e-12)
    assert np.max(np.abs(plan))<=.5 and np.max(np.abs(np.diff(np.r_[0.,plan])))<=.03+1e-12
    c.close()


@pytest.mark.parametrize('kind',['nan','unsolved','wrong_identity','expired','misaligned'])
def test_bad_or_stale_response_never_becomes_a_candidate(kind):
    c=controller();state,request=seed(c);due,_,reply=c.planner.backend.pending
    now=.05
    if kind=='nan':reply=replace(reply,commands=(float('nan'),)+reply.commands[1:])
    if kind=='unsolved':reply=replace(reply,status='PrimalInfeasible')
    if kind=='wrong_identity':reply=replace(reply,key=(999,*reply.key[1:]))
    if kind=='expired':now=.15
    if kind=='misaligned':now=.075
    c.planner.backend.pending=(due,request,reply);c._decision_now=now
    c.inbox.ingest(Packet('ego',1,now,tuple(state)),now)
    assert c.planner.plan(state,c.route,0.,c.cfg,1.,16.) is None
    assert c.planner.used_request is None
    c.close()


def test_wall_ttl_is_independent_of_logical_freshness():
    c=controller();_,request=seed(c)
    assert c.planner.fresh(request,.05,.05)
    assert not c.planner.fresh(request,.05,.15)
    c.close()


def test_snapshot_is_immutable_and_does_not_follow_owner_changes():
    c=controller();_,request=seed(c)
    original=request.gains;c._gains=c._gains*2;c.stiffness_estimate=.7
    assert request.gains==original and request.stiffness==1.
    assert not hasattr(request,'true_stiffness') and not hasattr(request,'inbox')
    c.close()


def test_logical_closed_loop_keeps_original_robust_admission_and_plant_bounds():
    c=controller();state=np.array([0.,.3,0.,12.,0.,0.]);previous=0.
    # Real conic proposals, fixed service, no inference policy or future truth.
    for i in range(12):
        now=i*.05;c.clock.now=now;c.inbox.ingest(Packet('ego',i,now,tuple(state)),now)
        result=c.decide(now);state=c.apply(now,state,.83)
        assert abs(c.applied.steering-previous)<=.03+1e-12 and abs(c.applied.steering)<=.5
        assert abs(state[1])<1.75
        if result['planned_candidate_selected']:
            assert result['eligible'][result['source']]
            assert result['planner_proposal_age']<.15 and result['planner_proposal_wall_age']<.15
        previous=c.applied.steering
    assert c.planner.accepted>0
    c.close()


def test_actual_process_stall_and_crash_have_nonblocking_fallback():
    c=controller();state,request=seed(c);c.close()
    backend=AsyncPlanner(request.cfg,request.factor,stall_s=.3)
    try:
        assert backend.ready and backend.submit(request,0.)
        assert backend.poll(.05) is None and backend.busy
        assert not backend.submit(replace(request,sequence=2),.05)
        backend.process.terminate();backend.process.join(timeout=2.)
        assert backend.poll(.1) is None and backend.failed
        assert not backend.submit(replace(request,sequence=2),.1)
    finally:backend.close()
