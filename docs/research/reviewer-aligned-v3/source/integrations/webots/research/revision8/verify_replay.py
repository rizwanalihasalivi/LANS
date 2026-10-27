"""Replay actual saved student inputs/actions with original Sensor/Execution objects."""
import argparse,csv,gzip,json
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
from bootstrap import RESEARCH
from core import Sensor,path_values
from execution import Execution,matched_lqr
from comparison import configure_lqr
from plant import advance
from student import load,P


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);a=parser.parse_args()
    torch.set_num_threads(1);configure_lqr();grid=json.loads((RESEARCH/'revision6/protocol.json').read_text())
    student=load(a.run/'students/701')
    previous=PPO.load(RESEARCH.parent/'results/revision6-correction/training/execution-301/policy.zip',device='cpu')
    checks=[]
    for method in ('student','previous_ppo','teacher'):
        model=student if method=='student' else previous if method=='previous_ppo' else None
        for region in ('nominal','sensor_stress','latency20','latency100'):
            speed=25;path_name='dlc220';case=grid['scenarios'][region];path=tuple(float(v) for v in grid['paths'][path_name])
            noise_id=P['splits']['evaluation']['noise_base']+speed*100+10+list(grid['scenarios']).index(region)
            sensor=Sensor(noise_id,case['noise'],case['sensor_delay_steps']);worker=Execution()
            y,h,_=path_values(0,path);state=np.array([0.,y+.15,h+.01,0.,0.,0.])
            file=a.run/'evaluation/seed-701/traces'/f'{region}-{method}.csv.gz'
            with gzip.open(file,'rt') as f:rows=list(csv.DictReader(f))
            max_input=0.;max_state=0.;max_command=0.;predictions=0;teacher_choices=0
            for tick,r in enumerate(rows):
                obs,estimate,k=sensor.measure(state,speed,path)
                inputs=np.r_[obs,worker.context(tick*.01),case['service_ticks']/10].astype(np.float32)
                stored=np.array([float(r[f'obs{i}']) for i in range(20)],dtype=np.float32)
                max_input=max(max_input,float(np.max(np.abs(inputs-stored))))
                assert np.allclose(inputs,stored,rtol=0,atol=1e-6)
                available=worker.pending is None or worker.pending[0]<=tick*.01+1e-9
                proposal=float(r['proposal'])
                if available and model is not None:
                    action,_=model.predict(inputs,deterministic=True)
                    expected=.08*float(np.clip(action[0],-1,1));assert abs(expected-proposal)<1e-9;predictions+=1
                if available and method=='teacher':
                    costs=np.array([float(r[f'cost{i}']) for i in range(5)])
                    index=int(r['teacher_selected']);best=float(costs.min())
                    if costs[2]-best<=max(1e-7,.001*costs[2]):assert index==2
                    else:assert costs[index]==best
                    assert proposal==P['candidates_rad'][index];teacher_choices+=1
                baseline,gain=matched_lqr(estimate,max(5.,float(obs[4])*25),k)
                command,_=worker.step(tick*.01,proposal,case['service_ticks'],baseline,estimate,state[5],max(5.,float(obs[4])*25),k,gain)
                state=advance(state,command,speed,case['mu'],case['stiffness'])
                state_error=max(abs(state[0]-float(r['x'])),abs(state[1]-float(r['y'])),abs(state[5]-float(r['actuator'])))
                max_state=max(max_state,state_error);max_command=max(max_command,abs(command-float(r['command'])))
                assert state_error<1e-8 and abs(command-float(r['command']))<1e-8
            checks.append(dict(method=method,scenario=region,steps=len(rows),predictions_checked=predictions,
                teacher_choices_checked=teacher_choices,max_observation_difference=max_input,max_state_difference=max_state,max_command_difference=max_command))
    (a.run/'independent-replay.json').write_text(json.dumps(dict(verified=True,cases=checks),indent=2)+'\n')
    print('Twelve original-object replays verified, including actual saved student predictions.')


if __name__=='__main__':main()
