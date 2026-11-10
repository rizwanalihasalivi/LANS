"""Run the repaired single pipeline with an actual spawned inference worker.

This is an engineering diagnostic, not a bypass of the scientific promotion gate.
"""
import argparse,json,math,time
from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path
import numpy as np
from integrations.unified_lans.physics import Config,advance,Command
from integrations.unified_lans.simulation import Network,move_npcs,truth_metrics
from integrations.unified_lans.inference import AsyncPPO,sha
from integrations.unified_lans.run import clean
from tools.unified_campaign.study import setup
from tools.unified_control_v4.control import gain_table,GRID
from tools.unified_control_v4 import mpc
from .control import Controller as NewController
from tools.unified_control_v8.control import Controller as OldController
from .train import selected_kwargs

_MATRICES={}


def warmup():
    start=time.perf_counter()
    for stiffness in [i/20 for i in range(14,27)]:gain_table(16.,stiffness)
    return time.perf_counter()-start


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True);parser.add_argument('--policy',required=True)
    parser.add_argument('--scenario',choices=['following','merge','crossing','curved'],default='following')
    parser.add_argument('--network',choices=['nominal','delayed','loss','reordered','blackout','ego_blackout'],default='nominal')
    parser.add_argument('--fault',choices=['none','stall','crash'],default='none')
    parser.add_argument('--seconds',type=float,default=6.);parser.add_argument('--speed',type=float,default=12.)
    parser.add_argument('--stiffness',type=float,default=.8);parser.add_argument('--delay',type=float,default=0.)
    parser.add_argument('--role',choices=['new','old'],default='new')
    parser.add_argument('--planner-fault',choices=['none','stall','crash'],default='none')
    a=parser.parse_args()
    def Controller(*args,_warm=False,**kwargs):
        if a.role=='old':return OldController(*args,quality_factor=1.1,early_id=True,tracking_only=False,**kwargs)
        extra=selected_kwargs();extra.update(planner_backend='process',planner_wall_stall_s=.3 if a.planner_fault=='stall' and not _warm else 0.)
        return NewController(*args,**extra,**kwargs)
    if not 2<=a.speed<=16 or not .7<=a.stiffness<=1.3 or not math.isfinite(a.seconds) or a.seconds<=0:
        parser.error('use speed 2..16, stiffness .7..1.3 and positive finite duration')
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    case=dict(id=0,stage='real_worker_engineering_diagnostic',scenario=a.scenario,mirror=1,speed=a.speed,
        stiffness=a.stiffness,lateral=.3,heading=.005,phase=9.,amplitude=1.15,
        network=a.network,delay=a.delay,network_seed=7710001)
    _,_,ego,npcs,network=setup(case)
    from tools.unified_campaign.study import StudyRoute
    kind='sine' if a.scenario=='curved' else ('lane_change' if a.scenario=='merge' else 'straight')
    route=StudyRoute(kind,1,9.,1.15);cfg=Config(horizon=2.)
    startup=time.perf_counter()
    c=Controller(route,a.scenario,cfg,a.delay,gains=(.04,0.),mode='hybrid',clock=time.monotonic,
        target_speed=a.speed,deterministic_grid=GRID,penalty=16.,adaptive=True,mpc=True,_warm=True)
    c.expected=set(npcs);warm_seconds=warmup()
    # Compile/initialize both nonlinear planning paths before timing begins.
    warm_ego=ego.copy();warm_npcs={k:v.copy() for k,v in npcs.items()};warm_start=time.monotonic()
    for tick in range(8 if a.role=='new' else 1):
        now=tick*.05;network.emit(now,warm_ego,warm_npcs,c.inbox);c.decide(now)
        warm_ego=c.apply(now,warm_ego,a.stiffness);move_npcs(warm_npcs,.05,route,a.scenario)
        remaining=warm_start+(tick+1)*.05-time.monotonic()
        if remaining>0:time.sleep(remaining)
    warm_responses=c.planner.accepted if a.role=='new' else None
    if a.role=='new':assert warm_responses>0,'Asynchronous proposal admission was not warmed'
    if hasattr(c,'close'):c.close()
    # The warm command is discarded; it is never counted as an applied test input.
    c=Controller(route,a.scenario,cfg,a.delay,gains=(.04,0.),mode='hybrid',clock=time.monotonic,
        target_speed=a.speed,deterministic_grid=GRID,penalty=16.,adaptive=True,mpc=True);c.expected=set(npcs)
    network=Network(7710001,a.network)
    startup_seconds=time.perf_counter()-startup
    root=Path(__file__).resolve().parents[2]
    frozen=json.loads((root/'results/publication-v9/confirmation/protocol.json').read_text())
    files=[root/name for name in frozen['source_hashes']]
    files.extend(Path(__file__).parent/name for name in ['live.py','live_case.py','RUNTIME_PROTOCOL.md'])
    protocol=dict(case=case,config=asdict(cfg),policy_sha256=sha(Path(a.policy)/'policy.zip'),fault=a.fault,role_controller=a.role,planner_fault=a.planner_fault,
        controller_penalty=16.,selected_kwargs=selected_kwargs() if a.role=='new' else None,
        matrix_warmup_s=warm_seconds,total_startup_warmup_s=startup_seconds,
        asynchronous_warm_responses=warm_responses,source_hashes={str(p.relative_to(root)):sha(p) for p in files},
        role='FUNCTIONAL_DIAGNOSTIC_NOT_SCIENTIFIC_PROMOTION',recording='full input-to-issue and complete simulation-cycle timing')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2));rows=[];accepted=0;rejected=0;submitted=0
    try:
        with AsyncPPO(a.policy,.3 if a.fault=='stall' else 0.) as worker:
            start=time.monotonic()
            for i in range(round(a.seconds/.05)):
                now=i*.05
                if a.fault=='crash' and now>=1. and worker.process.is_alive():worker.process.terminate()
                if a.planner_fault=='crash' and now>=1. and c.planner.backend.process.is_alive():c.planner.backend.process.terminate()
                scheduled_release=start+i*.05;actual_release=time.monotonic()
                tick_start=time.perf_counter();network.emit(now,ego,npcs,c.inbox)
                reply=worker.poll()
                if reply is not None:
                    if c.accept(reply,now):accepted+=1
                    else:rejected+=1
                features=c.features(now);packet=c.inbox.latest.get('ego')
                if packet is not None and features is not None:submitted+=int(worker.submit(features,packet.observed_s,now))
                before=ego.copy();previous=c.applied;decision=c.decide(now,worker.failed)
                response_ms=1000*(time.perf_counter()-tick_start)
                scheduled_response_ms=1000*(time.monotonic()-scheduled_release)
                ego=c.apply(now,ego,a.stiffness);move_npcs(npcs,.05,route,a.scenario)
                metrics=truth_metrics(ego,npcs,route,cfg)
                rows.append(dict(**decision,**metrics,tick=i,time_s=now,state_before=before.tolist(),state_after=ego.tolist(),
                    npc_truth={k:v.tolist() for k,v in npcs.items()},applied_steering=c.applied.steering,applied_accel=c.applied.accel,
                    steering_rate=(c.applied.steering-previous.steering)/.05,worker_failed=worker.failed,
                    response_ms=response_ms,cycle_ms=1000*(time.perf_counter()-tick_start),
                    scheduled_release_offset_s=now,actual_release_offset_s=actual_release-start,
                    release_lateness_ms=1000*(actual_release-scheduled_release),
                    scheduled_response_ms=scheduled_response_ms,scheduled_cycle_ms=1000*(time.monotonic()-scheduled_release)))
                if metrics['collision'] or abs(metrics['error'])>2.5:break
                remaining=start+(i+1)*.05-time.monotonic()
                if remaining>0:time.sleep(remaining)
    finally:
        if hasattr(c,'close'):c.close()
    raw=out/'ticks.jsonl';raw.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
    # Actual plant, timing and stale-data behavior are checked from the saved trace.
    state=np.array(rows[0]['state_before']);prev=Command()
    for i,r in enumerate(rows):
        np.testing.assert_allclose(state,r['state_before'],rtol=0,atol=1e-12)
        command=Command(r['applied_steering'],r['applied_accel']);assert abs(command.steering-prev.steering)<=.03+1e-10
        assert abs(command.steering)<=.5 and -6<=command.accel<=2.5
        state=advance(state,command,.05,a.stiffness);np.testing.assert_allclose(state,r['state_after'],rtol=0,atol=1e-12)
        if r['source']=='ppo':assert r['proposal_age']<.15 and r['proposal_wall_age']<.15 and not r['ego_backup']
        if r['ego_backup']:assert r['source'] in ('backup_lqr','hold_brake') and r['issued_accel']==-6.
        prev=command
    result=dict(ticks=len(rows),expected_ticks=round(a.seconds/.05),collisions=sum(r['collision'] for r in rows),
        corridor_exceedances=sum(r['corridor_exceeded'] for r in rows),max_error_m=max(abs(r['error']) for r in rows),
        accepted=accepted,rejected=rejected,submitted=submitted,ppo_ticks=sum(r['source']=='ppo' for r in rows),
        response_misses=sum(r['response_ms']>50 for r in rows),cycle_misses=sum(r['cycle_ms']>50 for r in rows),
        scheduled_response_misses=sum(r['scheduled_response_ms']>50 for r in rows),
        scheduled_cycle_misses=sum(r['scheduled_cycle_ms']>50 for r in rows),
        scheduled_response_max_ms=max(r['scheduled_response_ms'] for r in rows),
        response_max_ms=max(r['response_ms'] for r in rows),response_p95_ms=float(np.percentile([r['response_ms'] for r in rows],95)),
        trace_replay_passed=True,raw_sha256=sha(raw),role=protocol['role'])
    result={k:v.item() if isinstance(v,np.generic) else v for k,v in result.items()}
    (out/'summary.json').write_text(json.dumps(clean(result),indent=2));print(json.dumps(clean(result),indent=2))


if __name__=='__main__':main()
