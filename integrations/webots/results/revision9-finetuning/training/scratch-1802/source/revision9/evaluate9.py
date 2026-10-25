"""DEV-only checkpoint selection followed by a separate fresh-noise evaluation."""
import argparse,concurrent.futures,csv,gzip,itertools,json,os,subprocess,sys,time
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
from bootstrap import HERE,RESEARCH
from policy9 import P,FrozenStudent,PPOAdapter
from teacher import features
from kernels import measure,lqr,execution_step,path_values,initial_executor
from plant import advance
from comparison import configure_lqr
from core import GAINS
G=json.loads((RESEARCH/'revision6/protocol.json').read_text())
STUDENTS=RESEARCH.parent/'results/revision8-student/students'
DEV_METHODS=['lqr','fixed_m004','student']+[f'{arm}_{step}' for arm in P['arms'] for step in P['checkpoints']]
TEST_METHODS=['lqr','fixed_m004','student','scratch_selected','finetune_selected','scratch_100k','finetune_100k']


def episode(model,method,pair,speed,path_name,region,gains,split,trace=None):
    case=G['scenarios'][region];path=tuple(float(v) for v in G['paths'][path_name]);scheduled=int(np.ceil((220/speed+2)/.01))
    noise_id=P['splits'][split]+pair*10000+speed*100+list(G['paths']).index(path_name)*10+list(G['scenarios']).index(region)
    actual=np.random.default_rng(noise_id).normal(0,np.array([.03,np.deg2rad(.17),.01,.1])*case['noise'],size=(scheduled,4))
    y,h,_=path_values(0.,path);state=np.array([0.,y+.15,h+.01,0.,0.,0.])
    estimate=np.zeros(4);cov=np.eye(4)*.01;previous=np.zeros(4);worker=initial_executor()
    errors=[];weights=[];rates=[];runtimes=[];records=[];failed=False
    for tick in range(scheduled):
        raw_v=max(5.,previous[3]) if case['sensor_delay_steps'] and tick else max(5.,speed+actual[tick,3])
        estimate,cov,previous,v,k=measure(state,float(speed),path,actual[tick],case['sensor_delay_steps'],estimate,cov,previous,tick==0,float(case['noise']))
        observed=features(state,estimate,raw_v,path,worker,tick,case['service_ticks'])
        baseline,gain=lqr(estimate,v,k,gains);proposal=0.;start=time.perf_counter()
        available=worker[7]<0 or worker[6]<=tick*.01+1e-9
        if available:
            if method=='fixed_m004':proposal=-.04
            elif model is not None:
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
            records.append(dict(tick=tick,x=state[0],y=state[1],reference=reference,error=error,command=command,baseline=baseline,
                actuator=state[5],weight=weight,reason=reason,proposal=proposal,**{f'obs{i}':observed[i] for i in range(20)}))
        if abs(error)>2.5 or abs(state[2]-heading)>.6 or not np.isfinite(state).all():failed=True;break
    if trace:
        with gzip.open(trace,'wt',newline='') as f:
            w=csv.DictWriter(f,fieldnames=records[0],lineterminator='\n');w.writeheader();w.writerows(records)
    assert max(rates)<=.3500001
    return dict(seed=P['rl_seeds'][pair],pair=pair,noise_id=noise_id,speed=speed,path=path_name,scenario=region,method=method,
        survived=not failed,steps=len(errors),scheduled_steps=scheduled,rmse=float(np.sqrt(np.mean(np.square(errors)))),
        penalized_rmse=float(np.sqrt((sum(e*e for e in errors)+(scheduled-len(errors))*6.25)/scheduled)),
        active_fraction=float(np.mean(np.array(weights)>0)),mean_weight=float(np.mean(weights)),max_rate=max(rates),wall_p99_s=float(np.quantile(runtimes,.99)))


def load_checkpoint(training,arm,pair,steps):
    folder=training/f'{arm}-{P["rl_seeds"][pair]}'/f'checkpoint-{steps}'
    meta=json.loads((folder/'complete.json').read_text())
    assert meta['protocol']==P and meta['steps']==steps and meta['seed']==P['rl_seeds'][pair] and meta['arm']==arm
    model=PPO.load(folder/'policy.zip',device='cpu');assert model.num_timesteps==steps
    return PPOAdapter(model)


def shard(training,pair,out,split,selection):
    configure_lqr();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    gains=np.array([GAINS[v] for v in (15,20,25)]);models={'student':FrozenStudent(STUDENTS/str(P['student_seeds'][pair]))}
    methods=DEV_METHODS if split=='dev' else TEST_METHODS
    for method in methods:
        if method in ('lqr','fixed_m004','student'):continue
        arm,tag=method.split('_');steps=int(tag) if split=='dev' else 100000 if tag=='100k' else selection[f'{arm}-{P["rl_seeds"][pair]}']['steps']
        models[method]=load_checkpoint(training,arm,pair,steps)
    out.mkdir(parents=True,exist_ok=False);(out/'traces').mkdir();rows=[]
    with (out/'episodes.csv').open('w',newline='') as f:
        writer=None
        for speed,path,region in itertools.product(G['speeds'],G['paths'],G['scenarios']):
            for method in methods:
                trace=out/'traces'/f'{region}-{method}.csv.gz' if pair==0 and speed==25 and path=='dlc220' else None
                row=episode(models.get(method),method,pair,speed,path,region,gains,split,trace)
                if writer is None:writer=csv.DictWriter(f,fieldnames=row,lineterminator='\n');writer.writeheader()
                writer.writerow(row);f.flush();rows.append(row)
            print(split,pair,speed,path,region,len(rows),flush=True)
    assert len(rows)==36*len(methods)
    (out/'complete.json').write_text(json.dumps(dict(episodes=len(rows),pair=pair,split=split,protocol=P),indent=2)+'\n')


def metrics(rows):
    return dict(rmse=float(np.mean([float(r['penalized_rmse']) for r in rows])),survived=sum(str(r['survived']) in ('True','true') for r in rows),n=len(rows))


def select(rows):
    selected={}
    for pair in range(3):
        subset=[r for r in rows if int(r['pair'])==pair]
        for arm in P['arms']:
            candidates=[]
            for step in P['checkpoints']:
                method=f'{arm}_{step}';reasons=[];current=[r for r in subset if r['method']==method]
                for region in G['scenarios']:
                    a=metrics([r for r in current if r['scenario']==region]);b=metrics([r for r in subset if r['method']=='lqr' and r['scenario']==region])
                    if a['survived']<b['survived']:reasons.append(f'{region}: survival')
                    limit=1.02 if region=='nominal' else 1.01
                    if region!='latency100' and a['rmse']>limit*b['rmse']:reasons.append(f'{region}: RMSE')
                candidates.append(dict(steps=step,eligible=not reasons,reasons=reasons,**metrics(current)))
            eligible=[x for x in candidates if x['eligible']]
            chosen=min(eligible or candidates,key=lambda x:(x['rmse'],x['steps']))
            selected[f'{arm}-{P["rl_seeds"][pair]}']=dict(chosen,candidates=candidates)
        student=[r for r in subset if r['method']=='student'];initial=[r for r in subset if r['method']=='finetune_0']
        for a,b in zip(student,initial):
            assert (a['speed'],a['path'],a['scenario'])==(b['speed'],b['path'],b['scenario'])
            assert abs(float(a['penalized_rmse'])-float(b['penalized_rmse']))<1e-12
    return selected


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--training',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--split',choices=['dev','evaluation'],required=True);parser.add_argument('--pair',type=int,choices=range(3));parser.add_argument('--selection',type=Path);a=parser.parse_args()
    selection=json.loads(a.selection.read_text())['selected'] if a.selection else None
    if a.split=='evaluation' and selection is None:raise ValueError('frozen DEV selection manifest required')
    if a.pair is not None:shard(a.training,a.pair,a.output,a.split,selection);return
    assert json.loads((a.training/'complete.json').read_text())['protocol']==P
    a.output.mkdir(parents=True,exist_ok=False)
    def job(i):
        env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        out=a.output/f'seed-{P["rl_seeds"][i]}'
        command=[sys.executable,str(HERE/'evaluate9.py'),'--training',str(a.training),'--output',str(out),'--pair',str(i),'--split',a.split]
        if a.selection:command+=['--selection',str(a.selection)]
        with (a.output/f'{i}.log').open('w') as f:subprocess.run(command,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
        with (out/'episodes.csv').open() as f:return list(csv.DictReader(f))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=[r for shard_rows in pool.map(job,range(3)) for r in shard_rows]
    assert len(rows)==(1188 if a.split=='dev' else 756)
    with (a.output/'episodes.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
    if a.split=='dev':(a.output/'selection.json').write_text(json.dumps(dict(protocol=P,selected=select(rows)),indent=2)+'\n')
    (a.output/'complete.json').write_text(json.dumps(dict(episodes=len(rows),protocol=P,split=a.split),indent=2)+'\n')


if __name__=='__main__':main()
