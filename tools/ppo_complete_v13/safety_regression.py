"""Source-pinned opened-case guardian regression and independent physical replay.

The interrupted v1 is retained. This driver fixes only telemetry serialization
and adds explicit raw/certificate checks; it does not select fresh test cases
or alter the shared safety controller during a sweep.
"""
from pathlib import Path
import argparse,json,math,shutil
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.physics import Command,advance
from integrations.unified_lans.traffic import velocity
from integrations.unified_lans.run import clean
from integrations.unified_lans.simulation import move_npcs,truth_metrics
from tools.unified_control_v9.learning import setup
from tools.ppo_benefit_v10.core import PARAMS
from .safety import Controller
from .test_safety import python_profile

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_OUT=ROOT/'results/ppo-complete-v13/safety-development-v2'


def normalized(value):
    if isinstance(value,np.ndarray):return normalized(value.tolist())
    if isinstance(value,np.generic):return normalized(value.item())
    if isinstance(value,dict):return {k:normalized(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [normalized(v) for v in value]
    return clean(value)


def dump(path,value):
    path.write_text(json.dumps(normalized(value),indent=2,allow_nan=False)+'\n')


def sources():
    paths=[Path(__file__),Path(__file__).with_name('safety.py'),Path(__file__).with_name('test_safety.py'),
        ROOT/'tools/unified_control_v9/learning.py',ROOT/'tools/ppo_benefit_v10/core.py',
        ROOT/'tools/unified_campaign/study.py',ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py']
    paths.extend((ROOT/'integrations/unified_lans').glob('*.py'))
    for v in range(4,9):paths.extend((ROOT/f'tools/unified_control_v{v}').glob('*.py'))
    return sorted(set(paths))


def fixtures():
    jobs=[];inputs={}
    for stage,name in (('v11','ppo-plan-v11'),('v12','ppo-explore-v12')):
        folder=ROOT/f'results/{name}/evaluation';protocol=json.loads((folder/'protocol.json').read_text())
        inputs[str((folder/'protocol.json').relative_to(ROOT))]=sha(folder/'protocol.json')
        for case in protocol['cases']:
            for mode in ('lqr','adaptive'):
                old=folder/f'{case["id"]:03d}-{mode}-0.json'
                inputs[str(old.relative_to(ROOT))]=sha(old)
                meta=json.loads(old.read_text());raw=old.with_suffix('.jsonl')
                assert sha(raw)==meta['raw_sha256']
                inputs[str(raw.relative_to(ROOT))]=sha(raw)
                jobs.append((stage,case,mode,meta,raw))
    assert len(jobs)==288
    return jobs,inputs


def check_clearance_certificate(c,row,now,previous):
    z=c.forecast(now);prior=c.supervisor.state
    risk=c.supervisor.assess(z,c.inbox,c.expected,now,now+c.delay);c.supervisor.state=prior
    center=c.stiffness_estimate if c.adaptive else 1.;width=c.stiffness_uncertainty
    models=(max(.7,center-width),center,min(1.3,center+width)) if c.adaptive else (.7,1.,1.3)
    expected=np.asarray([python_profile(c,z,previous,row['issued_steering'],row['safety_burst_remaining_s'],
        model,risk.vehicles,row['safety_horizon_s']) for model in models])
    actual=c._safety_scores(z,previous,row['issued_steering'],c.cfg.max_accel,
        row['safety_burst_remaining_s'],risk.vehicles,row['safety_horizon_s'])
    np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-9)
    assert expected[:,1].min()>=0
    assert abs(row['safety_margin']-expected[:,1].min())<1e-9
    assert abs(row['costs']['safety_clear']-expected[:,0].mean())<1e-9
    return dict(state=z,models=models,previous_issued=[previous.steering,previous.accel],
        feedback_stiffness=c.feedback_stiffness,vehicles=risk.vehicles,values=expected,
        independent_python_certificate_passed=True)


def run(stage,case,mode,old,old_raw,out):
    params=dict(PARAMS,adaptive=mode!='lqr',mpc=mode!='lqr')
    c,clock,state,npcs,net=setup(case,'lqr' if mode=='lqr' else 'deterministic',Controller,params,grid=mode!='lqr')
    rows=[];maximum=float(state[3]);path=out/f'{stage}-{case["id"]:03d}-{mode}.jsonl'
    with path.open('x') as stream:
        for tick in range(120):
            now=tick*.05;clock.now=now;net.emit(now,state,npcs,c.inbox);before=state.copy();previous_issued=c.issued
            decision=c.decide(now)
            assert abs(c.issued.steering-previous_issued.steering)<=.03+1e-12
            assert abs(c.issued.steering)<=.5 and -6<=c.issued.accel<=2.5
            assert c.pending[-1]==(now+case['delay'],c.issued)
            cert=check_clearance_certificate(c,decision,now,previous_issued) if decision['source']=='safety_clear' else None
            previous_applied=c.applied;state=c.apply(now,state,case['stiffness'])
            move_npcs(npcs,.05,c.route,case['scenario']);truth=truth_metrics(state,npcs,c.route,c.cfg)
            maximum=max(maximum,float(state[3]))
            row=dict(**decision,**truth,time_s=now,tick=tick,state_before=before,state_after=state.copy(),
                npc_truth={name:z.copy() for name,z in npcs.items()},applied_steering=c.applied.steering,
                applied_accel=c.applied.accel,steering_rate=(c.applied.steering-previous_applied.steering)/.05,
                clearance_certificate=cert)
            row=normalized(row);stream.write(json.dumps(row,allow_nan=False)+'\n');rows.append(row)
            if truth['collision'] or abs(truth['error'])>2.5:break
    n=len(rows)
    metrics=dict(stage=stage,case=case,mode=mode,ticks=n,expected_ticks=120,
        failed=n<120 or any(r['collision'] or r['corridor_exceeded'] for r in rows),
        collisions=sum(r['collision'] for r in rows),
        rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(120-n)*6.25)/120),
        heading_rms=float(np.sqrt(np.mean([r['heading_error']**2 for r in rows]))),
        rate_rms=float(np.sqrt(np.mean([r['steering_rate']**2 for r in rows]))),progress_m=float(state[0]),
        minimum_true_clearance=float(min(r['true_clearance'] for r in rows)),max_speed_mps=maximum,
        safety_ticks=sum(r['safety_active'] for r in rows),
        independently_checked_clearance_decisions=sum(r['clearance_certificate'] is not None for r in rows),
        unverified_safety_ticks=sum(r['safety_active'] and not r['eligible'].get(r['source'],False) for r in rows),
        old=old,old_raw=str(old_raw.relative_to(ROOT)),raw_sha256=sha(path))
    dump(path.with_suffix('.json'),metrics)
    return metrics


def replay(meta,out):
    """Independent full plant/FIFO/NPC replay of logged physical outcomes."""
    case=meta['case'];mode=meta['mode'];path=out/f'{meta["stage"]}-{case["id"]:03d}-{mode}.jsonl'
    assert sha(path)==meta['raw_sha256']
    owner,_,state,npcs,_=setup(case,'lqr' if mode=='lqr' else 'deterministic',Controller,
        dict(PARAMS,adaptive=mode!='lqr',mpc=mode!='lqr'),grid=mode!='lqr')
    route=owner.route
    previous_issued=Command();previous_applied=Command();applied=Command();fifo=[];rows=[]
    for tick,line in enumerate(path.open()):
        r=json.loads(line);now=tick*.05;assert r['time_s']==now and r['tick']==tick
        np.testing.assert_allclose(r['state_before'],state,rtol=0,atol=1e-12)
        command=Command(r['issued_steering'],r['issued_accel'])
        assert abs(command.steering-previous_issued.steering)<=.03+1e-12 and abs(command.steering)<=.5 and -6<=command.accel<=2.5
        fifo.append((now+case['delay'],command))
        cert=r['clearance_certificate']
        if cert is not None:
            assert r['source']=='safety_clear' and r['eligible']['safety_clear']
            assert cert['independent_python_certificate_passed']
            np.testing.assert_allclose(cert['previous_issued'],[previous_issued.steering,previous_issued.accel],rtol=0,atol=1e-12)
            center=r['stiffness_estimate'] if mode!='lqr' else 1.;width=r['stiffness_uncertainty']
            models=(max(.7,center-width),center,min(1.3,center+width)) if mode!='lqr' else (.7,1.,1.3)
            np.testing.assert_allclose(cert['models'],models,rtol=0,atol=1e-12)
            feedback=float(np.clip(round(center*20)/20,.7,1.3)) if mode!='lqr' else 1.
            assert abs(cert['feedback_stiffness']-feedback)<1e-12
            # Independent causal current-received-state/FIFO forecast. The new
            # command at the application boundary has zero elapsed duration.
            z=state.copy();cursor=now;forecast_command=applied;until=now+case['delay']
            for due,queued in fifo:
                if due>until+1e-9:break
                if due>cursor:z=advance(z,forecast_command,due-cursor,center);cursor=due
                forecast_command=queued
            if until>cursor:z=advance(z,forecast_command,until-cursor,center)
            np.testing.assert_allclose(cert['state'],z,rtol=0,atol=1e-11)
            vehicles=[]
            for name,other in sorted(npcs.items()):
                predicted=other.copy();predicted[:2]+=velocity(other)*case['delay']
                vehicles.append((name,predicted,owner.cfg.uncertainty_rate*case['delay']))
            assert [v[0] for v in vehicles]==[v[0] for v in cert['vehicles']]
            for actual_vehicle,logged_vehicle in zip(vehicles,cert['vehicles']):
                np.testing.assert_allclose(actual_vehicle[1],logged_vehicle[1],rtol=0,atol=1e-12)
                assert abs(actual_vehicle[2]-logged_vehicle[2])<1e-12
            owner.feedback_stiffness=feedback
            expected=np.asarray([python_profile(owner,z,previous_issued,r['issued_steering'],
                r['safety_burst_remaining_s'],m,vehicles,r['safety_horizon_s']) for m in models])
            np.testing.assert_allclose(cert['values'],expected,rtol=0,atol=1e-9)
            assert expected[:,1].min()>=0 and abs(r['safety_margin']-expected[:,1].min())<1e-9
            assert abs(r['costs']['safety_clear']-expected[:,0].mean())<1e-9
            assert abs(r['safety_predicted_max_speed']-expected[:,4].max())<1e-9
        while fifo and fifo[0][0]<=now+1e-9:_,applied=fifo.pop(0)
        assert applied==Command(r['applied_steering'],r['applied_accel'])
        state=advance(state,applied,.05,case['stiffness']);move_npcs(npcs,.05,route,case['scenario'])
        np.testing.assert_allclose(r['state_after'],state,rtol=0,atol=1e-12)
        for name,z in npcs.items():np.testing.assert_allclose(r['npc_truth'][name],z,rtol=0,atol=1e-12)
        truth=truth_metrics(state,npcs,route,owner.cfg)
        for name,value in truth.items():
            if isinstance(value,(bool,np.bool_)):assert r[name]==bool(value)
            else:assert abs(r[name]-value)<1e-12
        assert abs(r['steering_rate']-(applied.steering-previous_applied.steering)/.05)<1e-12
        previous_issued=command;previous_applied=applied;rows.append(r)
    n=len(rows);assert n==meta['ticks']
    expected=math.sqrt((sum(r['error']**2 for r in rows)+(120-n)*6.25)/120)
    assert abs(expected-meta['rmse_m'])<1e-12
    assert meta['failed']==(n<120 or any(r['collision'] or r['corridor_exceeded'] for r in rows))
    assert meta['collisions']==sum(r['collision'] for r in rows)
    expected_metrics=dict(heading_rms=float(np.sqrt(np.mean([r['heading_error']**2 for r in rows]))),
        rate_rms=float(np.sqrt(np.mean([r['steering_rate']**2 for r in rows]))),progress_m=float(state[0]),
        minimum_true_clearance=min(r['true_clearance'] for r in rows),
        max_speed_mps=max([rows[0]['state_before'][3]]+[r['state_after'][3] for r in rows]),
        safety_ticks=sum(r['safety_active'] for r in rows),
        independently_checked_clearance_decisions=sum(r['clearance_certificate'] is not None for r in rows),
        unverified_safety_ticks=sum(r['safety_active'] and not r['eligible'].get(r['source'],False) for r in rows))
    for name,value in expected_metrics.items():assert abs(meta[name]-value)<1e-12,(name,meta[name],value)
    old_rows=[json.loads(line) for line in (ROOT/meta['old_raw']).open()]
    unchanged=not any(r['safety_active'] for r in rows)
    if unchanged:
        assert len(rows)==len(old_rows)
        keys=('issued_steering','issued_accel','applied_steering','applied_accel')
        np.testing.assert_allclose([[r[k] for k in keys] for r in rows],[[r[k] for k in keys] for r in old_rows],rtol=0,atol=1e-12)
        np.testing.assert_allclose([r['state_after'] for r in rows],[r['state_after'] for r in old_rows],rtol=0,atol=1e-12)
    return dict(ticks=n,unchanged_ordinary_episode=unchanged,certificates=meta['independently_checked_clearance_decisions'])


def assess(records):
    result={}
    for stage in ('v11','v12'):
        for mode in ('lqr','adaptive'):
            rr=[r for r in records if r['stage']==stage and r['mode']==mode]
            result[f'{stage}-{mode}']=dict(episodes=len(rr),failures=sum(r['failed'] for r in rr),
                old_failures=sum(r['old']['failed'] for r in rr),collisions=sum(r['collisions'] for r in rr),
                mean_rmse_m=float(np.mean([r['rmse_m'] for r in rr])),old_mean_rmse_m=float(np.mean([r['old']['rmse_m'] for r in rr])),
                mean_heading_rms=float(np.mean([r['heading_rms'] for r in rr])),mean_rate_rms=float(np.mean([r['rate_rms'] for r in rr])),
                minimum_clearance=min(r['minimum_true_clearance'] for r in rr),max_speed=max(r['max_speed_mps'] for r in rr),
                safety_ticks=sum(r['safety_ticks'] for r in rr),unverified_safety_ticks=sum(r['unverified_safety_ticks'] for r in rr),
                failures_detail=[dict(case=r['case'],rmse_m=r['rmse_m']) for r in rr if r['failed']])
    return result


def verify_only(out):
    protocol=json.loads((out/'protocol.json').read_text());src=protocol['source_hashes'];inputs=protocol['input_hashes']
    for name,digest in src.items():
        assert sha(out/'source'/name)==digest,('Saved generation source changed',name)
        if name!=str(Path(__file__).relative_to(ROOT)):assert sha(ROOT/name)==digest,('Mathematical source changed',name)
    for name,digest in inputs.items():assert sha(ROOT/name)==digest,('Input changed',name)
    records=json.loads((out/'summary.json').read_text());assert len(records)==288
    for r in records:
        path=out/f'{r["stage"]}-{r["case"]["id"]:03d}-{r["mode"]}.json'
        assert json.loads(path.read_text())==r
    assert json.loads((out/'assessment.json').read_text())==assess(records)
    audited=[]
    for r in records:
        audited.append(replay(r,out))
        if len(audited)%24==0:print('REPLAYED OPENED SAFETY',len(audited),'/288',flush=True)
    for name,digest in inputs.items():assert sha(ROOT/name)==digest,('Audit input changed',name)
    report=dict(passed=True,episodes=288,ticks=sum(r['ticks'] for r in audited),
        independently_checked_clearance_decisions=sum(r['certificates'] for r in audited),
        ordinary_episodes_identical_to_old=sum(r['unchanged_ordinary_episode'] for r in audited),
        generation_source_hashes=src,input_hashes=inputs,auditor_source_sha256=sha(__file__),
        summary_sha256=sha(out/'summary.json'),assessment_sha256=sha(out/'assessment.json'),
        limitation='Opened regression evidence; independently replayed plant/FIFO/causal forecast and finite CV/model-corner certificates, not universal safety or fresh-controller qualification.')
    target=out/'verification.json';assert not target.exists(),'Preserve completed audit; use a separate report for a new audit'
    dump(target,report);print(json.dumps(report,indent=2),flush=True)
    print('ALL 288 OPENED SAFETY REGRESSIONS PHYSICALLY REPLAYED',flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=DEFAULT_OUT)
    parser.add_argument('--verify-only',action='store_true');args=parser.parse_args()
    if args.verify_only:verify_only(args.output);return
    out=args.output;out.mkdir(parents=True,exist_ok=False);jobs,inputs=fixtures();src={str(p.relative_to(ROOT)):sha(p) for p in sources()}
    for name in src:
        target=out/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    protocol=dict(scope='288 already-opened development regressions; not untouched confirmation',jobs=len(jobs),
        source_hashes=src,input_hashes=inputs,prior_interrupted_attempt='results/ppo-complete-v13/safety-development-v1',
        prior_error='NumPy ndarray telemetry was not JSON-serialized; no source/controller repair from that partial attempt is inferred.')
    dump(out/'protocol.json',protocol);records=[]
    for stage,case,mode,old,old_raw in jobs:
        records.append(run(stage,case,mode,old,old_raw,out))
        if len(records)%12==0:print('SAFETY OPENED DEVELOPMENT',len(records),'/288',flush=True)
    dump(out/'summary.json',records);assessment=assess(records);dump(out/'assessment.json',assessment)
    for name,digest in src.items():assert sha(ROOT/name)==digest,('Generation source changed',name)
    verify_only(out)


if __name__=='__main__':main()
