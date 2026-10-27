"""Separate development, configuration freeze, and one-shot reserved evaluation."""
import argparse,csv,gzip,hashlib,itertools,json,math,sys,time
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
HERE=Path(__file__).resolve().parent
PARENT=HERE.parent
sys.path.insert(0,str(PARENT))
from core import Sensor,Supervisor,GAINS,path_values
from comparison import configure_lqr
from tracking import tracking_lqr
from geometry import corridor_margin
from gating import Gate
from plant import advance
PROTOCOL=json.loads((HERE/'protocol.json').read_text())
TRAINING=PARENT.parent/'results/research-training'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def sources():
    files=[HERE/n for n in ['run.py','gating.py','plant.py','test_gate.py','protocol.json']]
    files += [PARENT/n for n in ['core.py','protocol.json','comparison.py','comparison-protocol.json','tracking.py','tracking-protocol.json','geometry.py']]
    return {str(p.relative_to(PARENT)):digest(p) for p in files}
def models(seed):
    result={}
    for role in ['full','residual']:
        folder=TRAINING/f'{role}-{seed}';meta=json.loads((folder/'complete.json').read_text())
        assert meta['steps']==1000000 and meta['seed']==seed
        assert digest(folder/'policy.zip')==meta['policy_sha256']
        result[role]=PPO.load(folder/'policy.zip',device='cpu')
        assert result[role].num_timesteps==1000000
    return result

def episode(model,method,seed,speed,path_name,scenario_name,config,base,trace):
    scenario=PROTOCOL['scenarios'][scenario_name];path=tuple(PROTOCOL['paths'][path_name])
    y,heading,_=path_values(0,path);state=np.array([0.,y+.15,heading+.01,0.,0.,0.])
    # Same stream across methods/configs; distinct paths/scenarios, fresh split bases.
    noise_seed=base+seed*10000+speed*100+list(PROTOCOL['paths']).index(path_name)*10+list(PROTOCOL['scenarios']).index(scenario_name)
    sensor=Sensor(noise_seed,noise=scenario['noise'],delay_steps=scenario['sensor_delay_steps'])
    gate=Gate(config);old=Supervisor();pending=None;output=None;sequence=0
    errors=[];weights=[];age_values=[];wall=[];reasons={};margins=[];rates=[];trace_rows=[];prediction_checks=[]
    steps=math.ceil((220/speed+2)/.01);survived=True
    for i in range(steps):
        t=i*.01;obs,estimate,kappa=sensor.measure(state,speed,path);baseline=tracking_lqr(estimate,speed,kappa)
        if pending is not None and pending[0]<=t+1e-9:output=pending[1];pending=None
        if model is not None and pending is None:
            start=time.perf_counter();action,_=model.predict(obs,deterministic=True);sequence+=1
            packet=(sequence,t,float(action[0])*.5)
            if scenario['service_ms']==0:output=packet
            else:pending=(t+scenario['service_ms']/1000,packet)
            wall.append(time.perf_counter()-start)
        age=t-output[1] if output is not None else math.nan;j0=j1=math.nan;weight=0.;reason='baseline'
        started=time.perf_counter()
        if method=='lqr':command=baseline
        elif method=='old_fusion':command,weight,reason=old.fuse(t,baseline,output,estimate)
        elif method=='residual':
            weight=math.exp(-max(0.,age-.005)/.02) if output is not None else 0.
            command=baseline+weight*output[2] if output is not None else baseline
            reason='ungated'
        else:
            command,weight,reason,j0,j1=gate.choose(t,baseline,output,estimate,state[5],speed,kappa,GAINS[speed],
                                                  'residual' if method=='gated_residual' else 'full')
            prediction_checks.append(time.perf_counter()-started)
            if weight>0:assert j1<j0 and reason=='earned' and age<.05
        command=float(np.clip(command,-.5,.5));previous=state[5]
        state=advance(state,command,speed,scenario['mu'],scenario['stiffness'])
        ey=state[1]-path_values(state[0],path)[0];ep=state[2]-path_values(state[0],path)[1]
        errors.append(ey);weights.append(weight);rates.append(abs(state[5]-previous)/.01)
        margins.append(corridor_margin(state[0],state[1],state[2],path));reasons[reason]=reasons.get(reason,0)+1
        if output is not None:age_values.append(age)
        if trace:trace_rows.append([i,t,t+.01,state[0],state[1],state[2],ey,command,state[5],baseline,age,weight,j0,j1,reason])
        if abs(ey)>2.5 or abs(ep)>.6 or not np.isfinite(state).all():survived=False;break
    if trace:
        with gzip.open(trace,'wt',newline='') as f:
            writer=csv.writer(f);writer.writerow(['step','command_time_s','state_time_s','x_m','y_m','heading_rad','error_m','command_rad','actuator_rad','lqr_rad','age_s','weight','predicted_lqr_cost','predicted_candidate_cost','reason']);writer.writerows(trace_rows)
    assert max(rates)<=.3500001
    return dict(seed=seed,noise_seed=noise_seed,speed=speed,path=path_name,scenario=scenario_name,method=method,
                survived=survived,steps=len(errors),scheduled_steps=steps,rmse=float(np.sqrt(np.mean(np.square(errors)))),
                penalized_rmse=float(np.sqrt((sum(e*e for e in errors)+(steps-len(errors))*6.25)/steps)),
                active_fraction=float(np.mean(np.array(weights)>0)),mean_weight=float(np.mean(weights)),
                max_rate=max(rates),corridor_violation_fraction=float(np.mean(np.array(margins)<0)),
                age_p99=float(np.quantile(age_values,.99)) if age_values else 0.,
                inference_wall_p99=float(np.quantile(wall,.99)) if wall else 0.,
                gate_wall_p99=float(np.quantile(prediction_checks,.99)) if prediction_checks else 0.,reasons=json.dumps(reasons,sort_keys=True))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['develop','test']);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--freeze',type=Path);args=parser.parse_args()
    torch.set_num_threads(1);torch.set_num_interop_threads(1);configure_lqr()
    current=sources();frozen=None
    if args.phase=='test':
        assert args.freeze,'Test requires a prior development freeze'
        frozen=json.loads(args.freeze.read_text());assert frozen['source_sha256']==current,'Source changed after development freeze'
        configs=[frozen['selected_config']];seeds=PROTOCOL['test_policy_seeds'];speeds=PROTOCOL['test_speeds'];paths=PROTOCOL['test_paths'];base=PROTOCOL['reserved_test_noise_base']
    else:configs=PROTOCOL['candidates'];seeds=PROTOCOL['development_policy_seeds'];speeds=PROTOCOL['development_speeds'];paths=PROTOCOL['development_paths'];base=PROTOCOL['development_noise_base']
    policy_hashes={f'{r}-{s}':digest(TRAINING/f'{r}-{s}/policy.zip') for s in PROTOCOL['test_policy_seeds'] for r in ['full','residual']}
    if frozen:assert frozen['policy_sha256']==policy_hashes
    args.output.mkdir(parents=True,exist_ok=False);(args.output/'traces').mkdir();(args.output/'source').mkdir()
    for name in current:
        target=args.output/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((PARENT/name).read_bytes())
    (args.output/'start.json').write_text(json.dumps(dict(phase=args.phase,source_sha256=current,policy_sha256=policy_hashes,freeze_sha256=digest(args.freeze) if args.freeze else None),indent=2)+'\n')
    rows=[]
    with (args.output/'episodes.csv').open('w',newline='') as f:
        writer=None
        for seed in seeds:
            loaded=models(seed)
            for speed,path,scenario in itertools.product(speeds,paths,PROTOCOL['scenarios']):
                methods=PROTOCOL['methods'] if args.phase=='test' else ['lqr','gated_residual']
                for method in methods:
                    for index,config in enumerate(configs if method.startswith('gated') else configs[:1]):
                        model=None if method=='lqr' else loaded['residual' if 'residual' in method else 'full']
                        trace=args.output/'traces'/f'{method}-{scenario}.csv.gz' if args.phase=='test' and seed==0 and speed==25 and path=='dlc220' else None
                        row=episode(model,method,seed,speed,path,scenario,config,base,trace);row['config_index']=index
                        if writer is None:writer=csv.DictWriter(f,fieldnames=row);writer.writeheader()
                        writer.writerow(row);f.flush();rows.append(row)
            print(f'{args.phase}: seed {seed} completed, {len(rows)} episodes',flush=True)
    assert sources()==current
    if args.phase=='develop':
        baseline=[r for r in rows if r['method']=='lqr'];bnom=np.mean([r['penalized_rmse'] for r in baseline if r['scenario']=='nominal'])
        rankings=[]
        for index,config in enumerate(configs):
            subset=[r for r in rows if r['method']=='gated_residual' and r['config_index']==index]
            nominal=np.mean([r['penalized_rmse'] for r in subset if r['scenario']=='nominal'])
            eligible=sum(r['survived'] for r in subset)>=sum(r['survived'] for r in baseline) and nominal<=1.02*bnom
            rankings.append(dict(config=config,eligible=bool(eligible),mean_rmse=float(np.mean([r['penalized_rmse'] for r in subset])),nominal_ratio=float(nominal/bnom)))
        selected=min(rankings,key=lambda r:(not r['eligible'],r['mean_rmse']))
        freeze=dict(selected_config=selected['config'],development_accepted=selected['eligible'],rankings=rankings,source_sha256=current,policy_sha256=policy_hashes,development_csv_sha256=digest(args.output/'episodes.csv'),protocol=PROTOCOL)
        (args.output/'freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
    (args.output/'complete.json').write_text(json.dumps(dict(episodes=len(rows),source_sha256=current,episodes_sha256=digest(args.output/'episodes.csv')),indent=2)+'\n')
if __name__=='__main__':main()
