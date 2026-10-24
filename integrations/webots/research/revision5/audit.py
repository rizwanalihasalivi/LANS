"""Paired nonlearned controls and cloned-state predictor attribution audit."""
import argparse,csv,json,math,hashlib,itertools,sys
from pathlib import Path
import numpy as np
from numba import njit
from bootstrap import HERE,RESEARCH,ROOT
sys.path.append(str(RESEARCH/'revision4'))
from evaluation import episode
from core import Sensor,GAINS,path_values,reference
from plant import advance
from gating import Gate,predict_cost
from tracking import tracking_lqr
from mapping import RangeMappedPolicy
from stable_baselines3 import PPO
P=json.loads((HERE/'protocol.json').read_text())
V2=json.loads((RESEARCH/'revision2/protocol.json').read_text())
CONFIG={'horizon_steps':20,'relative_margin':.01}


class Candidate:
    def __init__(self,name):self.name=name
    def predict(self,obs,deterministic=True):
        if self.name=='linear_correction':
            u=float(np.clip(-.04*float(obs[0])*3-.08*float(obs[1])*.3,-.08,.08))
        else:u={'zero':0.,'constant_positive':.08,'constant_negative':-.08}[self.name]
        return np.array([u/.5]),None


@njit(cache=True)
def realized(state,command,speed,path,mu,stiffness,gain):
    z=state.copy();cost=0.
    for tick in range(20):
        y,dy,ddy=reference(z[0],*path);heading=math.atan(dy);kappa=ddy/(1+dy*dy)**1.5
        vyref=(1.4*speed-1650*1.2*speed**3/(2.6*80000))*kappa
        ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*speed**2)*kappa
        est=np.array([z[1]-y,z[3],z[2]-heading,z[4]])
        target=np.array([0.,vyref,-vyref/speed,speed*kappa])
        u=command if tick<5 else max(-.5,min(.5,ff-np.dot(gain,est-target)))
        z=advance(z,u,speed,mu,stiffness)
        y,dy,ddy=reference(z[0],*path);kappa=ddy/(1+dy*dy)**1.5
        ey=z[1]-y;ep=z[2]-math.atan(dy)
        cost+=.01*((ey/.5)**2+.2*(ep/.1)**2+.01*((z[4]-speed*kappa)/.2)**2+.001*(u/.5)**2)
    return cost+.1*((ey/.5)**2+.2*(ep/.1)**2)


def models(seed):
    legacy=ROOT/f'results/research-training/residual-{0 if seed==101 else 1}/policy.zip'
    # Original campaign model filename is recorded in revision4's runner.
    if not legacy.exists():legacy=legacy.with_name('model.zip')
    paths={'legacy':legacy,'A100k':ROOT/f'results/revision4-pilots/training/A-{seed}/policy.zip'}
    result={n:Candidate(n) for n in P['methods'] if n not in ['lqr','legacy','A100k']}
    result['legacy']=PPO.load(paths['legacy'],device='cpu')
    result['A100k']=RangeMappedPolicy(PPO.load(paths['A100k'],device='cpu'))
    return result,{n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in paths.items()}


def write_csv(path,rows):
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=False)
    sources={str(p.relative_to(RESEARCH)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'audit.py',HERE/'protocol.json',RESEARCH/'revision2/gating.py',RESEARCH/'revision2/plant.py',RESEARCH/'revision4/evaluation.py']}
    (out/'protocol.json').write_text((HERE/'protocol.json').read_text())
    (out/'sources.json').write_text(json.dumps(sources,indent=2)+'\n')
    rows=[];audits=[];hashes={}
    for seed in P['seeds']:
        candidates,model_hashes=models(seed);hashes[str(seed)]=model_hashes
        for speed,path_name,region in itertools.product(P['speeds'],P['paths'],P['scenarios']):
            for name in P['methods']:
                row=episode(None if name=='lqr' else candidates[name],'lqr' if name=='lqr' else 'gated_residual',seed,speed,path_name,region,CONFIG,P['noise_base'],None)
                row['method']=name;rows.append(row)
            if region.startswith('latency'):continue
            scenario=V2['scenarios'][region];path=tuple(V2['paths'][path_name]);y,h,_=path_values(0,path)
            state=np.array([0.,y+.15,h+.01,0.,0.,0.]);sensor=Sensor(P['noise_base']+seed*10000+speed*100+list(V2['paths']).index(path_name)*10+list(V2['scenarios']).index(region),scenario['noise'],scenario['sensor_delay_steps'])
            gates={n:Gate(CONFIG) for n in candidates}
            for tick in range(math.ceil((220/speed+2)/.01)):
                obs,estimate,kappa=sensor.measure(state,speed,path);base=tracking_lqr(estimate,speed,kappa);t=tick*.01
                for name,model in candidates.items():
                    action,_=model.predict(obs,deterministic=True);correction=float(np.clip(float(action[0])*.5,-.08,.08))
                    gate=gates[name];prior_weight=gate.weight
                    u,w,reason,j0,j1=gate.choose(t,base,(tick+1,t,correction),estimate,state[5],speed,kappa,GAINS[speed],'residual')
                    if tick%P['audit_sample_every_ticks']:continue
                    truth=np.array([state[1]-path_values(state[0],path)[0],state[3],state[2]-path_values(state[0],path)[1],state[4]])
                    actual0=realized(state,base,speed,path,scenario['mu'],scenario['stiffness'],GAINS[speed]);best_actual=actual0
                    pred0=predict_cost(estimate,state[5],base,speed,kappa,GAINS[speed],20)
                    ideal0=predict_cost(truth,state[5],base,speed,kappa,GAINS[speed],20)
                    actual_executed=actual0 if w==0 else realized(state,u,speed,path,scenario['mu'],scenario['stiffness'],GAINS[speed])
                    choices=[]
                    for limit in (.1,.25,.5):
                        weight=min(limit,prior_weight+.05);cmd=(1-weight)*base+weight*float(np.clip(base+correction,-.5,.5))
                        actual=realized(state,cmd,speed,path,scenario['mu'],scenario['stiffness'],GAINS[speed]);best_actual=min(best_actual,actual)
                        pred=predict_cost(estimate,state[5],cmd,speed,kappa,GAINS[speed],20)
                        ideal=predict_cost(truth,state[5],cmd,speed,kappa,GAINS[speed],20)
                        choices.append(dict(weight=weight,command_rad=cmd,predicted_delta=pred0-pred,ideal_state_predicted_delta=ideal0-ideal,realized_delta=actual0-actual))
                    tol=max(1e-7,.01*actual0)
                    audits.append(dict(seed=seed,speed=speed,path=path_name,scenario=region,tick=tick,method=name,reason=reason,gate_weight=w,
                        lqr_rad=base,proposed_residual_rad=correction,executed_rad=u,actuator_rad=state[5],
                        predicted_delta=j0-j1,realized_executed_delta=actual0-actual_executed,realized_best_delta=actual0-best_actual,
                        false_accept=bool(w>0 and actual0-actual_executed < -tol),
                        false_reject=bool(reason=='cost' and actual0-best_actual>tol),
                        safety_withheld_helpful=bool(reason not in ('cost','earned') and actual0-best_actual>tol),
                        choices=json.dumps(choices)))
                state=advance(state,base,speed,scenario['mu'],scenario['stiffness'])
                ey=state[1]-path_values(state[0],path)[0];ep=state[2]-path_values(state[0],path)[1]
                if abs(ey)>2.5 or abs(ep)>.6:break
            print(f'completed seed={seed} speed={speed} path={path_name} region={region}',flush=True)
    write_csv(out/'episodes.csv',rows);write_csv(out/'predictor-audit.csv',audits)
    (out/'complete.json').write_text(json.dumps(dict(episodes=len(rows),audited_states_candidates=len(audits),model_hashes=hashes,source_hashes=sources,reserved_evaluated=False),indent=2)+'\n')

if __name__=='__main__':main()
