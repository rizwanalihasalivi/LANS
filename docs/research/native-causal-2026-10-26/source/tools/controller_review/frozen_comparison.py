"""Prepare/run the finite frozen comparison only after timing/native eligibility.

Blocked preparation never opens the reserved noise stream or creates episode rows.
This is a common-software-plant comparison, not physical hardware validation.
"""
import argparse,csv,gzip,hashlib,itertools,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/controller_review'))
from causal_student import project_queries,load_causal,np
from realtime_optimized import measure,lqr,advance,path_values,configure_lqr,GAINS
from kernels import execution_step,initial_executor
from teacher import features
from data import G

METHODS=('lqr','fixed_m004','fixed_p004','causal_student')


def eligibility(timing,native):
    reasons=[]
    t=json.loads((timing/'summary.json').read_text());tv=json.loads((timing/'verification.json').read_text())
    n=json.loads((native/'verification.json').read_text())
    expected={(seed,case) for seed in (701,802,903) for case in
        ('nominal','delay20','delay60','delay100','cpu_stress','worker_crash')}
    if len(t['episodes'])!=18 or {(r['seed'],r['case']) for r in t['episodes']}!=expected:reasons.append('incomplete timing grid')
    if not t['functional_pass'] or not tv['raw_timestamp_and_model_replay_checks_pass']:reasons.append('timing functional/replay failure')
    if not t['timing_pass'] or any(e['deadline_misses'] for e in t['episodes']):reasons.append('10ms software timing criterion failed')
    # Audit exact raw timing rather than trusting a summary's pass flag.
    files=list(timing.glob('*-ticks.csv.gz'))
    if {f.name for f in files}!={f'{seed}-{case}-ticks.csv.gz' for seed,case in expected}:reasons.append('raw timing grid incomplete')
    for f in files:
        for row in csv.DictReader(gzip.open(f,'rt')):
            if int(row['apply_ns'])>int(row['target_ns'])+10_000_000:
                if 'raw software deadline misses' not in reasons:reasons.append('raw software deadline misses')
                break
    if n['smoke'] or len(n['cases'])!=6 or not n['native_interface_verification_pass']:reasons.append('native development interface incomplete/failed')
    if not n['strict_native_wall_timing_pass']:reasons.append('native wall-clock timing criterion failed')
    for case in n['cases']:
        trace=native/case['name']/'telemetry.csv'
        if not trace.exists():reasons.append('native raw trace missing');continue
        for row in csv.DictReader(trace.open()):
            if int(row['wall_apply_ns'])>int(row['wall_deadline_ns']):
                if 'raw native deadline misses' not in reasons:reasons.append('raw native deadline misses')
                break
    return dict(eligible=not reasons,reasons=reasons,reserved_noise_opened=False)


def episode(model,method,rep,speed,path_name,region):
    case=G['scenarios'][region];path=tuple(float(v) for v in G['paths'][path_name])
    scheduled=int(np.ceil((220/speed+2)/.01));noise_id=994000000+rep*10000+speed*100+list(G['paths']).index(path_name)*10+list(G['scenarios']).index(region)
    noise=np.random.default_rng(noise_id).normal(0,np.array([.03,np.deg2rad(.17),.01,.1])*case['noise'],size=(scheduled,4))
    y,h,_=path_values(0.,path);state=np.array([0.,y+.15,h+.01,0.,0.,0.])
    est=np.zeros(4);cov=np.eye(4)*.01;prev=np.zeros(4);worker=initial_executor()
    gains=np.array([GAINS[v] for v in (15,20,25)]);errors=[];active=0;failed=False
    for tick in range(scheduled):
        raw=max(5.,prev[3]) if case['sensor_delay_steps'] and tick else max(5.,speed+noise[tick,3])
        est,cov,prev,v,k=measure(state,float(speed),path,noise[tick],case['sensor_delay_steps'],est,cov,prev,tick==0,float(case['noise']))
        b,g=lqr(est,v,k,gains)
        if method=='lqr':u=b;weight=0.
        else:
            proposed=0.
            if worker[7]<0 or worker[6]<=tick*.01+1e-9:
                if method=='causal_student':
                    obs=features(state,est,raw,path,worker,tick,case['service_ticks'])
                    action,_=model.predict(project_queries(obs[None,:])[0],deterministic=True)
                    proposed=.08*float(np.clip(action[0],-1.,1.))
                else:proposed=-.04 if method=='fixed_m004' else .04
            u,weight,reason,submitted=execution_step(worker,tick*.01,proposed,case['service_ticks'],b,est,state[5],v,k,g,False)
        if not np.isfinite(u):raise RuntimeError('nonfinite command, abort reserved run')
        if region=='latency100':assert u==b and weight==0
        state=advance(state,u,float(speed),case['mu'],case['stiffness'])
        if not np.isfinite(state).all():raise RuntimeError('nonfinite plant, abort reserved run')
        y,h,_=path_values(state[0],path);error=state[1]-y;errors.append(error);active+=weight>0
        if abs(error)>2.5 or abs(state[2]-h)>.6:failed=True;break
    return dict(seed=(701,802,903)[rep],noise_id=noise_id,speed=speed,path=path_name,scenario=region,
        method=method,steps=len(errors),scheduled_steps=scheduled,survived=not failed,active_ticks=active,
        penalized_rmse=float(np.sqrt((np.square(errors).sum()+(scheduled-len(errors))*6.25)/scheduled)))


def main():
    p=argparse.ArgumentParser();p.add_argument('--timing',type=Path,required=True);p.add_argument('--native',type=Path,required=True)
    p.add_argument('--models',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--run-if-eligible',action='store_true');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    decision=eligibility(a.timing,a.native)
    protocol=dict(noise_base=994000000,episodes=432,seeds=[701,802,903],speeds=G['speeds'],paths=G['paths'],
        conditions=G['scenarios'],methods=METHODS,model_sha256={str(s):hashlib.sha256((a.models/str(s)/'student.pt').read_bytes()).hexdigest() for s in (701,802,903)},
        normalization_sha256={str(s):hashlib.sha256((a.models/str(s)/'normalization.npz').read_bytes()).hexdigest() for s in (701,802,903)},
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        selection='No post-test selection, retraining or tuning; every outcome is reported. Equality at100ms is fallback, not learned gain.',
        scope='common software plant; not native final comparison, hardware validation or reproduced SOTA')
    (a.output/'freeze.json').write_text(json.dumps(protocol,indent=2)+'\n')
    (a.output/'eligibility.json').write_text(json.dumps(decision,indent=2)+'\n')
    if not decision['eligible'] or not a.run_if_eligible:
        print(json.dumps(decision,indent=2));return
    configure_lqr();rows=[]
    with (a.output/'episodes.csv').open('x',newline='') as f:
        writer=None
        for rep,seed in enumerate((701,802,903)):
            model=load_causal(a.models/str(seed))
            for speed,path,region,method in itertools.product(G['speeds'],G['paths'],G['scenarios'],METHODS):
                row=episode(model,method,rep,speed,path,region)
                if writer is None:writer=csv.DictWriter(f,fieldnames=row);writer.writeheader()
                writer.writerow(row);f.flush();rows.append(row)
    assert len(rows)==432
    (a.output/'summary.json').write_text(json.dumps(dict(episodes=len(rows),
        mean_penalized_rmse={m:float(np.mean([r['penalized_rmse'] for r in rows if r['method']==m])) for m in METHODS}),indent=2)+'\n')
    decision['reserved_noise_opened']=True
    (a.output/'eligibility.json').write_text(json.dumps(decision,indent=2)+'\n')

if __name__=='__main__':main()
