"""Portable full-controller SOFTWARE-PLANT timing; no Webots/physical sensors."""
import argparse
import csv
import gc
import importlib.util
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import platform
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[2]
# Apply before boot/NumPy/SciPy load a BLAS runtime. Setting these later in
# load_portable() cannot resize an already initialized BLAS thread pool.
# Small fixed controller/actor matrices do not need nested parallel workers.
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
os.environ.setdefault('NUMBA_CACHE_DIR',str(ROOT/'.numba-cache'))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.matplotlib-cache'))
sys.path.insert(0,str(ROOT/'tools/reviewer_followup'))
sys.path.insert(0,str(ROOT/'tools/laptop'))
sys.path.insert(0,str(ROOT/'tools/controller_review'))
import boot
import numpy as np
import environment
from environment import CausalEnv
import boot10
from features9 import make_observation as observation
from filtered import FilteredController
from plant import advance
from kernels import path_values
from realtime_kernels import measure_fast
from precision_wait import DeadlineWaiter

environment.measure=measure_fast
CASES={'nominal':0.,'delay20':.02,'delay1000':1.,'cpu_stress':0.,'worker_crash':0.}


def controller(profile):
    if profile!='audited_history_comp_v10':raise ValueError('v9 history_comp profile required')
    from controller10 import RKController
    return RKController(compensated=True)


def validate_response(message,pending,received):
    try:
        if any(isinstance(message[k],bool) or not isinstance(message[k],int) for k in ('seq','observed_ns')) or message['seq']<1:raise RuntimeError('invalid request identity type')
        if pending!=(message['seq'],message['observed_ns']):raise RuntimeError('request/response identity mismatch')
        stamps=[message[k] for k in ('observed_ns','entered_ns','inferred_ns','sent_ns')]+[received]
        if any(not isinstance(v,int) or v<0 for v in stamps) or stamps!=sorted(stamps):raise RuntimeError('invalid response timestamps')
        if not math.isfinite(message['residual']) or abs(message['residual'])>.080000001:raise RuntimeError('invalid response residual')
    except (KeyError,TypeError,ValueError) as error:raise RuntimeError('malformed worker response') from error


def load_portable(folder):
    spec=importlib.util.spec_from_file_location('portable_actor',ROOT/'tools/laptop/laptop_benchmark.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.BASE=Path(folder);return module


def actor(connection,folder,seed,delay):
    try:
        portable=load_portable(folder);portable.golden_check();model=portable.load(seed)
        for _ in range(100):portable.logits(model,np.zeros((1,20),dtype=np.float32))
        with DeadlineWaiter('auto') as waiter:
            connection.send(('ready',waiter.backend))
            while True:
                request=connection.recv()
                if request is None:return
                seq,observed_ns,x,*extra=request
                entered=time.perf_counter_ns();index=int(portable.logits(model,x[None,:]).argmax(1)[0])
                inferred=time.perf_counter_ns()
                if delay:waiter.wait_until_ns(inferred+int(delay*1e9))
                message=dict(seq=seq,observed_ns=observed_ns,entered_ns=entered,
                    inferred_ns=inferred,sent_ns=time.perf_counter_ns(),residual=[-.08,-.04,0.,.04,.08][index],
                    observation_json=json.dumps(x.tolist()))
                if extra:message['query_metadata_json']=json.dumps(extra[0])
                connection.send(('output',message))
    except (EOFError,BrokenPipeError):pass
    except Exception as error:
        try:connection.send(('error',repr(error)))
        except (EOFError,OSError):pass
    finally:connection.close()


def burn(stop):
    value=.123
    while not stop.is_set():
        for _ in range(10000):value=(value*1.000001+.000001)%1.


def prepared_burn(stop,connection):
    connection.send('ready');connection.close();burn(stop)


def external_crash(connection):
    """Fault injection is not part of the monitor's control calculation."""
    import signal
    with DeadlineWaiter('auto') as waiter:
        connection.send('ready');target,pid=connection.recv();waiter.wait_until_ns(target)
        at=time.perf_counter_ns()
        try:os.kill(pid,signal.SIGTERM);connection.send(dict(requested_ns=target,sent_ns=at,pid=pid))
        except OSError as error:connection.send(dict(error=repr(error),requested_ns=target,sent_ns=at))
    connection.close()


def shutdown(process):
    process.join(timeout=.5)
    if process.is_alive():process.terminate();process.join(timeout=2)


def write_csv(file,rows):
    if not rows:return
    with file.open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=rows[0],lineterminator='\n');writer.writeheader();writer.writerows(rows)


def budget_due(target_ns,now_ns):return now_ns>=target_ns+9_000_000

def runtime_revoke(ctrl,baseline,reason,clear=True):
    if hasattr(ctrl,'revoke'):return ctrl.revoke(baseline,reason,clear=clear)[0]
    ctrl.filtered=0.;ctrl.weight=0.;ctrl.good=0;ctrl.last_command=baseline
    return baseline

def episode(ctx,case,seed,profile,seconds,models,out,external_fault=False,noise_base=1256000000,budget_guard=False):
    declared=json.loads((Path(models)/'manifest.json').read_text()).get('profile')
    versioned={'audited_history_comp_v10':'causal_recovery_history_v9'}
    if ((profile in versioned and declared!=versioned[profile]) or
            (profile not in versioned and declared in versioned.values())):
        raise ValueError('Controller/model input ABI mismatch; history and legacy artifacts cannot be mixed')
    if budget_guard and profile not in ('audited_history_comp_v10',):raise ValueError('Budget guard requires explicit recovery profile')
    env=CausalEnv(mode='lqr',case=(20,'dlc220',1,'nominal',noise_base+seed));env.reset()
    # Warm every parent numerical path outside the measured window.
    for _ in range(40):env.step(2)
    c=controller(profile)
    c.packet=(1,0.,.04);c.previews=env.obs[6:9].astype(float)*.02
    for i in range(5):c.choose(i*.001,env.baseline,env.estimate,env.state[5],env.measured_speed,env.curvature,env.gain)
    env.reset();env.tick=0;env.estimate=np.zeros(4);env.cov=np.eye(4)*.01;env.previous=np.zeros(4)
    ctrl=controller(profile);env.ctrl=ctrl
    parent,child=ctx.Pipe();worker=ctx.Process(target=actor,args=(child,str(models),seed,CASES[case]))
    worker.start();child.close()
    if not parent.poll(120):shutdown(worker);raise RuntimeError('actor startup timeout; first-run compilation is outside measured window')
    status,backend=parent.recv()
    if status!='ready':shutdown(worker);raise RuntimeError(backend)
    stop=ctx.Event();stress=None
    if case=='cpu_stress':
        ready,ready_child=ctx.Pipe();stress=ctx.Process(target=prepared_burn,args=(stop,ready_child));stress.start();ready_child.close()
        if not ready.poll(120) or ready.recv()!='ready':
            stop.set();shutdown(stress);shutdown(worker);ready.close();parent.close()
            raise RuntimeError('stress readiness timeout')
        ready.close()
    killer=None;fault=None;fault_event=None
    if case=='worker_crash' and external_fault:
        fault,fault_child=ctx.Pipe();killer=ctx.Process(target=external_crash,args=(fault_child,));killer.start();fault_child.close()
        if not fault.poll(120) or fault.recv()!='ready':
            stop.set();shutdown(killer);shutdown(worker);fault.close();parent.close()
            raise RuntimeError('fault injector readiness timeout')
    n=round(seconds/.01);packet=None;pending=None;busy=False;dead=False;seq=0;rows=[];packets=[];errors=[]
    enabled=gc.isenabled();gc.collect();gc.disable()
    try:
        with DeadlineWaiter('auto') as waiter:
            monitor_backend=waiter.backend;origin=time.perf_counter_ns()+20_000_000
            if killer is not None:fault.send((origin+(n//3)*10_000_000,worker.pid))
            for tick in range(n):
                target=origin+tick*10_000_000;waiter.wait_until_ns(target)
                release=time.perf_counter_ns()
                cpu_start=time.thread_time_ns()
                if case=='worker_crash' and tick==n//3 and not external_fault:worker.terminate()
                if not dead:
                    try:
                        if parent.poll():
                            tag,message=parent.recv()
                            if tag!='output':raise RuntimeError(message)
                            received=time.perf_counter_ns()
                            validate_response(message,pending,received)
                            if hasattr(ctrl,'compensator'):
                                ctrl.compensator.observe(message['seq'],(received-message['observed_ns'])/1e9)
                            message['received_ns']=received;packet=message;packets.append(message);busy=False;pending=None
                        if not worker.is_alive():raise RuntimeError('worker exited')
                    except (EOFError,OSError,RuntimeError) as error:
                        errors.append(str(error));dead=True;packet=None;busy=False
                polled=time.perf_counter_ns()
                env._sense()
                sensed=time.perf_counter_ns()
                baseline=env.baseline
                if packet is None:ctrl.packet=None
                else:ctrl.packet=(packet['seq'],(packet['observed_ns']-origin)/1e9,packet['residual'])
                ctrl.previews=env.obs[6:9].astype(float)*.02
                obs=observation(env.state,env.estimate,env.measured_speed,ctrl.previews,ctrl,(release-origin)/1e9)
                if getattr(ctrl,'policy_history_feature',False):obs[14]=float(np.clip(ctrl.filtered/.08,-1.,1.))
                query_meta=None
                query_allowed=not budget_guard or not budget_due(target,time.perf_counter_ns())
                if hasattr(ctrl,'compensator') and not busy and not dead and query_allowed:
                    obs,query_meta=ctrl.prepare_query(obs,env.estimate,env.state[5],env.measured_speed,ctrl.previews,env.gain)
                built=time.perf_counter_ns()
                submitted=False
                if not busy and not dead and query_allowed and (not budget_guard or not budget_due(target,time.perf_counter_ns())):
                    try:
                        seq+=1;request=(seq,release,obs)
                        if query_meta is not None:request=(*request,query_meta)
                        parent.send(request);busy=True;pending=(seq,release);submitted=True
                    except (OSError,EOFError):dead=True;packet=None;ctrl.packet=None
                submitted_at=time.perf_counter_ns()
                decision_at=time.perf_counter_ns()
                decision_skipped=budget_guard and budget_due(target,decision_at)
                if decision_skipped:command=runtime_revoke(ctrl,baseline,'budget');reason='budget'
                else:command,reason=ctrl.choose((decision_at-origin)/1e9,baseline,env.estimate,
                    env.state[5],env.measured_speed,env.curvature,env.gain)
                decision_command=command;decision_weight=ctrl.weight;decision_filter=ctrl.filtered;decision_good=ctrl.good
                apply=time.perf_counter_ns();age=None if packet is None else (apply-packet['observed_ns'])/1e9
                miss=apply>target+10_000_000
                if miss or (age is not None and age>=.05):
                    reason='deadline' if miss else 'age_at_apply'
                    command=runtime_revoke(ctrl,baseline,reason,clear=miss or not hasattr(ctrl,'revoke'))
                # Record after fallback handling; recheck at software commit.
                commit=time.perf_counter_ns();commit_age=None if packet is None else (commit-packet['observed_ns'])/1e9
                if commit>target+10_000_000 or (commit_age is not None and commit_age>=.05):
                    reason='deadline' if commit>target+10_000_000 else 'age_at_apply'
                    command=runtime_revoke(ctrl,baseline,reason,clear=commit>target+10_000_000 or not hasattr(ctrl,'revoke'))
                    commit=time.perf_counter_ns()
                apply=commit;age=None if packet is None else (apply-packet['observed_ns'])/1e9;miss=apply>target+10_000_000
                cpu_end=time.thread_time_ns()
                old=env.state[5];env.state=advance(env.state,command,20.,.9,1.);env.tick+=1
                y,h,_=path_values(env.state[0],env.path)
                row=dict(tick=tick,target_ns=target,release_ns=release,apply_ns=apply,
                    observed_ns=release,command=float(command),baseline=float(baseline),weight=ctrl.weight,
                    filtered_residual=ctrl.filtered,reason=reason,packet_seq=packet['seq'] if packet else -1,
                    packet_observed_ns=packet['observed_ns'] if packet else -1,packet_age_s=age,
                    deadline_miss=miss,worker_dead=dead,error=float(env.state[1]-y),heading_error=float(env.state[2]-h),
                    actuator=float(env.state[5]),actuator_rate=float((env.state[5]-old)/.01),
                    control_ns=apply-release,release_lateness_ns=release-target,control_cpu_ns=cpu_end-cpu_start,
                    poll_ns=polled-release,sensing_lqr_ns=sensed-polled,feature_ns=built-sensed,
                    submit_ns=submitted_at-built,supervision_commit_ns=apply-submitted_at,
                    submitted=submitted,request_seq=seq if submitted else -1,decision_ns=decision_at,
                    decision_command=decision_command,decision_weight=decision_weight,decision_filter=decision_filter,
                    decision_good=decision_good,good=ctrl.good,predicted_base=ctrl.last_costs[0],predicted_candidate=ctrl.last_costs[1])
                if hasattr(ctrl,'compensator'):
                    row['query_metadata_json']=json.dumps(query_meta) if submitted else ''
                    row['query_observation_json']=json.dumps(obs.tolist()) if submitted else ''
                if profile in ('audited_history_comp_v10',):
                    row['budget_guard']=budget_guard;row['decision_skipped']=decision_skipped
                    row['qualified_sequence']=ctrl.last_qualified_sequence
                    row['qualified_time_s']=ctrl.last_qualified_time
                rows.append(row)
    finally:
        if enabled:gc.enable()
        try:
            if not dead:parent.send(None)
        except (OSError,EOFError):pass
        shutdown(worker);parent.close();stop.set()
        if stress is not None:shutdown(stress)
        if killer is not None:
            shutdown(killer)
            if fault.poll():fault_event=fault.recv()
            fault.close()
    write_csv(out/f'{case}-ticks.csv',rows);write_csv(out/f'{case}-packets.csv',packets)
    violations=sum((r['worker_dead'] or r['deadline_miss'] or (r['packet_age_s'] is not None and r['packet_age_s']>=.05))
                   and (r['weight']!=0 or r['command']!=r['baseline']) for r in rows)
    result=dict(case=case,ticks=n,seed=seed,noise_id=noise_base+seed,profile=profile,
        deadline_misses=sum(r['deadline_miss'] for r in rows),fallback_violations=violations,
        nonzero_correction_ticks=sum(abs(r['command']-r['baseline'])>1e-10 for r in rows),
        survived=all(abs(r['error'])<=2.5 and abs(r['heading_error'])<=.6 for r in rows),
        actor_packets=len(packets),intentional_failure_events=errors,external_fault_event=fault_event,monitor_timer_backend=monitor_backend,
        worker_timer_backend=backend,simulated_duration_s=n*.01,
        wall_duration_s=(rows[-1]['apply_ns']-origin)/1e9+.01)
    print(case,result['deadline_misses'],'controller deadlines missed; fallback violations',violations,flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--models',type=Path,default=ROOT/'actor')
    p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=float,default=13.)
    p.add_argument('--seed',type=int,choices=[701,802,903],default=701)
    p.add_argument('--profile',choices=['audited_history_comp_v10'],default='audited_history_comp_v10')
    p.add_argument('--budget-guard',action='store_true')
    args=p.parse_args()
    if not .5<=args.seconds<=30:p.error('seconds must be0.5..30')
    args.output.mkdir(parents=True,exist_ok=False)
    rows=[episode(mp.get_context('spawn'),case,args.seed,args.profile,args.seconds,args.models,args.output,external_fault=True,budget_guard=args.budget_guard) for case in CASES]
    result=dict(scope='Full observer/LQR/residual-supervisor/actor IPC plus fixed-step software plant; NOT native Webots, sensors/CAN or physical actuator',
        runtime=dict(python=sys.version,platform=platform.platform(),numpy=np.__version__),episodes=rows,
        functional_pass=all(r['survived'] and r['fallback_violations']==0 for r in rows),
        observed_timing_pass=all(r['deadline_misses']==0 for r in rows),guaranteed_hard_realtime=False,
        injection='Actual post-inference worker unavailability; recorded separately from computation duration',
        limits='Plant advances in10ms simulation steps; host stalls do not continuously advance physical dynamics. Target execution must be verified on this laptop.')
    (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    with zipfile.ZipFile(args.output/'Results.zip','w',zipfile.ZIP_DEFLATED) as z:
        for f in args.output.iterdir():
            if f.suffix in ('.json','.csv'):z.write(f,f.name)
    print('Saved',args.output/'Results.zip',flush=True)


if __name__=='__main__':main()
