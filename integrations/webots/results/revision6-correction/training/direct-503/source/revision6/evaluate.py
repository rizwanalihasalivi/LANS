"""Fresh paired development grid; uniform physics, sensing and executed commands."""
import argparse,csv,gzip,json,math,time
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
from bootstrap import HERE,RESEARCH
from core import Sensor,path_values
from comparison import configure_lqr
from execution import Execution,matched_lqr
from plant import advance
from mpc import MPC
P=json.loads((HERE/'protocol.json').read_text())


def episode(model,method,seed,speed,path_name,region,trace=None):
    case=P['scenarios'][region];path=tuple(P['paths'][path_name])
    noise=P['development_noise_base']+P['seeds'].index(seed)*10000+speed*100+list(P['paths']).index(path_name)*10+list(P['scenarios']).index(region)
    sensor=Sensor(noise,case['noise'],case['sensor_delay_steps'])
    y,h,_=path_values(0,path);state=np.array([0.,y+.15,h+.01,0.,0.,0.])
    executor=Execution();mpc=MPC() if method=='mpc' else None
    errors=[];weights=[];ages=[];runtimes=[];rates=[];corrections=[];reasons={};trace_rows=[]
    scheduled=math.ceil((220/speed+2)/.01);failed=False
    for tick in range(scheduled):
        t=tick*.01;obs,estimate,kappa=sensor.measure(state,speed,path)
        measured=max(5.,float(obs[4])*25);baseline,gain=matched_lqr(estimate,measured,kappa)
        context=executor.context(t)
        inputs=np.r_[obs,context,case['service_ticks']/10].astype(np.float32)
        started=time.perf_counter();weight=0.;age=math.nan;reason='local'
        if method=='lqr':command=baseline
        elif method=='mpc':command=mpc.command(estimate,state[5],measured,obs[6:9]*.02,baseline);reason=mpc.last_status
        else:
            # An unavailable worker does not run another policy inference. At release
            # the next request may be submitted, matching Execution.step's lifecycle.
            available=executor.pending is None or executor.pending[0]<=t+1e-9
            proposed=0.
            if available:
                if method.startswith('constant'):proposed=.08 if method=='constant_positive' else -.08
                else:
                    value,_=model.predict(inputs,deterministic=True)
                    if not np.isfinite(value).all():raise ValueError('nonfinite learned action')
                    proposed=.08*float(np.clip(value[0],-1,1))
            command,info=executor.step(t,proposed,case['service_ticks'],baseline,estimate,state[5],measured,kappa,gain)
            weight=info['gate_weight'];age=info['action_age_s'];reason=info['gate_reason']
            if region=='latency100':assert command==baseline and weight==0.
        runtimes.append(time.perf_counter()-started)
        old=state[5];state=advance(state,command,speed,case['mu'],case['stiffness'])
        reference,heading,_=path_values(state[0],path);error=state[1]-reference
        errors.append(error);weights.append(weight);rates.append(abs(state[5]-old)/.01);corrections.append(command-baseline)
        if math.isfinite(age):ages.append(age)
        reasons[reason]=reasons.get(reason,0)+1
        if trace:trace_rows.append(dict(tick=tick,state_time_s=t+.01,x=state[0],y=state[1],reference=reference,
            error=error,command=command,baseline=baseline,actuator=state[5],weight=weight,age=age,reason=reason))
        if abs(error)>2.5 or abs(state[2]-heading)>.6 or not np.isfinite(state).all():failed=True;break
    if trace:
        with gzip.open(trace,'wt',newline='') as f:
            w=csv.DictWriter(f,fieldnames=trace_rows[0],lineterminator='\n');w.writeheader();w.writerows(trace_rows)
    assert max(rates)<=.3500001
    return dict(seed=seed,noise_seed=noise,speed=speed,path=path_name,scenario=region,method=method,survived=not failed,
        steps=len(errors),scheduled_steps=scheduled,rmse=float(np.sqrt(np.mean(np.square(errors)))),
        penalized_rmse=float(np.sqrt((sum(e*e for e in errors)+(scheduled-len(errors))*6.25)/scheduled)),
        active_fraction=float(np.mean(np.array(weights)>0)),mean_weight=float(np.mean(weights)),
        correction_rms_rad=float(np.sqrt(np.mean(np.square(corrections)))),max_rate=max(rates),
        wall_p99_s=float(np.quantile(runtimes,.99)),age_p99_s=float(np.quantile(ages,.99)) if ages else 0.,
        mpc_calls=mpc.calls if mpc else 0,mpc_fallbacks=mpc.fallbacks if mpc else 0,reasons=json.dumps(reasons,sort_keys=True))


def main():
    p=argparse.ArgumentParser();p.add_argument('--training',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    configure_lqr();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    assert json.loads((a.training/'complete.json').read_text())['total_training_steps']==600000
    a.output.mkdir(parents=True,exist_ok=False);(a.output/'traces').mkdir()
    # Preserve evaluated implementations after the pre-run evaluation freeze.
    for source in HERE.glob('*'):
        if source.suffix in ('.py','.json'):
            target=a.output/'source'/source.name;target.parent.mkdir(exist_ok=True);target.write_bytes(source.read_bytes())
    rows=[]
    with (a.output/'episodes.csv').open('w',newline='') as f:
        writer=None
        for seed in P['seeds']:
            models={}
            for arm in P['arms']:
                folder=a.training/f'{arm}-{seed}';meta=json.loads((folder/'complete.json').read_text())
                assert meta['seed']==seed and meta['steps']==100000 and meta['arm']==arm and meta['protocol']==P
                model=PPO.load(folder/'policy.zip',device='cpu')
                assert model.num_timesteps==100000 and model.observation_space.shape==(20,) and model.seed==seed
                models[arm]=model
            for speed in P['speeds']:
                for path in P['paths']:
                    for region in P['scenarios']:
                        for method in P['methods']:
                            trace=a.output/'traces'/f'{region}-{method}.csv.gz' if seed==P['seeds'][0] and speed==25 and path=='dlc220' else None
                            row=episode(models.get(method),method,seed,speed,path,region,trace)
                            if writer is None:writer=csv.DictWriter(f,fieldnames=row,lineterminator='\n');writer.writeheader()
                            writer.writerow(row);f.flush();rows.append(row)
                    print(f'seed{seed} speed{speed} path{path}: {len(rows)} episodes',flush=True)
    assert len(rows)==P['episodes']
    (a.output/'complete.json').write_text(json.dumps(dict(episodes=len(rows),protocol=P,final_reserved=False,native=False),indent=2)+'\n')


if __name__=='__main__':main()
