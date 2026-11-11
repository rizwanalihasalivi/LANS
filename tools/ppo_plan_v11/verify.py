"""Independent Python physics/rollout audit of every sequence admission."""
import json,math
from pathlib import Path
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.physics import Command,Config,constrain,advance,errors
from integrations.unified_lans.simulation import move_npcs,truth_metrics
from integrations.unified_lans.traffic import Packet,velocity
from tools.unified_control_v4.control import ScheduledLQR
from tools.unified_control_v8.control import Controller as Base
from tools.unified_control_v9.learning import setup
from tools.unified_control_v9.verify import fixture,FIFO,equal
from tools.ppo_benefit_v10.core import PARAMS
from .probe import ROOT,DATA,dump


def plan_python(z,knots,shift,accel,previous,route,feedback,center):
    z=z.copy();baseline=ScheduledLQR(16.);baseline.stiffness=feedback;plan=[];cfg=Config(horizon=2.)
    for i in range(40):
        index=(i+shift)*7/39
        residual=.08*np.interp(index,np.arange(8),knots) if index<=7 else 0.
        u=constrain(Command(baseline(z,route)+residual,accel),Command(previous,accel),cfg)
        plan.append(u.steering);z=advance(z,u,.05,center);previous=u.steering
    return plan


def rollout_python(z,first,plan,accel,previous,route,feedback,stiff,npcs):
    z=z.copy();baseline=ScheduledLQR(16.);baseline.stiffness=feedback;total=0.;heading=0.;rate_energy=0.;margin=1e9;cfg=Config(horizon=2.)
    for i in range(40):
        base=baseline(z,route);u=first if i==0 else base
        if i>0 and plan is not None:u=min(base+.08,max(base-.08,plan[i]))
        if i>0:u=min(previous+.03,max(previous-.03,u))
        u=min(.5,max(-.5,u));z=advance(z,Command(u,accel),.05,stiff)
        e,_=errors(z,route);ey,ep=float(e[0]),float(e[2]);rate=(u-previous)/.05
        total+=.05*(8*ey**2+2*ep**2+.03*u*u+.02*rate*rate);heading+=.05*ep**2;rate_energy+=.05*rate**2
        margin=min(margin,1.75-abs(ey));t=(i+1)*.05
        for other in npcs.values():
            future=np.asarray(other[:2])+velocity(other)*t
            margin=min(margin,float(np.linalg.norm(future-z[:2]))-4.6-.5-.6*t)
        previous=u
    return np.array([total,margin,heading,rate_energy])


def main():
    protocol=json.loads((DATA/'protocol.json').read_text())
    for name,digest in protocol['source_hashes'].items():
        assert sha(DATA/'source'/name)==digest and sha(ROOT/name)==digest
    summary=json.loads((DATA/'summary.json').read_text());assert len(summary)==192
    keys=set();ticks=0;checked_plans=0
    for meta in summary:
        case=meta['case'];mode=meta['mode'];key=(case['id'],mode);assert key not in keys;keys.add(key)
        assert case==protocol['cases'][case['id']]
        path=DATA/f'{case["id"]:03d}-{mode}.jsonl';assert sha(path)==meta['raw_sha256']
        assert meta['protocol_sha256']==sha(DATA/'protocol.json');equal(json.loads(path.with_suffix('.json').read_text()),meta)
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        route,state,npcs=fixture(case);fifo=FIFO(case['delay']);previous=Command();issued=Command();prior_label=None
        c,clock,*_=setup(case,'lqr' if mode=='lqr' else 'deterministic',Base,
            dict(PARAMS,adaptive=mode!='lqr',mpc=mode!='lqr'),grid=mode!='lqr')
        for i,row in enumerate(rows):
            now=i*.05;assert row['tick']==i and row['time_s']==now;clock.now=now
            np.testing.assert_allclose(row['state_before'],state,rtol=0,atol=1e-12)
            c.inbox.ingest(Packet('ego',i,now,tuple(state)),now)
            for name,other in npcs.items():c.inbox.ingest(Packet(name,i,now,tuple(other)),now)
            c.update_model();equal(row['stiffness_estimate'],c.stiffness_estimate);equal(row['stiffness_uncertainty'],c.stiffness_uncertainty)
            actual=Command(row['issued_steering'],row['issued_accel'])
            if row.get('sequence_plan_selected'):
                assert row['source']=='ppo_plan' and case['delay']==0. and prior_label is not None
                assert 0<=row['sequence_age']<.15 and 0<=row['sequence_wall_age']<.15 and row['risk']!='DANGER' and not row['ego_backup']
                equal(row['sequence_knots'],prior_label);assert row['sequence_shift']==0
                alternative=c.decide(now);equal(alternative['costs'][alternative['source']],row['sequence_reference_cost'])
                equal(alternative['issued_accel'],actual.accel)
                feedback=c.feedback_stiffness;center=c.stiffness_estimate;width=c.stiffness_uncertainty
                plan=plan_python(state,row['sequence_knots'],0,actual.accel,issued.steering,route,feedback,center)
                equal(plan[0],actual.steering)
                baseline=ScheduledLQR(16.);baseline.stiffness=feedback
                base=constrain(Command(baseline(state,route),actual.accel),issued,Config(horizon=2.))
                models=[max(.7,center-width),center,min(1.3,center+width)]
                candidates=np.asarray([rollout_python(state,plan[0],plan,actual.accel,issued.steering,route,feedback,s,npcs) for s in models])
                references=np.asarray([rollout_python(state,base.steering,None,actual.accel,issued.steering,route,feedback,s,npcs) for s in models])
                assert np.all(candidates[:,0]<references[:,0]-1e-9+1e-12)
                assert np.all(candidates[:,2]<=1.21*references[:,2]+2e-6+1e-12)
                assert np.all(candidates[:,3]<=1.21*references[:,3]+1e-5+1e-12)
                assert candidates[:,1].min()>=-1e-12
                equal(row['sequence_cost'],float(candidates[:,0].mean()));equal(row['sequence_margin'],float(candidates[:,1].min()))
                assert row['sequence_cost']<row['sequence_reference_cost']-1e-8
                c.pending.pop();checked_plans+=1
            elif mode=='sequence_teacher' and case['delay']==.1:
                assert not row['sequence_plan_selected']
            applied=Command(row['applied_steering'],row['applied_accel']);fifo.step(now,actual,applied)
            equal(row['steering_rate'],(applied.steering-previous.steering)/.05)
            state=advance(state,applied,.05,case['stiffness']);np.testing.assert_allclose(row['state_after'],state,rtol=0,atol=1e-12)
            move_npcs(npcs,.05,route,case['scenario'])
            for name,other in npcs.items():np.testing.assert_allclose(row['npc_truth'][name],other,rtol=0,atol=1e-12)
            truth=truth_metrics(state,npcs,route,Config(horizon=2.))
            for name,value in truth.items():equal(row[name],value)
            c.pending.append((now+case['delay'],actual));c.issued=actual
            while c.pending and c.pending[0][0]<=now+1e-9:_,c.applied=c.pending.pop(0)
            assert c.applied==applied
            c.history.append((now,now+.05,applied));c.history=[h for h in c.history if h[1]>=now-c.backup_limit_s-c.cfg.ego_ttl]
            c.supervisor.state=row['risk'];previous=applied;issued=actual;prior_label=row['label']
        n=len(rows);assert n==meta['ticks'] and meta['expected_ticks']==120
        metrics=dict(rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(120-n)*6.25)/120),
            heading_rms=float(np.sqrt(np.mean([r['heading_error']**2 for r in rows]))),
            rate_rms=float(np.sqrt(np.mean([r['steering_rate']**2 for r in rows]))),progress_m=float(state[0]),
            failed=n<120 or any(r['collision'] or r['corridor_exceeded'] for r in rows),collisions=sum(r['collision'] for r in rows),
            plan_ticks=sum(r.get('sequence_plan_selected',False) for r in rows))
        for name,value in metrics.items():equal(meta[name],value)
        ticks+=n
    assert keys=={(c['id'],mode) for c in protocol['cases'] for mode in protocol['modes']}
    assessment=json.loads((DATA/'assessment.json').read_text());metrics={}
    for mode in protocol['modes']:
        rr=[r for r in summary if r['mode']==mode]
        metrics[mode]={name:float(np.mean([r[name] for r in rr])) for name in ('rmse_m','heading_rms','rate_rms','progress_m')}
    equal(assessment['metrics'],metrics)
    equal(assessment['gain_vs_adaptive_percent'],100*(1-metrics['sequence_teacher']['rmse_m']/metrics['adaptive']['rmse_m']))
    equal(assessment['gain_vs_lqr_percent'],100*(1-metrics['sequence_teacher']['rmse_m']/metrics['lqr']['rmse_m']))
    result=dict(episodes=192,ticks=ticks,selected_proposals_independently_replayed=checked_plans,source_sha256=sha(__file__),
        protocol_sha256=sha(DATA/'protocol.json'),assessment_sha256=sha(DATA/'assessment.json'),passed=True,
        scope='Raw physics, observer, FIFO, every admitted robust plan and analytical counterfactual; no PPO training or general ceiling claim.')
    dump(DATA/'verification.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':main()
