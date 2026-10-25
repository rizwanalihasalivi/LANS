"""Saved-model/optimizer audit and original-object replay of final actor decisions."""
import argparse,csv,gzip,hashlib,json
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
from bootstrap import RESEARCH
from policy9 import P,FrozenStudent,logits
from evaluate9 import G,load_checkpoint,STUDENTS
from core import Sensor,path_values
from execution import Execution,matched_lqr
from comparison import configure_lqr
from plant import advance


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    torch.set_num_threads(1);configure_lqr();checks=[];models=[]
    real=torch.from_numpy(np.load(RESEARCH.parent/'results/revision8-student/data/dev.npz')['x'])
    for pair in range(3):
        student=FrozenStudent(STUDENTS/str(P['student_seeds'][pair]));initial={}
        for arm in P['arms']:
            for step in P['checkpoints']:
                adapter=load_checkpoint(a.run/'training',arm,pair,step);model=adapter.model
                assert model.seed==P['rl_seeds'][pair] and model.num_timesteps==step
                norm=model.policy.features_extractor
                assert torch.equal(norm.mean,student.mean) and torch.equal(norm.std,student.std)
                values=[float(s['step'].item()) for s in model.policy.optimizer.state.values() if 'step' in s]
                meta=json.loads((a.run/'training'/f'{arm}-{P["rl_seeds"][pair]}'/f'checkpoint-{step}/complete.json').read_text())
                assert max(values,default=0)==meta['optimizer_steps']
                if step==0:
                    initial[arm]=model
                    assert not values
                    if arm=='finetune':
                        with torch.no_grad():np.testing.assert_array_equal(logits(model,real).numpy(),student(real).numpy())
                else:assert values and max(values)>0
                models.append(dict(arm=arm,pair=pair,step=step,optimizer_steps=max(values,default=0)))
        for k,v in initial['scratch'].policy.mlp_extractor.value_net.state_dict().items():assert torch.equal(v,initial['finetune'].policy.mlp_extractor.value_net.state_dict()[k])
        assert torch.equal(initial['scratch'].policy.value_net.weight,initial['finetune'].policy.value_net.weight)
    selection=json.loads((a.run/'dev/selection.json').read_text())['selected'];pair=0
    for method in ('student','finetune_selected','finetune_100k','scratch_selected'):
        if method=='student':model=FrozenStudent(STUDENTS/str(P['student_seeds'][pair]))
        else:
            arm,tag=method.split('_');step=100000 if tag=='100k' else selection[f'{arm}-{P["rl_seeds"][pair]}']['steps']
            model=load_checkpoint(a.run/'training',arm,pair,step)
        for region in ('nominal','sensor_stress','latency20','latency100'):
            speed=25;path_name='dlc220';case=G['scenarios'][region];path=tuple(float(v) for v in G['paths'][path_name])
            noise_id=P['splits']['evaluation']+speed*100+10+list(G['scenarios']).index(region)
            sensor=Sensor(noise_id,case['noise'],case['sensor_delay_steps']);worker=Execution()
            y,h,_=path_values(0,path);state=np.array([0.,y+.15,h+.01,0.,0.,0.])
            file=a.run/f'evaluation/seed-{P["rl_seeds"][pair]}/traces'/f'{region}-{method}.csv.gz'
            with gzip.open(file,'rt') as f:rows=list(csv.DictReader(f))
            max_input=0.;max_state=0.;max_command=0.;predictions=0
            for tick,r in enumerate(rows):
                obs,estimate,k=sensor.measure(state,speed,path)
                inputs=np.r_[obs,worker.context(tick*.01),case['service_ticks']/10].astype(np.float32)
                stored=np.array([float(r[f'obs{i}']) for i in range(20)],dtype=np.float32)
                max_input=max(max_input,float(np.max(np.abs(inputs-stored))));assert np.allclose(inputs,stored,rtol=0,atol=1e-6)
                available=worker.pending is None or worker.pending[0]<=tick*.01+1e-9
                proposal=0.
                if available:
                    action,_=model.predict(inputs,deterministic=True);proposal=.08*float(np.clip(action[0],-1,1));predictions+=1
                assert abs(proposal-float(r['proposal']))<1e-9
                baseline,gain=matched_lqr(estimate,max(5.,float(obs[4])*25),k)
                command,_=worker.step(tick*.01,proposal,case['service_ticks'],baseline,estimate,state[5],max(5.,float(obs[4])*25),k,gain)
                state=advance(state,command,speed,case['mu'],case['stiffness'])
                difference=max(abs(state[0]-float(r['x'])),abs(state[1]-float(r['y'])),abs(state[5]-float(r['actuator'])))
                max_state=max(max_state,difference);max_command=max(max_command,abs(command-float(r['command'])))
                assert difference<1e-8 and abs(command-float(r['command']))<1e-8
            checks.append(dict(method=method,scenario=region,steps=len(rows),predictions=predictions,max_observation_difference=max_input,max_state_difference=max_state,max_command_difference=max_command))
    (a.run/'independent-verification.json').write_text(json.dumps(dict(verified=True,saved_models=models,replays=checks,step0_real_dev_rows=len(real)),indent=2)+'\n')
    print('24 saved model audits; full DEV logit parity for all3 transfers;16 original-object replays passed.')


if __name__=='__main__':main()
