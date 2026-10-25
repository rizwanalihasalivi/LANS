"""Frozen paired PPO pilot; exact actor transfer, fresh critic and optimizer."""
import argparse,concurrent.futures,csv,json,os,subprocess,sys,time
from pathlib import Path
import torch
from torch import nn
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv,VecNormalize
from stable_baselines3.common.logger import configure
from bootstrap import HERE,RESEARCH
from policy10 import P,FrozenStudent,ObservedStandardizer,copy_actor
from env10 import TrainingEnv
from anchor10 import AnchoredPPO
STUDENTS=RESEARCH.parent/'results/revision8-student/students'


def create_model(env,student,seed,arm):
    cfg=P['ppo']
    model=AnchoredPPO('MlpPolicy',env,anchor_coef=P['anchor']['coefficient'] if arm in P['anchor']['arms'] else 0.,mask_busy=arm in P['credit']['arms'],student_seed=P['student_seeds'][P['rl_seeds'].index(seed)],n_steps=cfg['n_steps'],batch_size=cfg['batch_size'],n_epochs=cfg['n_epochs'],
        learning_rate=cfg['learning_rate'],clip_range=cfg['clip_range'],target_kl=cfg['target_kl'],
        ent_coef=cfg['ent_coef'],vf_coef=cfg['vf_coef'],gamma=cfg['gamma'],gae_lambda=cfg['gae_lambda'],
        seed=seed,device='cpu',verbose=0,policy_kwargs=dict(net_arch=dict(pi=[64,64],vf=[64,64]),activation_fn=nn.Tanh,
        features_extractor_class=ObservedStandardizer,features_extractor_kwargs=dict(mean=student.mean.numpy(),std=student.std.numpy())))
    if arm not in P['arms']:raise ValueError(arm)
    copy_actor(model,student)
    return model


class Diagnostics(BaseCallback):
    def __init__(self,out):super().__init__();self.out=out;self.rows=[];self.count=0;self.active=0;self.sums={};self.regions={}
    def _on_step(self):
        for info in self.locals['infos']:
            self.count+=1;self.active+=info['gate_weight']>0
            self.regions[info['training_region']]=self.regions.get(info['training_region'],0)+1
            for k in ('reward_tracking','reward_effort','reward_change','reward_survival','reward_relative','credit_bonus','training_reward','decision_eligible'):
                self.sums[k]=self.sums.get(k,0.)+info[k]
        return True
    def _on_rollout_end(self):
        b=self.model.rollout_buffer
        row=dict(steps=self.num_timesteps,active_fraction=self.active/self.count,
            advantage_mean=float(b.advantages.mean()),advantage_std=float(b.advantages.std()),return_mean=float(b.returns.mean()),
            **{k:v/self.count for k,v in self.sums.items()})
        self.rows.append(row);(self.out/'progress.json').write_text(json.dumps(row,indent=2)+'\n')


def run(arm,pair,out):
    torch.set_num_threads(1);torch.set_num_interop_threads(1);out.mkdir(parents=True,exist_ok=False)
    seed=P['rl_seeds'][pair];student_seed=P['student_seeds'][pair];student=FrozenStudent(STUDENTS/str(student_seed))
    sources=list(HERE.glob('*.py'))+[HERE/'protocol.json',RESEARCH/'revision5/execution.py',RESEARCH/'revision5/execution_env.py',
        RESEARCH/'revision2/gating.py',RESEARCH/'revision2/plant.py',RESEARCH/'core.py',RESEARCH/'comparison.py',RESEARCH/'revision4/reward_model.py',RESEARCH/'revision7/kernels.py']
    for source in sources:
        target=out/'source'/source.relative_to(RESEARCH);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
    env=VecNormalize(DummyVecEnv([lambda i=i:Monitor(TrainingEnv(pair,i,seed+i,credit=arm in P['credit']['arms']),str(out/f'episodes-{i}.csv')) for i in range(8)]),norm_obs=False,norm_reward=True,clip_reward=10.)
    model=create_model(env,student,seed,arm);model.set_logger(configure(str(out),['csv']));callback=Diagnostics(out)
    start=time.perf_counter();commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE,text=True).strip()
    def save():
        folder=out/f'checkpoint-{model.num_timesteps}';folder.mkdir();model.save(folder/'policy.zip');env.save(folder/'normalization.pkl')
        steps=[float(v['step'].item()) for v in model.policy.optimizer.state.values() if 'step' in v]
        (folder/'complete.json').write_text(json.dumps(dict(arm=arm,pair=pair,seed=seed,student_seed=student_seed,
            steps=model.num_timesteps,optimizer_steps=max(steps,default=0),optimizer_states=len(steps),
            reward_normalizer_count=float(env.ret_rms.count),observation_dimensions=20,profile='anchored_credit_ppo_v10',anchor_coef=model.anchor_coef,mask_busy=model.mask_busy,
            source_commit=commit,protocol=P),indent=2)+'\n')
    save()
    for index,chunk in enumerate([25000,25000,50000]):
        model.learn(total_timesteps=chunk,callback=callback,reset_num_timesteps=index==0)
        model.logger.dump(model.num_timesteps);save()
    assert model.num_timesteps==100000 and callback.count==100000
    with (out/'diagnostics.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=callback.rows[0],lineterminator='\n');w.writeheader();w.writerows(callback.rows)
    (out/'complete.json').write_text(json.dumps(dict(arm=arm,pair=pair,seed=seed,student_seed=student_seed,steps=model.num_timesteps,
        wall_s=time.perf_counter()-start,regions=callback.regions,source_commit=commit,protocol=P),indent=2)+'\n');env.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--arm',choices=P['arms']);p.add_argument('--pair',type=int,choices=range(3));a=p.parse_args()
    if a.arm is not None:run(a.arm,a.pair,a.output);return
    a.output.mkdir(parents=True,exist_ok=False)
    def job(item):
        pair,arm=item;name=f'{arm}-{P["rl_seeds"][pair]}';env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        with (a.output/f'{name}.log').open('w') as f:
            subprocess.run([sys.executable,str(HERE/'train10.py'),'--output',str(a.output/name),'--arm',arm,'--pair',str(pair)],stdout=f,stderr=subprocess.STDOUT,env=env,check=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(job,[(i,arm) for i in range(3) for arm in P['arms']]))
    (a.output/'complete.json').write_text(json.dumps(dict(total_steps=1200000,protocol=P),indent=2)+'\n')


if __name__=='__main__':main()
