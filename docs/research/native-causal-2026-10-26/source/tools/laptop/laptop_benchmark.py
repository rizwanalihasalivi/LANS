"""Portable recorded-observation CPU/IPC timing. No vehicle actuation or training."""
import argparse,csv,hashlib,json,multiprocessing as mp,os,platform,sys,time
from pathlib import Path
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
import numpy as np

BASE=Path(__file__).resolve().parent
CANDIDATES=np.array([-.08,-.04,0.,.04,.08],dtype=np.float32)


def logits(model,x):
    x=(np.asarray(x,dtype=np.float32)-model['mean'])/model['std']
    return np.tanh(np.tanh(x@model['w0']+model['b0'])@model['w1']+model['b1'])@model['w2']+model['b2']


def load(seed):
    with np.load(BASE/f'model-{seed}.npz',allow_pickle=False) as archive:
        return {key:archive[key].copy() for key in archive.files}


def worker(conn,seed,delay):
    try:
        model=load(seed);logits(model,np.zeros((1,20),np.float32));conn.send(('ready',None))
        while True:
            request=conn.recv()
            if request is None:return
            sequence,observed,x=request;start=time.perf_counter_ns()
            index=int(logits(model,x[None,:]).argmax(1)[0]);end=time.perf_counter_ns()
            if delay:time.sleep(delay)
            conn.send(('output',dict(sequence=sequence,observed_ns=observed,
                infer_start_ns=start,infer_end_ns=end,sent_ns=time.perf_counter_ns(),
                residual_rad=float(CANDIDATES[index]))))
    except (EOFError,BrokenPipeError):pass
    except Exception as error:
        try:conn.send(('error',repr(error)))
        except (EOFError,BrokenPipeError):pass
    finally:conn.close()


def burn(stop):
    x=1
    while not stop.is_set():
        for _ in range(10000):x=(x*1664525+1013904223)&0xffffffff


def close_process(p):
    p.join(timeout=.5)
    if p.is_alive():p.terminate();p.join(timeout=2)


def percentile(values):
    if not values:return None
    a=np.asarray(values,dtype=float)
    return dict(n=len(a),median_ms=float(np.median(a)),p95_ms=float(np.quantile(a,.95)),
        p99_ms=float(np.quantile(a,.99)),max_ms=float(a.max()))


def golden_check():
    manifest=json.loads((BASE/'manifest.json').read_text())
    for name,digest in manifest['sha256'].items():
        if hashlib.sha256((BASE/name).read_bytes()).hexdigest()!=digest:raise ValueError('bundle hash mismatch: '+name)
    golden=np.load(BASE/'golden.npz',allow_pickle=False);x=golden['x'];checks=[]
    for seed in (701,802,903):
        predicted=logits(load(seed),x);expected=golden[f'logits{seed}']
        error=float(np.max(np.abs(predicted-expected)))
        if not np.array_equal(predicted.argmax(1),expected.argmax(1)) or error>1e-4:
            raise ValueError('NumPy/Torch model parity failed; timing would not validate the trained model')
        checks.append(dict(seed=seed,rows=len(x),max_logit_error=error,action_parity=True))
    return x,checks


def run_case(ctx,seed,case,seconds,observations,out):
    delay={'nominal':0.,'delay20':.02,'delay100':.1,'cpu_stress':0.,'worker_crash':0.}[case]
    parent,child=ctx.Pipe();p=ctx.Process(target=worker,args=(child,seed,delay));p.start();child.close()
    if not parent.poll(30):close_process(p);raise RuntimeError('worker startup timeout')
    status,message=parent.recv()
    if status!='ready':close_process(p);raise RuntimeError(message)
    stop=ctx.Event();stress=None
    if case=='cpu_stress':stress=ctx.Process(target=burn,args=(stop,));stress.start()
    rows=[];packets=[];busy=False;dead=False;sequence=0;packet=None;pending=None;injected=False;failure=None
    steps=round(seconds/.01);origin=time.perf_counter_ns()+20_000_000
    try:
        for tick in range(steps):
            target=origin+tick*10_000_000;remaining=(target-time.perf_counter_ns())/1e9
            if remaining>0:time.sleep(remaining)
            release=time.perf_counter_ns()
            if case=='worker_crash' and tick>=steps//3 and not injected:p.terminate();injected=True
            if not dead:
                try:
                    if parent.poll():
                        status,result=parent.recv()
                        if status!='output':raise RuntimeError(result)
                        if pending!=(result['sequence'],result['observed_ns']):raise RuntimeError('timestamp/sequence mismatch')
                        result['received_ns']=time.perf_counter_ns();packets.append(result);packet=result;busy=False
                    if not p.is_alive():raise RuntimeError('worker exited')
                except (EOFError,OSError,RuntimeError) as error:dead=True;busy=False;packet=None;failure=str(error)
            if not busy and not dead:
                sequence+=1;observed=time.perf_counter_ns()
                try:
                    parent.send((sequence,observed,observations[tick%len(observations)]));pending=(sequence,observed);busy=True
                except (EOFError,OSError) as error:dead=True;busy=False;packet=None;failure=str(error)
            finished=time.perf_counter_ns()
            age=(finished-packet['observed_ns'])/1e6 if packet else None
            rows.append(dict(tick=tick,release_ns=release,scheduled_ns=target,monitor_end_ns=finished,
                deadline_miss=finished>target+10_000_000,packet_age_ms=age,
                packet_fresh_by_age=age is not None and 0<=age<50,worker_dead=dead))
    finally:
        if not dead:
            try:parent.send(None)
            except (EOFError,OSError):pass
        close_process(p);parent.close();stop.set()
        if stress:close_process(stress)
    for suffix,records in [('ticks',rows),('packets',packets)]:
        if records:
            with (out/f'{case}-{suffix}.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=records[0]);w.writeheader();w.writerows(records)
    result=dict(case=case,ticks=len(rows),delivered_packets=len(packets),worker_failure=failure,unexpected_worker_failure=dead and case!='worker_crash',
        monitor_deadline_misses=sum(r['deadline_miss'] for r in rows),
        inference=percentile([(p['infer_end_ns']-p['infer_start_ns'])/1e6 for p in packets]),
        observation_to_receive=percentile([(p['received_ns']-p['observed_ns'])/1e6 for p in packets]),
        release_lateness=percentile([(r['release_ns']-r['scheduled_ns'])/1e6 for r in rows]),
        post_worker_failure_monitor_ticks=sum(r['worker_dead'] for r in rows))
    print(case+': '+str(result['monitor_deadline_misses'])+' monitor deadlines missed',flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=BASE/'laptop-results')
    p.add_argument('--seconds',type=float,default=10.);p.add_argument('--seed',type=int,choices=[701,802,903],default=701)
    p.add_argument('--cases',nargs='+',choices=['nominal','delay20','delay100','cpu_stress','worker_crash'],
        default=['nominal','delay20','delay100','cpu_stress','worker_crash']);p.add_argument('--verify-only',action='store_true');a=p.parse_args()
    if not .3<=a.seconds<=60:p.error('seconds must be between .3 and60')
    observations,checks=golden_check()
    if a.verify_only:print(json.dumps(checks,indent=2));return
    a.output.mkdir(parents=True,exist_ok=False)
    results=[run_case(mp.get_context('spawn'),a.seed,c,a.seconds,observations,a.output) for c in a.cases]
    report=dict(trace_kind='laptop_cpu_ipc_recorded_observations',physical_acknowledgements=False,
        vehicle_readiness_certified=False,benchmark_completed=all(not r['unexpected_worker_failure'] for r in results),os=platform.platform(),cpu=platform.processor() or os.environ.get('PROCESSOR_IDENTIFIER','unknown'),
        python=platform.python_version(),numpy=np.__version__,seed=a.seed,model_checks=checks,cases=results,
        limitations=['Recorded inputs, not live vehicle sensors; model is NumPy export of trained causal student with verified action parity.',
            'No observer, LQR, predictive gate, plant, CAN or actuator executes here. Monitor deadlines are not full controller deadlines.',
            'Injected worker sleep is separated from actual inference time. Windows scheduling is not a hard-real-time guarantee.',
            'No hostname, device ID, product ID or network identifiers are collected.'])
    (a.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Saved '+str(a.output/'summary.json'),flush=True)
    if not report['benchmark_completed']:raise SystemExit('Unexpected worker failure; inspect summary.json')

if __name__=='__main__':mp.freeze_support();main()
