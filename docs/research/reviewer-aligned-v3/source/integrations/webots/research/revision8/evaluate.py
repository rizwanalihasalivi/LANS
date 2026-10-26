"""Closed-loop fresh evaluation after supervised DEV-only checkpoint selection."""
import argparse,concurrent.futures,csv,gzip,itertools,json,os,subprocess,sys,time
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
from bootstrap import HERE,RESEARCH
from teacher import choose,features
from data import noise_inputs,P,G
from student import load
from kernels import measure,lqr,execution_step,path_values,initial_executor
from plant import advance
from comparison import configure_lqr
from core import GAINS
METHODS=['lqr','fixed_m004','teacher','student','previous_ppo']


def episode(model,method,repetition,speed,path_name,region,gains,trace=None):
    case=G['scenarios'][region];path=tuple(float(v) for v in G['paths'][path_name]);scheduled=int(np.ceil((220/speed+2)/.01))
    noise_id,actual,forecast,_=noise_inputs(P['splits']['evaluation']['noise_base'],repetition,speed,list(G['paths']).index(path_name),list(G['scenarios']).index(region),case,scheduled)
    y,h,_=path_values(0.,path);state=np.array([0.,y+.15,h+.01,0.,0.,0.])
    estimate=np.zeros(4);cov=np.eye(4)*.01;previous=np.zeros(4);worker=initial_executor()
    errors=[];weights=[];rates=[];runtimes=[];records=[];failed=False;teacher_calls=0
    for tick in range(scheduled):
        raw_v=max(5.,previous[3]) if case['sensor_delay_steps'] and tick else max(5.,speed+actual[tick,3])
        estimate,cov,previous,v,k=measure(state,float(speed),path,actual[tick],case['sensor_delay_steps'],estimate,cov,previous,tick==0,float(case['noise']))
        observed=features(state,estimate,raw_v,path,worker,tick,case['service_ticks'])
        baseline,gain=lqr(estimate,v,k,gains);proposal=0.;selected=-1;costs=np.full(5,np.nan)
        available=worker[7]<0 or worker[6]<=tick*.01+1e-9;start=time.perf_counter()
        if available:
            if method=='teacher':
                selected,costs=choose(state,estimate,cov,previous,worker,tick,case['service_ticks'],float(speed),path,case['mu'],case['stiffness'],forecast[tick],case['sensor_delay_steps'],float(case['noise']),v,k,gains)
                proposal=P['candidates_rad'][selected];teacher_calls+=1
            elif method=='fixed_m004':proposal=-.04
            elif method in ('student','previous_ppo'):
                action,_=model.predict(observed,deterministic=True)
                if np.asarray(action).shape!=(1,) or not np.isfinite(action).all():raise ValueError('finite normalized action required')
                proposal=.08*float(np.clip(action[0],-1.,1.))
        command,weight,reason,submitted=execution_step(worker,tick*.01,proposal,case['service_ticks'],baseline,estimate,state[5],v,k,gain,False)
        runtimes.append(time.perf_counter()-start)
        if region=='latency100':assert command==baseline and weight==0.
        old=state[5];state=advance(state,command,float(speed),case['mu'],case['stiffness'])
        reference,heading,_=path_values(state[0],path);error=state[1]-reference
        errors.append(error);weights.append(weight);rates.append(abs(state[5]-old)/.01)
        if trace:
            records.append(dict(tick=tick,state_time_s=(tick+1)*.01,x=state[0],y=state[1],reference=reference,error=error,
                command=command,baseline=baseline,actuator=state[5],weight=weight,reason=reason,proposal=proposal,
                teacher_selected=selected,**{f'cost{i}':costs[i] for i in range(5)},**{f'obs{i}':observed[i] for i in range(20)}))
        if abs(error)>2.5 or abs(state[2]-heading)>.6 or not np.isfinite(state).all():failed=True;break
    if trace:
        with gzip.open(trace,'wt',newline='') as f:
            w=csv.DictWriter(f,fieldnames=records[0],lineterminator='\n');w.writeheader();w.writerows(records)
    assert max(rates)<=.3500001
    return dict(seed=P['student']['seeds'][repetition],noise_id=noise_id,speed=speed,path=path_name,scenario=region,method=method,
        survived=not failed,steps=len(errors),scheduled_steps=scheduled,rmse=float(np.sqrt(np.mean(np.square(errors)))),
        penalized_rmse=float(np.sqrt((sum(e*e for e in errors)+(scheduled-len(errors))*6.25)/scheduled)),
        active_fraction=float(np.mean(np.array(weights)>0)),mean_weight=float(np.mean(weights)),max_rate=max(rates),
        wall_p99_s=float(np.quantile(runtimes,.99)),teacher_calls=teacher_calls)


def shard(students,repetition,out):
    configure_lqr();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    gains=np.array([GAINS[v] for v in (15,20,25)]);seed=P['student']['seeds'][repetition]
    student=load(students/str(seed));previous_seed=[301,402,503][repetition]
    previous=PPO.load(RESEARCH.parent/f'results/revision6-correction/training/execution-{previous_seed}/policy.zip',device='cpu')
    assert previous.seed==previous_seed and previous.num_timesteps==100000 and previous.observation_space.shape==(20,)
    out.mkdir(parents=True,exist_ok=False);(out/'traces').mkdir();rows=[]
    with (out/'episodes.csv').open('w',newline='') as f:
        writer=None
        for speed,path,region in itertools.product(G['speeds'],G['paths'],G['scenarios']):
            for method in METHODS:
                trace=out/'traces'/f'{region}-{method}.csv.gz' if repetition==0 and speed==25 and path=='dlc220' else None
                model=student if method=='student' else previous if method=='previous_ppo' else None
                row=episode(model,method,repetition,speed,path,region,gains,trace)
                if writer is None:writer=csv.DictWriter(f,fieldnames=row,lineterminator='\n');writer.writeheader()
                writer.writerow(row);f.flush();rows.append(row)
            print('evaluation',seed,speed,path,region,len(rows),flush=True)
    assert len(rows)==180
    (out/'complete.json').write_text(json.dumps(dict(episodes=180,seed=seed,previous_ppo_seed=previous_seed,protocol=P),indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--students',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--repetition',type=int,choices=[0,1,2]);a=parser.parse_args()
    if a.repetition is not None:shard(a.students,a.repetition,a.output);return
    assert json.loads((a.students/'complete.json').read_text())['protocol']==P
    a.output.mkdir(parents=True,exist_ok=False)
    def job(i):
        env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
        out=a.output/f'seed-{P["student"]["seeds"][i]}'
        with (a.output/f'{i}.log').open('w') as f:
            subprocess.run([sys.executable,str(HERE/'evaluate.py'),'--students',str(a.students),'--output',str(out),'--repetition',str(i)],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
        with (out/'episodes.csv').open() as f:return list(csv.DictReader(f))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=[r for shard_rows in pool.map(job,range(3)) for r in shard_rows]
    assert len(rows)==540
    with (a.output/'episodes.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
    (a.output/'complete.json').write_text(json.dumps(dict(episodes=540,protocol=P,ppo_finetuning=False,actual_future_noise_in_teacher=False),indent=2)+'\n')


if __name__=='__main__':main()
