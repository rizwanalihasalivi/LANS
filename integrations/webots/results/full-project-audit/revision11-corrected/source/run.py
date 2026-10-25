"""Common-state shadow gate and realized objective attribution, not optimization."""
import argparse,csv,json,sys,itertools,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;R=HERE.parent
sys.path.insert(0,str(R/'revision8'))
import bootstrap
import numpy as np
from numba import njit
from teacher import features
from student import load
from kernels import measure,lqr,execution_step,path_values,initial_executor
from plant import advance
from gating import Gate,predict_cost
from comparison import configure_lqr
from core import GAINS
P=json.loads((HERE/'protocol.json').read_text());G=json.loads((R/'revision6/protocol.json').read_text())

@njit(cache=True)
def branch(state,estimate,cov,previous,tick,command,horizon,actual,speed,path,mu,stiffness,noise,gains):
 z=state.copy();est=estimate.copy();variance=cov.copy();raw=previous.copy();total=0.;lateral=0.
 for j in range(horizon):
  # Current observation is already assimilated; future measurements use paired draws.
  if j>0:est,variance,raw,v,k=measure(z,speed,path,actual[tick+j],0,est,variance,raw,False,noise)
  else:
   v=max(5.,np.float64(np.float32(previous[3]/25))*25);_,_,k=path_values(z[0],path)
  base,gain=lqr(est,v,k,gains);u=command if j<5 else base
  z=advance(z,u,speed,mu,stiffness);y,h,k=path_values(z[0],path);ey=z[1]-y;ep=z[2]-h
  lateral+=ey*ey
  total+=.01*((ey/.5)**2+.2*(ep/.1)**2+.01*((z[4]-speed*k)/.2)**2+.001*(u/.5)**2)
  if abs(ey)>2.5 or abs(ep)>.6 or not np.isfinite(z).all():
   # Diagnostic failed branches are explicit, not assigned arbitrary tracking-cost equality.
   return np.nan,lateral+(horizon-j-1)*6.25,True
 return total+.1*((ey/.5)**2+.2*(ep/.1)**2),lateral,False

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE,text=True).strip()
 configure_lqr();gains=np.array([GAINS[v] for v in (15,20,25)]);allrows=[];episodes=[]
 for rep,region,behavior in itertools.product(P['repetitions'],P['regions'],P['behaviors']):
  case=G['scenarios'][region];path=tuple(float(x) for x in G['paths']['dlc220']);speed=25.;steps=int(np.ceil((220/speed+2)/.01))
  noise_id=P['noise_base']+rep*10000+2510+P['regions'].index(region)
  scales=np.array([.03,np.deg2rad(.17),.01,.1])*case['noise'];actual=np.random.default_rng(noise_id).normal(0,scales,(steps+100,4))
  model=load(R.parent/f'results/revision8-student/students/{[701,802][rep]}')
  y,h,_=path_values(0.,path);state=np.array([0.,y+.15,h+.01,0.,0.,0.]);est=np.zeros(4);cov=np.eye(4)*.01;previous=np.zeros(4);worker=initial_executor()
  shadows={value:Gate({'horizon_steps':20,'relative_margin':.01}) for value in P['candidates_rad']};errors=[];failed=False;proposal=0.
  for tick in range(steps):
   est,cov,previous,v,k=measure(state,speed,path,actual[tick],0,est,cov,previous,tick==0,float(case['noise']));base,gain=lqr(est,v,k,gains)
   for residual,shadow in shadows.items():
    prior=shadow.weight;chosen,w,reason,j0,j1=shadow.choose(tick*.01,base,(tick+1,tick*.01,residual),est,state[5],v,k,gain,'residual')
    if tick%P['sample_every_ticks']:continue
    candidates=[]
    for limit in (.1,.25,.5):
     weight=min(limit,prior+.05)
     if weight not in candidates:candidates.append(weight)
    for horizon in P['branch_horizons_ticks']:
     c0,l0,f0=branch(state,est,cov,previous,tick,base,horizon,actual,speed,path,case['mu'],case['stiffness'],float(case['noise']),gains)
     # Include actual chosen action separately; rejected/persistence decisions execute baseline.
     for index,weight in enumerate(candidates+[-1.]):
      command=chosen if weight<0 else (1-weight)*base+weight*float(np.clip(base+residual,-.5,.5))
      c1,l1,f1=branch(state,est,cov,previous,tick,command,horizon,actual,speed,path,case['mu'],case['stiffness'],float(case['noise']),gains)
      pred0=predict_cost(est,state[5],base,v,k,gain,20);pred1=predict_cost(est,state[5],command,v,k,gain,20)
      allrows.append(dict(repetition=rep,noise_id=noise_id,region=region,behavior=behavior,tick=tick,residual_rad=residual,horizon_ticks=horizon,kind='executed' if weight<0 else 'available',weight=w if weight<0 else weight,reason=reason,baseline_rad=base,command_rad=command,predicted_delta=pred0-pred1,realized_delta=c0-c1,lateral_delta=l0-l1,baseline_realized_cost=c0,baseline_lateral_cost=l0,failed_baseline=f0,failed_candidate=f1))
   if behavior=='student' and tick%5==0:
    action,_=model.predict(features(state,est,max(5.,speed+actual[tick,3]),path,worker,tick,0));proposal=.08*float(action[0])
   command,w,_,_=execution_step(worker,tick*.01,proposal,0,base,est,state[5],v,k,gain,False,tick%5==0)
   old=state[5];state=advance(state,command,speed,case['mu'],case['stiffness']);assert abs(state[5]-old)<=.003500001
   y,h,_=path_values(state[0],path);errors.append(state[1]-y)
   if abs(errors[-1])>2.5 or abs(state[2]-h)>.6 or not np.isfinite(state).all():failed=True;break
  episodes.append(dict(repetition=rep,region=region,behavior=behavior,noise_id=noise_id,survived=not failed,steps=len(errors),scheduled_steps=steps,penalized_rmse=float(np.sqrt((sum(x*x for x in errors)+(steps-len(errors))*6.25)/steps))))
  print(rep,region,behavior,len(allrows),flush=True)
 for name,rows in [('branches',allrows),('episodes',episodes)]:
  with (a.output/(name+'.csv')).open('w') as f:
   writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
 (a.output/'complete.json').write_text(json.dumps(dict(trajectories=len(episodes),branch_rows=len(allrows),protocol=P,source_commit=source_commit,submission_semantics='fresh-query-only-v1'),indent=2)+'\n')
if __name__=='__main__':main()
