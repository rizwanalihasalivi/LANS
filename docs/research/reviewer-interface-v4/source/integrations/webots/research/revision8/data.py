"""Episode-grouped independent train/dev labels; no final evaluation data read."""
import argparse,concurrent.futures,itertools,json,os,subprocess,sys
from pathlib import Path
import numpy as np
from numba import njit
from bootstrap import HERE,RESEARCH
from teacher import choose,features
from kernels import measure,lqr,execution_step,path_values
from plant import advance
from comparison import configure_lqr
from core import GAINS
P=json.loads((HERE/'protocol.json').read_text());G=json.loads((RESEARCH/'revision6/protocol.json').read_text())


@njit(cache=True)
def collect(speed,path,case,actual,forecasts,random_classes,gains,behavior,scheduled):
    mu,stiffness,noise_scale=case[:3];delay=int(case[3]);service=int(case[4])
    y,h,_=path_values(0.,path);state=np.array([0.,y+.15,h+.01,0.,0.,0.])
    estimate=np.zeros(4);cov=np.eye(4)*.01;previous=np.zeros(4);worker=np.zeros(12)
    worker[2]=-1.;worker[3]=-1.;worker[7]=-1.
    x=np.empty((scheduled,20),np.float32);costs=np.empty((scheduled,5));labels=np.empty(scheduled,np.int64);ticks=np.empty(scheduled,np.int64)
    candidates=np.array([-.08,-.04,0.,.04,.08]);count=0;errors=np.empty(scheduled);failed=False
    for tick in range(scheduled):
        raw_speed=max(5.,previous[3]) if delay and tick>0 else max(5.,speed+actual[tick,3])
        estimate,cov,previous,v,k=measure(state,speed,path,actual[tick],delay,estimate,cov,previous,tick==0,noise_scale)
        available=worker[7]<0 or worker[6]<=tick*.01+1e-9
        if available and tick%5==0:
            target,values=choose(state,estimate,cov,previous,worker,tick,service,speed,path,mu,stiffness,forecasts[tick],delay,noise_scale,v,k,gains)
            x[count]=features(state,estimate,raw_speed,path,worker,tick,service);costs[count]=values;labels[count]=target;ticks[count]=tick;count+=1
        proposal=0. if behavior==0 else -.04 if behavior==1 else candidates[random_classes[tick]]
        baseline,gain=lqr(estimate,v,k,gains)
        command,_,_,_=execution_step(worker,tick*.01,proposal,service,baseline,estimate,state[5],v,k,gain,False)
        state=advance(state,command,speed,mu,stiffness)
        ref,heading,_=path_values(state[0],path);errors[tick]=state[1]-ref
        if abs(errors[tick])>2.5 or abs(state[2]-heading)>.6 or not np.isfinite(state).all():
            failed=True;return x[:count],costs[:count],labels[:count],ticks[:count],errors[:tick+1],failed
    return x[:count],costs[:count],labels[:count],ticks[:count],errors,failed


def noise_inputs(base,repetition,speed,path_index,region_index,case,scheduled,behavior=0):
    noise_id=base+repetition*10000+speed*100+path_index*10+region_index
    scales=np.array([.03,np.deg2rad(.17),.01,.1])*case['noise']
    actual=np.random.default_rng(noise_id).normal(0,scales,size=(scheduled,4))
    forecasts=np.random.default_rng(noise_id+70000000+behavior*1000000).normal(0,scales,size=(scheduled,21,4))
    actions=np.random.default_rng(noise_id+50000000).integers(0,5,size=scheduled)
    return noise_id,actual,forecasts,actions


def shard(split,repetition,out):
    configure_lqr();gains=np.array([GAINS[v] for v in (15,20,25)]);out.mkdir(parents=True,exist_ok=False)
    arrays={k:[] for k in ('x','costs','labels','ticks','groups')};episodes=[]
    for speed,path_name,region,behavior in itertools.product(G['speeds'],G['paths'],G['scenarios'],range(3)):
        case=G['scenarios'][region];path=tuple(float(v) for v in G['paths'][path_name]);scheduled=int(np.ceil((220/speed+2)/.01))
        noise_id,actual,forecast,actions=noise_inputs(P['splits'][split]['noise_base'],repetition,speed,list(G['paths']).index(path_name),list(G['scenarios']).index(region),case,scheduled,behavior)
        parameters=np.array([case['mu'],case['stiffness'],case['noise'],case['sensor_delay_steps'],case['service_ticks']],dtype=float)
        x,costs,labels,ticks,errors,failed=collect(float(speed),path,parameters,actual,forecast,actions,gains,behavior,scheduled)
        group=len(episodes)
        for key,value in [('x',x),('costs',costs),('labels',labels),('ticks',ticks),('groups',np.full(len(x),group))]:arrays[key].append(value)
        episodes.append(dict(group=group,noise_id=noise_id,repetition=repetition,speed=speed,path=path_name,scenario=region,behavior=behavior,
            rows=len(x),survived=not failed,steps=len(errors),scheduled_steps=scheduled,
            penalized_rmse=float(np.sqrt((sum(errors**2)+(scheduled-len(errors))*6.25)/scheduled))))
        print(split,repetition,speed,path_name,region,behavior,'labels',len(x),flush=True)
    np.savez_compressed(out/'labels.npz',**{k:np.concatenate(v) for k,v in arrays.items()})
    (out/'episodes.json').write_text(json.dumps(episodes,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--split',choices=['train','dev']);parser.add_argument('--repetition',type=int);a=parser.parse_args()
    if a.split is not None:shard(a.split,a.repetition,a.output);return
    a.output.mkdir(parents=True,exist_ok=False)
    def job(split,repetition):
        out=a.output/f'{split}-{repetition}';env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        with (a.output/f'{split}-{repetition}.log').open('w') as f:
            subprocess.run([sys.executable,str(HERE/'data.py'),'--output',str(out),'--split',split,'--repetition',str(repetition)],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
        print('label shard complete',split,repetition,flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(job,split,i) for split in ('train','dev') for i in range(P['splits'][split]['noise_repetitions'])]
        for f in futures:f.result()
    counts={}
    for split in ('train','dev'):
        arrays={k:[] for k in ('x','costs','labels','ticks','groups')};episodes=[]
        for i in range(P['splits'][split]['noise_repetitions']):
            folder=a.output/f'{split}-{i}';part=json.loads((folder/'episodes.json').read_text());offset=len(episodes)
            with np.load(folder/'labels.npz') as z:
                for k in arrays:arrays[k].append(z[k]+offset if k=='groups' else z[k])
            for row in part:row['group']+=offset
            episodes.extend(part)
        merged={k:np.concatenate(v) for k,v in arrays.items()}
        np.savez_compressed(a.output/f'{split}.npz',**merged)
        (a.output/f'{split}-episodes.json').write_text(json.dumps(episodes,indent=2)+'\n')
        counts[split]=dict(episodes=len(episodes),rows=len(merged['x']),classes=np.bincount(merged['labels'],minlength=5).tolist())
    (a.output/'complete.json').write_text(json.dumps(dict(protocol=P,counts=counts,future_actual_noise_used=False),indent=2)+'\n')


if __name__=='__main__':main()
