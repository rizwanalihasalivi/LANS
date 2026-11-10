"""Actual process workers with fixed releases and complete inline-log timing."""
from contextlib import ExitStack
from pathlib import Path
import argparse,json,math,time,resource
import numpy as np
from integrations.unified_lans.inference import AsyncPPO
from integrations.unified_lans.physics import Command
from integrations.unified_lans.simulation import Network,move_npcs,truth_metrics
from integrations.unified_lans.run import clean
from tools.unified_control_v9.learning import setup,close_controller
from tools.unified_control_v4.control import gain_table
from tools.unified_control_v8.control import Controller as V8
from .traffic_guard import Controller
from .timing import Schedule,control_affinity
from .calibrate import write,sha


def execute(job,out,arm):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    c=job['case'];new=job['role']=='new';cls=Controller if new else V8
    params=dict(quality_factor=1.1,early_id=True,tracking_only=False)
    if new:
        params.update(arm);params.pop('sync');params.update(planner_backend='process',planner_wall_stall_s=.3 if job['planner_fault']=='stall' else 0.)
    startup=time.perf_counter()
    for s in [i/20 for i in range(14,27)]:gain_table(16.,s)
    # Real owner admission, not merely a subprocess import, is warmed. Startup
    # packets/commands are discarded before fresh initial conditions are built.
    warm_params=dict(params)
    if new:warm_params['planner_wall_stall_s']=0.
    warm_case=dict(c,scenario='following',mirror=1,lateral=0.,heading=0.,stiffness=1.,phase=0.,amplitude=1.,
        network='nominal',delay=0.,npc_x_shift=0.,npc_speed_scale=1.)
    warm,clock,ego,npcs,net=setup(warm_case,'hybrid',cls,warm_params)
    warm.expected=set();npcs={}
    warm.clock=time.monotonic
    try:
        schedule=Schedule()
        for i in range(8):
            schedule.wait(i);now=i*.05;clock.now=now;net.emit(now,ego,npcs,warm.inbox);warm.decide(now)
            ego=warm.apply(now,ego,warm_case['stiffness'])
        # Compile the optional planned-array cost overload explicitly. A solver
        # can legitimately reject all startup plans; this is not worker failure.
        warm._plan=np.zeros(round(warm.cfg.horizon/warm.cfg.dt));warm._plan_residual=0.
        warm.cost(ego.copy(),Command(0.,0.),0.,0.,(),warm.cfg.horizon)
        warm._plan=None;warm._plan_residual=None
        warm_admitted=getattr(warm.planner,'accepted',None);warm_rejected=getattr(warm.planner,'rejected',None)
        if new:assert warm.planner.backend.ready and not warm.planner.backend.failed,'Startup solver process failed'
    finally:close_controller(warm)
    with ExitStack() as cleanup:
        pipe,clock,ego,npcs,net=setup(c,'hybrid',cls,params);pipe.clock=time.monotonic;cleanup.callback(close_controller,pipe)
        worker=AsyncPPO(job['policy'],.3 if job['ppo_fault']=='stall' else 0.);cleanup.callback(worker.close)
        planner_process=getattr(getattr(pipe.planner,'backend',None),'process',None)
        affinity=cleanup.enter_context(control_affinity([worker.process,planner_process]))
        write(out/'protocol.json',dict(job=job,arm=arm,startup_s=time.perf_counter()-startup,affinity=affinity,
            warm_fixture='zero-error nominal empty-road startup; optional planned-array cost compiled; scored case unchanged',
            startup_plans_admitted=warm_admitted,startup_plans_rejected=warm_rejected,
            role='finite actual-worker engineering diagnostic; not WCET',inline_trace=True,fixed_release=True))
        rows=[];timing=[];accepted=rejected=submitted=0;schedule=Schedule();faults=[]
        with (out/'ticks.jsonl').open('x') as trace:
            for i in range(120):
                schedule.wait(i);tick_start=time.perf_counter();actual_release=time.monotonic();now=i*.05;clock.now=now
                cpu_start=time.process_time();usage_before=resource.getrusage(resource.RUSAGE_SELF)
                if now>=1.:
                    for name,condition,process in [('ppo',job['ppo_fault']=='crash',worker.process),('planner',job['planner_fault']=='crash',planner_process)]:
                        if condition and name not in faults and process is not None:
                            process.terminate();faults.append(name)
                net.emit(now,ego,npcs,pipe.inbox);reply=worker.poll()
                if reply is not None:
                    if pipe.accept(reply,now):accepted+=1
                    else:rejected+=1
                features=pipe.features(now);packet=pipe.inbox.latest.get('ego')
                if features is not None and packet is not None:submitted+=int(worker.submit(features,packet.observed_s,now))
                before=ego.copy();previous=pipe.applied;decision=pipe.decide(now,worker.failed)
                response_ms=1000*(time.perf_counter()-tick_start);response_cpu_ms=1000*(time.process_time()-cpu_start);scheduled_response_ms=1000*(time.monotonic()-schedule.target(i))
                plant_start=time.perf_counter()
                ego=pipe.apply(now,ego,c['stiffness']);move_npcs(npcs,.05,pipe.route,c['scenario'])
                metrics=truth_metrics(ego,npcs,pipe.route,pipe.cfg)
                plant_wall_ms=1000*(time.perf_counter()-plant_start)
                row=dict(**decision,**metrics,tick=i,time_s=now,state_before=before.tolist(),state_after=ego.tolist(),
                    npc_truth={k:v.tolist() for k,v in npcs.items()},applied_steering=pipe.applied.steering,applied_accel=pipe.applied.accel,
                    steering_rate=(pipe.applied.steering-previous.steering)/.05,worker_failed=worker.failed,
                    response_ms=response_ms,scheduled_response_ms=scheduled_response_ms,
                    response_cpu_ms=response_cpu_ms,plant_wall_ms=plant_wall_ms,
                    release_lateness_ms=1000*(actual_release-schedule.target(i)))
                trace_start=time.perf_counter()
                trace.write(json.dumps(clean(row),allow_nan=False)+'\n');trace.flush();rows.append(row)
                trace_write_ms=1000*(time.perf_counter()-trace_start)
                usage_after=resource.getrusage(resource.RUSAGE_SELF);owner_cpu_ms=1000*(time.process_time()-cpu_start)
                timing.append(dict(tick=i,complete_cycle_ms=1000*(time.perf_counter()-tick_start),
                    scheduled_cycle_ms=1000*(time.monotonic()-schedule.target(i)),owner_cpu_ms=owner_cpu_ms,
                    response_cpu_ms=response_cpu_ms,plant_wall_ms=plant_wall_ms,trace_write_ms=trace_write_ms,
                    voluntary_context_switches=usage_after.ru_nvcsw-usage_before.ru_nvcsw,
                    involuntary_context_switches=usage_after.ru_nivcsw-usage_before.ru_nivcsw))
                if metrics['collision'] or abs(metrics['error'])>2.5:break
        (out/'timing.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in timing))
        s=dict(case=c,mode='hybrid',actor=job['actor'],role=job['role'],stage='actual_worker',ticks=len(rows),expected_ticks=120,
            failed=len(rows)<120 or any(r['collision'] or r['corridor_exceeded'] for r in rows),
            rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(120-len(rows))*6.25)/120),
            heading_rms=math.sqrt(np.mean([r['heading_error']**2 for r in rows])),rate_rms=math.sqrt(np.mean([r['steering_rate']**2 for r in rows])),
            progress_m=float(ego[0]),min_clearance=min(r['true_clearance'] for r in rows),collisions=sum(r['collision'] for r in rows),
            ppo_ticks=sum(r['source']=='ppo' for r in rows),recourse_ticks=sum(r['source']=='recovery_lqr' for r in rows),
            uncertified_recourse_ticks=sum(bool(r.get('recovery') and r['recovery']['mode']=='uncertified_emergency_improvement') for r in rows),
            accepted=accepted,rejected=rejected,submitted=submitted,ppo_fault=job['ppo_fault'],planner_fault=job['planner_fault'],
            response_misses=sum(r['response_ms']>50 for r in rows),scheduled_response_misses=sum(r['scheduled_response_ms']>50 for r in rows),
            cycle_misses=sum(r['complete_cycle_ms']>50 for r in timing),scheduled_cycle_misses=sum(r['scheduled_cycle_ms']>50 for r in timing),
            response_max_ms=max(r['response_ms'] for r in rows),cycle_max_ms=max(r['complete_cycle_ms'] for r in timing),
            scheduled_cycle_max_ms=max(r['scheduled_cycle_ms'] for r in timing),
            raw_sha256=sha(out/'ticks.jsonl'),timing_sha256=sha(out/'timing.jsonl'),
            fault_checks_passed=all(r['source']!='ppo' for r in rows if r['time_s']>=1.5) if job['ppo_fault']!='none' else True)
        if job['planner_fault']!='none':s['fault_checks_passed']&=all(not r['planned_candidate_selected'] for r in rows if r['time_s']>=1.5)
        write(out/'summary.json',s);return s


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    spec=json.loads(a.job.read_text());print(json.dumps(execute(spec['job'],a.output,spec['arm'])),flush=True)


if __name__=='__main__':main()
