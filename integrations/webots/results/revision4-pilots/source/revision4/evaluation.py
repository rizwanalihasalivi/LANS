"""Same paired surrogate cells, with a separately labeled full-command reference."""
import csv,gzip,json,math,time
import numpy as np
from bootstrap import RESEARCH
from core import Sensor,Supervisor,GAINS,path_values
from tracking import tracking_lqr
from gating import Gate
from plant import advance
from geometry import corridor_margin
PROTOCOL=json.loads((RESEARCH/'revision2/protocol.json').read_text())
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
        elif method=='standalone_full_reference':
            command=output[2] if output is not None else 0.
            reason='standalone_full_hold'
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
