"""Frozen-policy paired evaluation with held-out noise seeds on known geometries."""
import argparse,csv,gzip,hashlib,json,math,time
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
from core import PROTOCOL,Sensor,Supervisor,advance,path_values,lqr
from comparison import configure_lqr
from geometry import corridor_margin
from tracking import tracking_lqr as lqr

PATHS={'dlc220':(1,0.,0.,0.),'sine120':(0,2.5,120.,.3),'sine160':(0,3.,160.,1.1)}

def episode(model,method,seed,speed,path_name,delay_ms,trace=None):
    path=PATHS[path_name]; y,heading,_=path_values(0,path)
    state=np.array([0.,y+.15,heading+.01,0.,0.,0.])
    sensor=Sensor(20000+seed*100+speed); supervisor=Supervisor()
    output=None;pending=None;sequence=0;wall_inference=[];ages=[];weights=[];errors=[];max_rate=0.;records=[];margins=[]
    count=math.ceil((220/speed+2)/.01);failed=False
    for i in range(count):
        t=i*.01;obs,estimate,kappa=sensor.measure(state,speed,path)
        baseline=lqr(estimate,speed,kappa)
        if pending is not None and pending[0]<=t+1e-9:output=pending[1];pending=None
        if model is not None and pending is None:
            start=time.perf_counter();action,_=model.predict(obs,deterministic=True);wall_inference.append(time.perf_counter()-start)
            sequence+=1;packet=(sequence,t,float(action[0])*.5)
            if delay_ms==0:output=packet
            else:pending=(t+delay_ms/1000,packet)
        age=t-output[1] if output is not None else 0.;weight=0.;reason='baseline'
        if method=='lqr':command=baseline
        elif method=='ppo':command=output[2] if output is not None else 0.
        elif method=='residual':
            residual=output[2] if output is not None else 0.
            command=baseline+math.exp(-max(0.,age-.005)/.02)*residual
        elif method=='fusion':command,weight,reason=supervisor.fuse(t,baseline,output,estimate)
        else:
            # Basic finite-value protection remains in both ablations.
            valid=output is not None and math.isfinite(output[2])
            weight=.7 if valid else 0.
            if method=='no_supervisor' and valid:weight*=max(0.,min(1.,(.05-age)/.04))
            command=weight*output[2]+(1-weight)*baseline if valid else baseline
        command=float(np.clip(command,-.5,.5));previous=state[5]
        state=advance(state,command,speed);max_rate=max(max_rate,abs(state[5]-previous)/.01)
        ey=state[1]-path_values(state[0],path)[0];ep=state[2]-path_values(state[0],path)[1]
        errors.append(ey);weights.append(weight);margins.append(corridor_margin(state[0],state[1],state[2],path))
        if output is not None:ages.append(age)
        if trace is not None:records.append([i,t,t+.01,state[0],state[1],state[2],ey,ep,command,state[5],age,weight,reason])
        if abs(ey)>2.5 or abs(ep)>.6 or not np.isfinite(state).all():failed=True;break
    if trace is not None:
        with gzip.open(trace,'wt',newline='') as f:
            writer=csv.writer(f,lineterminator='\n');writer.writerow(['step','t_command_s','t_state_s','x_m','y_m','heading_rad','error_m','heading_error_rad','command_rad','actuator_rad','age_s','weight','reason']);writer.writerows(records)
    assert max_rate<=.3500001
    return {'seed':seed,'method':method,'speed_m_s':speed,'path':path_name,'delay_ms':delay_ms,
            'survived':not failed,'steps':len(errors),'scheduled_steps':count,'rmse_m':float(np.sqrt(np.mean(np.square(errors)))),
            'failure_penalized_rmse_m':float(np.sqrt((np.sum(np.square(errors))+(count-len(errors))*2.5**2)/count)),
            'corridor_min_margin_m':float(min(margins)),'corridor_violation_fraction':float(np.mean(np.array(margins)<0)),
            'max_abs_error_m':float(np.max(np.abs(errors))),'max_actuator_rate_rad_s':max_rate,
            'fallback_fraction':float(np.mean(np.array(weights)==0)) if method=='fusion' else '',
            'age_mean_s':float(np.mean(ages)) if ages else 0.,'age_p99_s':float(np.quantile(ages,.99)) if ages else 0.,
            'age_over_10ms_fraction':float(np.mean(np.array(ages)>.01000001)) if ages else 0.,
            'inference_mean_wall_s':float(np.mean(wall_inference)) if wall_inference else 0.,
            'inference_p99_wall_s':float(np.quantile(wall_inference,.99)) if wall_inference else 0.}

def main():
    p=argparse.ArgumentParser();p.add_argument('--training',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--wait-for-training',action='store_true');args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False);(args.output/'traces').mkdir()
    sources=['evaluate.py','core.py','protocol.json','comparison.py','comparison-protocol.json','final-training-protocol.json','geometry.py','corridor-protocol.json','tracking.py','tracking-protocol.json','evaluation-revision.json']
    (args.output/'source').mkdir()
    frozen_hashes={}
    for name in sources:
        data=Path(__file__).with_name(name).read_bytes();(args.output/'source'/name).write_bytes(data);frozen_hashes[name]=hashlib.sha256(data).hexdigest()
    torch.set_num_threads(1);torch.set_num_interop_threads(1);configure_lqr()
    digest=hashlib.sha256(Path(__file__).with_name('protocol.json').read_bytes()).hexdigest()
    rows=[]
    with (args.output/'episodes.csv').open('w',newline='') as f:
        writer=None
        for seed in PROTOCOL['training_seeds']:
            models={}
            for role in ('full','residual'):
                folder=args.training/f'{role}-{seed}'
                if args.wait_for_training:
                    deadline=time.monotonic()+3600
                    if not (folder/'complete.json').exists():print(f'Waiting for final {role}-{seed} checkpoint',flush=True)
                    while not (folder/'complete.json').exists():
                        if time.monotonic()>deadline:raise TimeoutError(f'training incomplete: {folder}')
                        time.sleep(5)
                metadata=json.loads((folder/'complete.json').read_text())
                assert metadata['steps']==1000000 and metadata['protocol_sha256']==digest
                assert metadata['training_profile']=='positive_survival_v2'
                assert metadata['final_training_protocol_sha256']==hashlib.sha256(Path(__file__).with_name('final-training-protocol.json').read_bytes()).hexdigest()
                if role=='residual':
                    assert metadata['tracking_protocol_sha256']==hashlib.sha256(Path(__file__).with_name('tracking-protocol.json').read_bytes()).hexdigest()
                    assert metadata['comparison_protocol_sha256']==hashlib.sha256(Path(__file__).with_name('comparison-protocol.json').read_bytes()).hexdigest()
                assert metadata['policy_sha256']==hashlib.sha256((folder/'policy.zip').read_bytes()).hexdigest()
                models[role]=PPO.load(str(folder/'policy.zip'),device='cpu')
            for speed in (15,20,25):
                for path in PATHS:
                    for delay in (0,20,100):
                        for method in PROTOCOL['evaluation_methods']:
                            model=None if method=='lqr' else models['residual' if method=='residual' else 'full']
                            trace=args.output/'traces'/f'{method}-delay{delay}.csv.gz' if seed==0 and speed==25 and path=='dlc220' else None
                            row=episode(model,method,seed,speed,path,delay,trace)
                            if writer is None:writer=csv.DictWriter(f,fieldnames=row);writer.writeheader()
                            writer.writerow(row);f.flush();rows.append(row)
            print(f'evaluated seed {seed}: {len(rows)} episodes',flush=True)
    summary={}
    # Aggregate at the seed level; no independent-time-step confidence claims.
    for method in PROTOCOL['evaluation_methods']:
        selected=[r for r in rows if r['method']==method]
        per_seed=[np.mean([r['failure_penalized_rmse_m'] for r in selected if r['seed']==s]) for s in range(5)]
        summary[method]={'episodes':len(selected),'survived':sum(r['survived'] for r in selected),'corridor_clean':sum(r['corridor_violation_fraction']==0 for r in selected),
                         'seed_mean_penalized_rmse':list(map(float,per_seed)),
                         'mean_penalized_rmse':float(np.mean(per_seed)),'sample_sd_across_seeds':float(np.std(per_seed,ddof=1))}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (args.output/'protocol.json').write_bytes(Path(__file__).with_name('protocol.json').read_bytes())
    assert all(hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()==d for n,d in frozen_hashes.items())
    (args.output/'source-hashes.json').write_text(json.dumps(frozen_hashes,indent=2)+'\n')
if __name__=='__main__':main()
