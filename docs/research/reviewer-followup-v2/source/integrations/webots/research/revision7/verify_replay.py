"""Independent original-object replay of stored gated and bypass trajectories."""
import argparse,csv,gzip,json,math
from pathlib import Path
import numpy as np
from bootstrap import RESEARCH
from core import Sensor,path_values
from comparison import configure_lqr
from execution import Execution,matched_lqr
from plant import advance


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);a=parser.parse_args()
    configure_lqr();grid=json.loads((RESEARCH/'revision6/protocol.json').read_text())
    evidence=[]
    for method in ('oracle_gated','oracle_bypass'):
        for region in ('nominal','sensor_stress','latency20','latency100'):
            seed=301;speed=25;path_name='dlc220';case=grid['scenarios'][region];path=tuple(grid['paths'][path_name])
            noise_seed=grid['development_noise_base']+speed*100+10+list(grid['scenarios']).index(region)
            sensor=Sensor(noise_seed,case['noise'],case['sensor_delay_steps']);worker=Execution()
            y,h,_=path_values(0,path);state=np.array([0.,y+.15,h+.01,0.,0.,0.])
            file=a.run/f'seed-{seed}'/'traces'/f'{speed}-{path_name}-{region}-{method}.csv.gz'
            with gzip.open(file,'rt') as f:rows=list(csv.DictReader(f))
            max_state_error=0.;max_command_error=0.;failed=False
            for tick,r in enumerate(rows):
                obs,estimate,kappa=sensor.measure(state,speed,path);measured=max(5.,float(obs[4])*25)
                baseline,gain=matched_lqr(estimate,measured,kappa)
                command,info=worker.step(tick*.01,float(r['proposal']),case['service_ticks'],baseline,estimate,state[5],measured,kappa,gain)
                if method=='oracle_bypass':
                    packet=worker.packet
                    command=baseline if packet is None or tick*.01-packet[1]<0 or tick*.01-packet[1]>=.05 else float(np.clip(baseline+packet[2],-.5,.5))
                state=advance(state,command,speed,case['mu'],case['stiffness'])
                error=max(abs(state[0]-float(r['x'])),abs(state[1]-float(r['y'])),abs(state[2]-float(r['heading'])),abs(state[5]-float(r['actuator'])))
                max_state_error=max(max_state_error,error);max_command_error=max(max_command_error,abs(command-float(r['command'])))
                assert error<1e-9 and abs(command-float(r['command']))<1e-9
                ref,heading,_=path_values(state[0],path)
                failed=abs(state[1]-ref)>2.5 or abs(state[2]-heading)>.6
                if failed:assert tick==len(rows)-1
            if len(rows)<math.ceil((220/speed+2)/.01):assert failed
            evidence.append(dict(method=method,scenario=region,steps=len(rows),failed=bool(failed),max_state_difference=max_state_error,max_command_difference=max_command_error))
    (a.run/'independent-replay.json').write_text(json.dumps(dict(verified=True,cases=evidence),indent=2)+'\n')
    print('Eight original-object trajectory replays verified, including diagnostic failures.')


if __name__=='__main__':main()
