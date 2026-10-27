"""Wall-paced validation of retrained causal-query-v2 students and deadline fallback.

Uses real spawned CPU inference, IPC, observation timestamps and the frozen Gate.
Does not implement native Webots, hard-real-time scheduling or physical actuation.
"""
import argparse
import csv
import gzip
import gc
import hashlib
import json
import multiprocessing as mp
import os
import platform
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'integrations/webots/research/revision8'))
import numpy as np
from student import load
from kernels import lqr, path_values, initial_executor
from realtime_kernels import measure_fast as measure
from teacher import features
from plant import advance
from comparison import configure_lqr
from core import GAINS
from gating import Gate

CASES = dict(nominal=0., delay20=.020, delay60=.060, delay100=.100,
             cpu_stress=0., worker_crash=0.)


def worker_main(connection, folder, delay, cpu):
    try:
        os.sched_setaffinity(0, {cpu})
        import torch
        torch.set_num_threads(1); torch.set_num_interop_threads(1)
        started = time.perf_counter_ns()
        model = load(Path(folder))
        model.predict(np.zeros(20, dtype=np.float32))
        connection.send(('ready', time.perf_counter_ns()-started))
        while True:
            request = connection.recv()
            if request is None:
                return
            seq, observed, observation = request
            entered = time.perf_counter_ns()
            action, _ = model.predict(observation, deterministic=True)
            inferred = time.perf_counter_ns()
            if delay:
                time.sleep(delay)  # Real injected worker unavailability, not inference.
            connection.send(('output', dict(seq=seq, observed_ns=observed,
                entered_ns=entered, inferred_ns=inferred, sent_ns=time.perf_counter_ns(),
                residual=.08*float(np.clip(action[0], -1., 1.)),
                observation_json=json.dumps(observation.tolist()))))
    except (EOFError, BrokenPipeError):
        pass
    except Exception as error:
        try:
            connection.send(('error', repr(error)))
        except (EOFError, BrokenPipeError):
            pass
    finally:
        connection.close()


def burn(stop, cpu):
    os.sched_setaffinity(0, {cpu})
    value = 1
    while not stop.is_set():
        for _ in range(10000):
            value = (value * 1664525 + 1013904223) & 0xffffffff


def causal_features(state, estimate, speed, path, gate, packet, busy, pending_ns,
                    last_command, now_ns):
    # Preserve 20 channels; never reveal future output or completion time.
    executor = initial_executor()
    executor[0] = gate.weight; executor[1] = gate.good
    if packet is not None:
        executor[3] = packet['seq']
        executor[4] = -(now_ns-packet['observed_ns'])/1e9
        executor[5] = packet['residual']
    if busy:
        executor[7] = 1
        executor[8] = -(now_ns-pending_ns)/1e9
        executor[9] = 0.  # Unknown pending proposal; explicit neutral placeholder.
        executor[6] = 0.  # Unknown time-to-ready, never fabricated forecast.
    executor[11] = last_command
    return features(state, estimate, speed, path, executor, 0, 0)


from causal_student import load_causal as load, runtime_features as causal_features


def final_command(gate, result, packet, apply_ns, baseline, deadline_ns=None):
    if deadline_ns is not None and apply_ns > deadline_ns:
        return gate.reset(baseline, 'deadline')
    # Recheck immediately before software application; gate computation takes time.
    if packet is not None and (apply_ns-packet['observed_ns'])/1e9 >= .05:
        return gate.reset(baseline, 'age_at_apply')
    return result


def stats(values):
    if not values:
        return None
    values = np.asarray(values, dtype=float)
    return dict(n=len(values), median_ms=float(np.median(values)),
        p95_ms=float(np.quantile(values, .95)), p99_ms=float(np.quantile(values, .99)),
        max_ms=float(np.max(values)))


def shutdown(process):
    process.join(timeout=.2)
    if process.is_alive():
        process.terminate(); process.join(timeout=2)
    if process.is_alive():
        process.kill(); process.join(timeout=2)


def episode(ctx, seed, case, seconds, out, cpus, model_root, noise_base):
    folder = model_root/str(seed)
    parent, child = ctx.Pipe()
    process = ctx.Process(target=worker_main, args=(child, str(folder), CASES[case], cpus[-1]))
    started = time.perf_counter_ns(); process.start(); child.close()
    if not parent.poll(45):
        shutdown(process); raise RuntimeError('worker startup timeout')
    status, warmup_ns = parent.recv()
    if status != 'ready':
        shutdown(process); raise RuntimeError(warmup_ns)
    startup_ms = (time.perf_counter_ns()-started)/1e6
    stop = ctx.Event(); stress=[]
    if case == 'cpu_stress':
        for cpu in set(cpus):
            p=ctx.Process(target=burn,args=(stop,cpu));p.start();stress.append(p)
        time.sleep(.2)
    configure_lqr()
    gains=np.array([GAINS[v] for v in (15,20,25)])
    from data import G
    path=tuple(float(v) for v in G['paths']['dlc220'])
    y,h,_=path_values(0.,path)
    initial=np.array([0.,y+.15,h+.01,0.,0.,0.]); state=initial.copy()
    estimate=np.zeros(4);cov=np.eye(4)*.01;previous=np.zeros(4)
    gate=Gate({'horizon_steps':20,'relative_margin':.01})
    steps=int(round(seconds/.01));rng=np.random.default_rng(noise_base+seed)
    noises=rng.normal(size=(steps,4))*np.array([.03,np.deg2rad(.17),.01,.10])
    # Compile all controller/plant paths before the wall-paced experiment.
    est,c,prev,v,k=measure(state,20.,path,noises[0],0,estimate,cov,previous,True,1.)
    baseline,gain=lqr(est,v,k,gains)
    gate.choose(.01,baseline,(1,0.,-.04),est,state[5],v,k,gain,'residual')
    advance(state,baseline,20.,1.,1.)
    causal_features(state,est,20.,path,gate,None,False,0,0.,time.perf_counter_ns())
    # Exercise returned-array layouts, feature scalar types and both initial/updated
    # observer paths. Smoke evidence exposed cold Numba signatures on tick 0/1.
    warm_state=state.copy();we=estimate.copy();wc=cov.copy();wp=previous.copy()
    for i in range(40):
        we,wc,wp,wv,wk=measure(warm_state,20.,path,noises[i % steps],0,we,wc,wp,i==0,1.)
        wb,wg=lqr(we,wv,wk,gains)
        causal_features(warm_state,we,max(5.,20.+noises[i % steps,3]),path,gate,
            None,False,0,0.,time.perf_counter_ns())
        gate.choose(.01,wb,(1,0.,-.04),we,warm_state[5],wv,wk,wg,'residual')
        warm_state=advance(warm_state,wb,20.,1.,1.)
    gate=Gate({'horizon_steps':20,'relative_margin':.01})
    packet=None;busy=False;pending_ns=0;sequence=0;last_command=0.
    dead=False;injected=False;failures=[];rows=[];responses=[]
    # Bound cyclic-GC work outside the finite measured control window. Refcount
    # cleanup still operates; restore caller state even when the episode fails.
    gc_was_enabled=gc.isenabled();gc_started=time.perf_counter_ns();gc.collect()
    preparation_gc_ms=(time.perf_counter_ns()-gc_started)/1e6;gc.disable()
    signatures_before={name:[str(x) for x in fn.signatures] for name,fn in
        [('measure',measure),('lqr',lqr),('advance',advance),('features',features)]}
    cgroup_before=cpu_counters();usage_before=resource.getrusage(resource.RUSAGE_SELF)
    origin=time.perf_counter_ns()+20_000_000
    try:
        for tick in range(steps):
            target=origin+tick*10_000_000
            wait=(target-time.perf_counter_ns())/1e9
            if wait>0:time.sleep(wait)
            release=time.perf_counter_ns(); observed=release
            thread_start=time.thread_time_ns()
            if case=='worker_crash' and tick>=steps//3 and not injected:
                process.terminate();injected=True
            if not dead:
                try:
                    if parent.poll():
                        status,message=parent.recv()
                        if status!='output':raise RuntimeError(message)
                        delivered=time.perf_counter_ns();message['received_ns']=delivered
                        responses.append(message.copy());packet=message;busy=False
                    if not process.is_alive():raise RuntimeError('worker exited')
                except (EOFError,OSError,RuntimeError) as error:
                    failures.append(dict(tick=tick,error=str(error)))
                    dead=True;packet=None;busy=False
            estimate,cov,previous,v,k=measure(state,20.,path,noises[tick],0,
                estimate,cov,previous,tick==0,1.)
            sensed=time.perf_counter_ns();thread_sensed=time.thread_time_ns()
            obs=causal_features(state,estimate,max(5.,20.+noises[tick,3]),path,gate,
                packet,busy,pending_ns,last_command,observed)
            built=time.perf_counter_ns();thread_built=time.thread_time_ns()
            baseline,gain=lqr(estimate,v,k,gains)
            based=time.perf_counter_ns();thread_based=time.thread_time_ns()
            submitted=False
            if not busy and not dead:
                try:
                    sequence+=1;parent.send((sequence,observed,obs));busy=True
                    pending_ns=observed;submitted=True
                except (EOFError,OSError):
                    dead=True;packet=None;busy=False
                    failures.append(dict(tick=tick,error='send failure'))
            gate_start=time.perf_counter_ns();thread_gate=time.thread_time_ns()
            gate_packet=None if packet is None else (packet['seq'],
                (packet['observed_ns']-origin)/1e9,packet['residual'])
            result=gate.choose((gate_start-origin)/1e9,baseline,gate_packet,
                estimate,state[5],v,k,gain,'residual')
            apply=time.perf_counter_ns()
            result=final_command(gate,result,packet,apply,baseline,target+10_000_000)
            thread_apply=time.thread_time_ns()
            command,weight,reason,j0,j1=result;last_command=command
            age=None if packet is None else (apply-packet['observed_ns'])/1e6
            old_delta=state[5]
            state=advance(state,command,20.,1.,1.)
            y,h,_=path_values(state[0],path)
            finished=time.perf_counter_ns()
            row=dict(tick=tick,release_ns=release,target_ns=target,apply_ns=apply,
                observed_ns=observed,packet_observed_ns=packet['observed_ns'] if packet else -1,
                packet_seq=packet['seq'] if packet else -1,packet_age_ms=age,
                observer_ms=(sensed-release)/1e6,features_ms=(built-sensed)/1e6,
                observer_cpu_ms=(thread_sensed-thread_start)/1e6,
                features_cpu_ms=(thread_built-thread_sensed)/1e6,
                lqr_cpu_ms=(thread_based-thread_built)/1e6,
                gate_cpu_ms=(thread_apply-thread_gate)/1e6,
                control_cpu_ms=(thread_apply-thread_start)/1e6,
                lqr_ms=(based-built)/1e6,gate_ms=(apply-gate_start)/1e6,
                control_ms=(apply-release)/1e6,iteration_ms=(finished-release)/1e6,
                release_lateness_ms=(release-target)/1e6,
                response_ms=(apply-target)/1e6,deadline_miss=apply>target+10_000_000,
                command=command,baseline=baseline,weight=weight,reason=reason,
                error=state[1]-y,heading_error=state[2]-h,actuator=state[5],
                actuator_rate=abs(state[5]-old_delta)/.01,busy=busy,
                submitted=submitted,worker_dead=dead,predicted_lqr=j0,predicted_fused=j1)
            rows.append(row)
            if not np.isfinite(state).all():raise RuntimeError('nonfinite state')
    finally:
        if gc_was_enabled:gc.enable()
        try:
            if not dead:parent.send(None)
        except (OSError,EOFError):pass
        shutdown(process);parent.close();stop.set()
        for p in stress:shutdown(p)
    cgroup_after=cpu_counters();usage_after=resource.getrusage(resource.RUSAGE_SELF)
    # Independent paired LQR replay, outside the real-time measurement window.
    shadow=initial.copy(); est=np.zeros(4);c=np.eye(4)*.01;prev=np.zeros(4);lqr_errors=[];diff=[]
    for tick,row in enumerate(rows):
        est,c,prev,v,k=measure(shadow,20.,path,noises[tick],0,est,c,prev,tick==0,1.)
        b,_=lqr(est,v,k,gains);shadow=advance(shadow,b,20.,1.,1.)
        y,_,_=path_values(shadow[0],path);lqr_errors.append(shadow[1]-y)
        diff.append(abs(b-row['command']))
    name=f'{seed}-{case}'
    for filename,records in [(name+'-ticks.csv.gz',rows),(name+'-packets.csv.gz',responses)]:
        if records:
            with gzip.open(out/filename,'wt',newline='') as f:
                w=csv.DictWriter(f,fieldnames=records[0]);w.writeheader();w.writerows(records)
    stale=[r for r in rows if r['packet_age_ms'] is not None and r['packet_age_ms']>=50]
    fallback=[r for r in rows if r['reason'] in ('missing','age','age_at_apply','deadline') or r['worker_dead']]
    result=dict(seed=seed,case=case,ticks=len(rows),startup_ms=startup_ms,
        cyclic_gc_disabled_during_window=True,preparation_gc_ms=preparation_gc_ms,
        signatures_before=signatures_before,
        signatures_after={name:[str(x) for x in fn.signatures] for name,fn in
            [('measure',measure),('lqr',lqr),('advance',advance),('features',features)]},
        worker_model_load_and_warmup_ms=warmup_ns/1e6,packets=len(responses),
        simulated_duration_s=len(rows)*.01,wall_duration_s=(rows[-1]['apply_ns']-origin)/1e9+.01,
        control=stats([r['control_ms'] for r in rows]),
        observer=stats([r['observer_ms'] for r in rows]),
        response=stats([r['response_ms'] for r in rows]),
        release_lateness=stats([r['release_lateness_ms'] for r in rows]),
        inference=stats([(r['inferred_ns']-r['entered_ns'])/1e6 for r in responses]),
        request_to_delivery=stats([(r['received_ns']-r['observed_ns'])/1e6 for r in responses]),
        request_to_worker=stats([(r['entered_ns']-r['observed_ns'])/1e6 for r in responses]),
        inference_to_delivery=stats([(r['received_ns']-r['inferred_ns'])/1e6 for r in responses]),
        earned_application_age=stats([r['packet_age_ms'] for r in rows if r['weight']>0]),
        all_held_packet_ages=stats([r['packet_age_ms'] for r in rows if r['packet_age_ms'] is not None]),
        deadline_misses=sum(r['deadline_miss'] for r in rows),
        late_authority_violations=sum(r['deadline_miss'] and r['weight']!=0 for r in rows),
        late_release_ticks=sum(r['release_lateness_ms']>=10 for r in rows),
        control_over_budget_ticks=sum(r['control_ms']>=10 for r in rows),
        control_cpu=stats([r['control_cpu_ms'] for r in rows]),
        cgroup_delta={k:cgroup_after[k]-cgroup_before[k] for k in cgroup_before},
        voluntary_switches=usage_after.ru_nvcsw-usage_before.ru_nvcsw,
        involuntary_switches=usage_after.ru_nivcsw-usage_before.ru_nivcsw,
        active_ticks=sum(r['weight']>0 for r in rows),
        stale_ticks=len(stale),stale_authority_violations=sum(r['weight']!=0 or r['command']!=r['baseline'] for r in stale),
        fallback_ticks=len(fallback),fallback_violations=sum(r['command']!=r['baseline'] or r['weight']!=0 for r in fallback),
        worker_failure_events=failures,post_failure_ticks=sum(r['worker_dead'] for r in rows),
        survived=all(abs(r['error'])<=2.5 and abs(r['heading_error'])<=.6 for r in rows),
        rmse=float(np.sqrt(np.mean([r['error']**2 for r in rows]))),
        paired_lqr_rmse=float(np.sqrt(np.mean(np.square(lqr_errors)))),
        paired_lqr_max_command_difference=max(diff),max_actuator_rate=max(r['actuator_rate'] for r in rows),
        max_command=max(abs(r['command']) for r in rows))
    (out/(name+'-summary.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('seed','case','packets','deadline_misses','active_ticks','stale_authority_violations','survived')}),flush=True)
    return result


def cpu_counters():
    path=Path('/sys/fs/cgroup/cpu.stat')
    return {key:int(value) for key,value in (line.split() for line in path.read_text().splitlines())} if path.exists() else {}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--model-root',type=Path,required=True)
    p.add_argument('--noise-base',type=int,default=983000000)
    p.add_argument('--seconds',type=float,default=13.)
    p.add_argument('--seeds',type=int,nargs='+',default=[701,802,903],choices=[701,802,903])
    p.add_argument('--cases',nargs='+',default=list(CASES),choices=list(CASES))
    a=p.parse_args()
    if a.seconds<.3 or a.seconds>60:p.error('seconds must be in [.3,60]')
    a.output.mkdir(parents=True,exist_ok=False)
    original_affinity=os.sched_getaffinity(0);cpus=sorted(original_affinity)[:2]
    sources=[Path(__file__),Path(__file__).with_name('realtime_kernels.py'),Path(__file__).with_name('causal_student.py'),Path(__file__).with_name('realtime_student.py'),ROOT/'integrations/webots/research/revision8/student.py',
        ROOT/'integrations/webots/research/revision8/teacher.py',
        ROOT/'integrations/webots/research/revision2/gating.py',
        ROOT/'integrations/webots/research/revision7/kernels.py']
    protocol=dict(kind='causal-adapter wall-paced software-in-the-loop; not native or hard real time',
        seeds=a.seeds,cases={k:CASES[k] for k in a.cases},seconds=a.seconds,
        period_ms=10,stale_age_ms=50,cpus=cpus,cpu=platform.processor(),
        affinity_before=sorted(original_affinity),python=platform.python_version(),
        feature_change='causal_query_v2: retrained train-only standardized weights; ready delivery before query; removed14/15/16/17/19 in training and runtime',
        model_root=str(a.model_root.resolve()),noise_base=a.noise_base,
        acceptance='Report every deadline miss. Functional pass requires no stale/fallback authority violations, bounded commands/rates, survival, severe-delay exact paired LQR commands, crash detection and continued ticks. Timing pass additionally requires zero 10ms response deadline misses; no hard-real-time claim.',
        source_hashes={str(s.relative_to(ROOT)):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources},
        model_hashes={str(seed):hashlib.sha256((a.model_root/str(seed)/'student.pt').read_bytes()).hexdigest() for seed in a.seeds})
    (a.output/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    ctx=mp.get_context('spawn');results=[]
    try:
        os.sched_setaffinity(0,{cpus[0]})
        for seed in a.seeds:
            for case in a.cases:results.append(episode(ctx,seed,case,a.seconds,a.output,cpus,a.model_root,a.noise_base))
    finally:os.sched_setaffinity(0,original_affinity)
    functional=all(r['survived'] and r['stale_authority_violations']==0 and r['fallback_violations']==0
        and r['late_authority_violations']==0
        and r['max_actuator_rate']<=.3500001 and r['max_command']<=.5
        and (r['case'] not in ('delay60','delay100') or r['paired_lqr_max_command_difference']==0)
        and (r['case']!='worker_crash' or r['post_failure_ticks']>0) for r in results)
    summary=dict(episodes=results,functional_pass=functional,
        timing_pass=all(r['deadline_misses']==0 for r in results),
        limitations=['software plant advances in fixed 10ms steps; wall pacing and lateness measured, not continuously evolving physical hardware',
            'cloud scheduler; fixed two-core affinity; stress is two Python busy loops, not exhaustive WCET testing',
            'causal features now match the trained profile, but teacher labels come from archived deterministic-service TRAIN/DEV; native performance is not established',
            'three seeds, one DLC path and 20m/s only; no claim of broad tracking superiority',
            'software command application boundary, not physical CAN/actuator acknowledgement'])
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('functional_pass:',functional,'timing_pass:',summary['timing_pass'],flush=True)

if __name__=='__main__':main()
