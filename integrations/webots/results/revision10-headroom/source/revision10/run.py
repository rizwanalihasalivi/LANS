"""Fixed small development diagnostic; reuse original gate/observer/plant."""
import argparse,csv,json,sys,itertools,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;RESEARCH=HERE.parent
sys.path.insert(0,str(RESEARCH/'revision8'))
import bootstrap
import numpy as np
from numba import njit
from teacher import features
from student import load
from kernels import measure,lqr,execution_step,path_values,initial_executor
from plant import advance
from comparison import configure_lqr
from core import GAINS
P=json.loads((HERE/'protocol.json').read_text());G=json.loads((RESEARCH/'revision6/protocol.json').read_text())

@njit(cache=True)
def cost(state,estimate,cov,previous,worker,tick,first,second,horizon,service,speed,path,mu,stiffness,forecast,delay,noise,v,k,gains):
 total=0.
 for sign in (0.,1.,-1.):
  z=state.copy();est=estimate.copy();variance=cov.copy();raw=previous.copy();ex=worker.copy();mv=v;curve=k;value=0.
  for j in range(horizon):
   baseline,gain=lqr(est,mv,curve,gains)
   u,_,_,_=execution_step(ex,(tick+j)*.01,first if j<20 else second,service,baseline,est,z[5],mv,curve,gain,False)
   z=advance(z,u,speed,mu,stiffness);y,h,_=path_values(z[0],path);ey=z[1]-y;value+=ey*ey
   if abs(ey)>2.5 or abs(z[2]-h)>.6 or not np.isfinite(z).all():value+=(horizon-j-1)*6.25;break
   if j<horizon-1:est,variance,raw,mv,curve=measure(z,speed,path,sign*forecast[j+1],delay,est,variance,raw,False,noise)
  total+=value
 return total/3

@njit(cache=True)
def choose(state,estimate,cov,previous,worker,tick,mode,service,speed,path,mu,stiffness,forecast,delay,noise,v,k,gains):
 grid=np.array([-.08,-.04,0.,.04,.08]);horizon=20 if mode==0 else 40;values=np.empty(5)
 for i in range(5):values[i]=cost(state,estimate,cov,previous,worker,tick,grid[i],grid[i],horizon,service,speed,path,mu,stiffness,forecast,delay,noise,v,k,gains)
 zero=values[2];best=2;bestcost=zero
 if mode==2:
  order=np.argsort(values);indices=order[:2]
  for i in indices:
   for j in range(5):
    value=cost(state,estimate,cov,previous,worker,tick,grid[i],grid[j],40,service,speed,path,mu,stiffness,forecast,delay,noise,v,k,gains)
    if value<bestcost or (value==bestcost and abs(grid[i])<abs(grid[best])):best=i;bestcost=value
 else:
  for i in range(5):
   if values[i]<bestcost or (values[i]==bestcost and abs(grid[i])<abs(grid[best])):best=i;bestcost=values[i]
 if zero-bestcost<=max(1e-7,.001*zero):best=2
 return grid[best]

def episode(method,rep,region,model,gains):
 case=G['scenarios'][region];speed=25.;path=tuple(float(v) for v in G['paths']['dlc220']);scheduled=int(np.ceil((220/speed+2)/.01))
 identity=P['noise_base']+rep*10000+2500+10+P['scenarios'].index(region)
 scales=np.array([.03,np.deg2rad(.17),.01,.1])*case['noise']
 actual=np.random.default_rng(identity).normal(0,scales,(scheduled,4))
 forecasts=np.random.default_rng(identity+P['forecast_offset']).normal(0,scales,(scheduled,41,4))
 y,h,_=path_values(0.,path);state=np.array([0.,y+.15,h+.01,0.,0.,0.]);est=np.zeros(4);cov=np.eye(4)*.01;previous=np.zeros(4);worker=initial_executor()
 errors=[];proposal=0.;calls=0;maxrate=0.;active=0;failed=False;started=time.perf_counter()
 for tick in range(scheduled):
  raw_v=max(5.,previous[3]) if case['sensor_delay_steps'] and tick else max(5.,speed+actual[tick,3])
  est,cov,previous,v,k=measure(state,speed,path,actual[tick],case['sensor_delay_steps'],est,cov,previous,tick==0,float(case['noise']))
  baseline,gain=lqr(est,v,k,gains)
  available=worker[7]<0 or worker[6]<=tick*.01+1e-9
  if available and tick%5==0:
   if method=='student':a,_=model.predict(features(state,est,raw_v,path,worker,tick,case['service_ticks']));proposal=.08*float(a[0])
   elif method=='fixed_m004':proposal=-.04
   elif method!='lqr':
    proposal=choose(state,est,cov,previous,worker,tick,['hold20','hold40','sequence40'].index(method),case['service_ticks'],speed,path,case['mu'],case['stiffness'],forecasts[tick],case['sensor_delay_steps'],float(case['noise']),v,k,gains);calls+=1
  u,w,_,_=execution_step(worker,tick*.01,proposal,case['service_ticks'],baseline,est,state[5],v,k,gain,False)
  if region=='latency100':assert u==baseline and w==0
  old=state[5];state=advance(state,u,speed,case['mu'],case['stiffness']);maxrate=max(maxrate,abs(state[5]-old)/.01);active+=w>0
  y,h,_=path_values(state[0],path);ey=state[1]-y;errors.append(ey)
  if abs(ey)>2.5 or abs(state[2]-h)>.6 or not np.isfinite(state).all():failed=True;break
 assert maxrate<=.3500001
 return dict(repetition=rep,noise_id=identity,scenario=region,method=method,survived=not failed,steps=len(errors),scheduled_steps=scheduled,penalized_rmse=float(np.sqrt((sum(e*e for e in errors)+(scheduled-len(errors))*6.25)/scheduled)),active_fraction=active/len(errors),teacher_calls=calls,wall_s=time.perf_counter()-started)

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 configure_lqr();gains=np.array([GAINS[v] for v in (15,20,25)]);rows=[]
 for rep in P['repetitions']:
  model=load(RESEARCH.parent/f'results/revision8-student/students/{P["student_seeds"][rep]}')
  for region,method in itertools.product(P['scenarios'],P['methods']):
   row=episode(method,rep,region,model,gains);rows.append(row)
   with (a.output/'episodes.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
   print(rep,region,method,row['penalized_rmse'],flush=True)
 (a.output/'complete.json').write_text(json.dumps(dict(episodes=len(rows),protocol=P),indent=2)+'\n')
if __name__=='__main__':main()
