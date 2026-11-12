import math
import numpy as np
import pytest
from integrations.unified_lans.physics import Config,Command,Route,advance,errors
from integrations.unified_lans.traffic import Packet
from tools.unified_control_v8.control import Controller as Base
from tools.unified_control_v4.kernels import rollout
from tools.ppo_complete_v13.plans import PlanMixin,CorrectionProposal,anchored_rollout


class Clock:
    def __init__(self):self.now=0.
    def __call__(self):return self.now


class Controller(PlanMixin,Base):pass


def controller(delay=0.,**kwargs):
    clock=Clock();c=Controller(Route('straight'),cfg=Config(horizon=2.),delay=delay,clock=clock,
        mode='deterministic',target_speed=8.,penalty=16.,adaptive=True,mpc=False,**kwargs)
    state=np.array([0.,.05,.005,8.,0.,0.]);c.inbox.ingest(Packet('ego',0,0.,tuple(state)),0.)
    return c,clock,state


@pytest.mark.parametrize('delay',[0.,.05,.1])
def test_neutral_preserves_exact_reference_and_has_no_penalty(delay):
    c,clock,_=controller(delay);ctx=c.prepare(0.);baseline=ctx.row
    score=c.score_candidate(ctx,np.zeros(8))
    assert score.neutral and score.values==ctx.reference_values and not any(score.violations.values())
    row=c.finish(ctx,CorrectionProposal(1,0.,0.,0.,tuple(np.zeros(8))))
    assert row['source']==baseline['source'] and row['sequence_reason']=='neutral'
    assert not row['sequence_plan_selected'] and c.issued==Command(baseline['issued_steering'],baseline['issued_accel'])
    assert c.pending[-1][1]==c.issued


def python_rollout(c,z,coeffs,first,residual,plan,planned,k,scale=.5):
    z=z.copy();previous=0.;cost=0.;margin=1e9;heading=0.;rate=0.;commands=[]
    for i in range(40):
        base=c.baseline_fn(z,c.route);delta=.02*scale*np.interp(i*7/39,np.arange(8),coeffs)
        if i==0:
            raw=first if delta==0 else base+np.clip(residual+delta,-.08,.08)
            u=raw if delta==0 else np.clip(raw,previous-.03,previous+.03)
        else:
            anchor=np.clip(plan[i],base-.08,base+.08) if planned else base
            u=np.clip(np.clip(anchor+delta,base-.08,base+.08),previous-.03,previous+.03)
        u=float(np.clip(u,-.5,.5));z=advance(z,Command(u,.1),.05,k);e,_=errors(z,c.route)
        slew=(u-previous)/.05;cost+=.05*(8*e[0]**2+2*e[2]**2+.03*u*u+.02*slew*slew)
        heading+=.05*e[2]**2;rate+=.05*slew*slew;margin=min(margin,1.75-abs(e[0]));commands.append(u);previous=u
    return np.array([cost,margin,heading,rate]),np.array(commands)


@pytest.mark.parametrize('planned',[False,True])
def test_anchor_feedback_matches_independent_python_and_original_zero(planned):
    c,_,z=controller();coeffs=np.linspace(-.15,.1,8);plan=.01*np.sin(np.linspace(0,math.pi,40));first=-.01;residual=first-c.baseline_fn(z,c.route)
    for model in (.7,1.,1.3):
        args=(.1,0.,.05,40,model,c._gains,c._route,np.empty((0,7)),2.3,.5,.6,.5,.6,.08,1.)
        v,u,_=anchored_rollout(z,coeffs,.5,.02,first,residual,plan,planned,*args)
        expected,commands=python_rollout(c,z,coeffs,first,residual,plan,planned,model)
        np.testing.assert_allclose(v,expected,rtol=0,atol=1e-11);np.testing.assert_allclose(u,commands,rtol=0,atol=1e-12)
        neutral,_,_=anchored_rollout(z,np.zeros(8),1.,.02,first,residual,plan,planned,*args)
        original=rollout(z,first,.1,0.,.05,2.,model,c._gains,c._route,np.empty((0,7)),2.3,.5,.6,.5,.6,1.,plan if planned else None)
        np.testing.assert_allclose(neutral,original,rtol=0,atol=1e-12)


def test_strict_real_age_and_no_timestamp_refresh_at_100ms():
    c,clock,_=controller(.1);ctx=c.prepare(0.);clock.now=.050000001
    p=CorrectionProposal(1,0.,0.,0.,tuple(np.zeros(8)));row=c.finish(ctx,p)
    assert not row['sequence_plan_selected'] and row['sequence_reason']=='invalid_or_expired'
    c,clock,_=controller(.1);ctx=c.prepare(0.);clock.now=.01
    row=c.finish(ctx,CorrectionProposal(1,0.,0.,.01,tuple(np.zeros(8))))
    assert row['sequence_reason']=='invalid_or_expired'


def test_deadline_ownership_context_immutability_and_postfinish_rollback():
    c,clock,_=controller();ctx=c.prepare(0.);old=ctx.row
    copy=ctx.row;copy['costs']['lqr']=-99.;assert ctx.row['costs']['lqr']!=-99.
    with pytest.raises(RuntimeError):c.prepare(0.)
    clock.now=.06;row=c.finish(ctx,CorrectionProposal(1,0.,0.,0.,tuple(np.ones(8))),deadline_wall=.05)
    assert row['sequence_reason']=='deadline_fallback' and c.issued==Command(old['issued_steering'],old['issued_accel'])
    restored=c.restore_baseline(ctx,'final_deadline_fallback',row);assert restored['source']==old['source']
    with pytest.raises(ValueError):c.finish(ctx)
    c.apply(0.,np.array([0.,.05,.005,8.,0.,0.]))
    with pytest.raises(RuntimeError):c.restore_baseline(ctx,'too_late')


def test_only_original_guards_can_be_selected_and_anchor_toggle_never_weakens_them():
    c,_,_=controller(anchor_quality_factor=None);ctx=c.prepare(0.)
    for action in np.random.default_rng(42).uniform(-1,1,(24,8)):
        score=c.score_candidate(ctx,action)
        assert all(np.isfinite(list(score.violations.values())))
        if score.admissible:
            values=np.asarray(score.values);ref=np.asarray(ctx.lqr_values)
            assert np.all(values[:,0]<ref[:,0]-1e-9)
            assert np.all(values[:,2]<=1.21*ref[:,2]+2e-6) and np.all(values[:,3]<=1.21*ref[:,3]+1e-5)
            assert np.min(values[:,1])>=0
    c.finish(ctx)


def test_malformed_coefficients_cannot_replace_baseline():
    for coefficients in ((float('nan'),)*8,(2.,)*8,(0.,)*7):
        c,_,_=controller();ctx=c.prepare(0.);old=c.issued
        row=c.finish(ctx,CorrectionProposal(1,0.,0.,0.,coefficients))
        assert row['sequence_reason']=='invalid_or_expired' and c.issued==old


def test_same_tick_cannot_accumulate_multiple_slew_increments():
    c,clock,state=controller();ctx=c.prepare(0.);c.finish(ctx)
    for now in (0.,.001,.049):
        with pytest.raises(ValueError):c.prepare(now)
    state=c.apply(0.,state);clock.now=.05
    c.inbox.ingest(Packet('ego',1,.05,tuple(state)),.05)
    c.finish(c.prepare(.05))


@pytest.mark.parametrize('finished',[False,True])
def test_delayed_queue_does_not_allow_postphysical_finalization(finished):
    c,_,state=controller(.1);ctx=c.prepare(0.)
    if finished:c.finish(ctx)
    # At100msdelay the queued command is STILL present after this physical
    # step. It has nevertheless left the owner's pre-application boundary.
    c.apply(0.,state);assert len(c.pending)==1
    with pytest.raises(RuntimeError):
        if finished:c.restore_baseline(ctx,'too_late')
        else:c.finish(ctx)


def test_expired_raw_score_stops_before_remaining_backtracking(monkeypatch):
    c,clock,_=controller();ctx=c.prepare(0.);baseline=c.issued;original=c.score_candidate;calls=[]
    def slow_score(*args,**kwargs):
        calls.append(1);result=original(*args,**kwargs);clock.now=.06;return result
    monkeypatch.setattr(c,'score_candidate',slow_score)
    row=c.finish(ctx,CorrectionProposal(1,0.,0.,0.,tuple(np.ones(8))),deadline_wall=.05)
    assert len(calls)==1 and row['sequence_reason']=='deadline_fallback'
    assert c.issued==baseline and not row['sequence_plan_selected']


@pytest.mark.parametrize('delay',[0.,.05,.1])
def test_zero_action_full_trajectory_and_winning_cost_match_shared_owner(delay):
    from tools.ppo_complete_v13.safety import Controller as Safe
    from tools.unified_control_v9.learning import setup
    from tools.ppo_benefit_v10.core import PARAMS
    from integrations.unified_lans.simulation import move_npcs
    class Anchored(PlanMixin,Safe):pass
    case=dict(scenario='curved',mirror=1,speed=12.,delay=delay,stiffness=.85,
        lateral=.25,heading=.012,phase=1.,amplitude=1.,network='nominal',network_seed=913)
    a,aclock,az,anpcs,anet=setup(case,'deterministic',Anchored,PARAMS,grid=True)
    b,bclock,bz,bnpcs,bnet=setup(case,'deterministic',Safe,PARAMS,grid=True)
    planned=0;eligible=0
    for tick in range(24):
        now=tick*.05;aclock.now=bclock.now=now
        anet.emit(now,az,anpcs,a.inbox);bnet.emit(now,bz,bnpcs,b.inbox)
        ctx=a.prepare(now);base=b.decide(now)
        if ctx.eligible:
            eligible+=1
            assert np.mean(np.asarray(ctx.reference_values)[:,0])==pytest.approx(base['costs'][base['source']],abs=1e-11)
        planned+=ctx.planned
        result=a.finish(ctx,CorrectionProposal(tick+1,now,now,now,(0.,)*8))
        assert result['source']==base['source'] and a.issued==b.issued
        assert a.pending==b.pending and not result['sequence_plan_selected']
        az=a.apply(now,az,case['stiffness']);bz=b.apply(now,bz,case['stiffness'])
        np.testing.assert_array_equal(az,bz)
        move_npcs(anpcs,.05,a.route,case['scenario']);move_npcs(bnpcs,.05,b.route,case['scenario'])
    assert eligible>0


def test_stored_winning_conic_tail_has_exact_analytical_reference_cost():
    from tools.ppo_complete_v13.safety import Controller as Safe
    from tools.unified_control_v9.learning import setup
    from tools.ppo_benefit_v10.core import PARAMS
    from integrations.unified_lans.simulation import move_npcs
    class Anchored(PlanMixin,Safe):pass
    # Opened v12 fixture1 is a regression, not an untouched evaluation case.
    case=dict(scenario='following',mirror=1,speed=8.,delay=0.,stiffness=.7659204055821786,
        lateral=.2809351532044119,heading=.016995878247404072,phase=17.030277146097625,
        amplitude=1.2210664075294264,npc_x_shift=3.0838228946255093,npc_speed_scale=.7968846065724775,
        network='nominal',network_seed=1293810016)
    c,clock,state,npcs,net=setup(case,'deterministic',Anchored,PARAMS,grid=True);seen=False
    for tick in range(28):
        now=tick*.05;clock.now=now;net.emit(now,state,npcs,c.inbox);ctx=c.prepare(now)
        if ctx.planned and ctx.eligible:
            seen=True;score=c.score_candidate(ctx,np.zeros(8))
            assert score.cost==pytest.approx(ctx.row['costs'][ctx.row['source']],abs=1e-11)
            for j,model in enumerate(ctx.models):
                values,_,_=anchored_rollout(np.asarray(ctx.state),np.zeros(8),1.,c.correction_amplitude,
                    ctx.reference_first,ctx.reference_residual,np.asarray(ctx.reference_plan),True,
                    ctx.acceleration,ctx.previous.steering,.05,40,model,c._gains,c._route,
                    np.asarray([(*s,u) for _,s,u in ctx.vehicles]).reshape(-1,7),2.3,.5,.6,.5,.6,.08,c.feedback_stiffness)
                np.testing.assert_allclose(values,np.asarray(ctx.reference_values)[j],rtol=0,atol=1e-12)
        c.finish(ctx);state=c.apply(now,state,case['stiffness']);move_npcs(npcs,.05,c.route,case['scenario'])
    assert seen
