"""Matched delayed hybrid training; no training runs without an explicit entry call.

Actor observations remain the public 17-feature contract. Plant truth and a
matched shadow LQR are used only to generate reward/audit records. The feedforward
actor does not observe the pending proposal or estimator history, so delayed
credit remains partially observed; no immediate-action-credit claim is made.
"""
from dataclasses import asdict,dataclass
from pathlib import Path
import hashlib,io,json,math,shutil,zipfile
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from integrations.unified_lans.controller import Proposal
from integrations.unified_lans.inference import CONTRACT,FEATURES,sha
from integrations.unified_lans.physics import Config
from integrations.unified_lans.run import clean
from integrations.unified_lans.simulation import Network,initial,move_npcs,truth_metrics
from tools.unified_campaign.study import Clock,StudyRoute
from tools.unified_control_v8.control import Controller

ROOT=Path(__file__).resolve().parents[2]
SERVICE_S=.05
STEPS_PER_SEED=16384
SEEDS=(42,43,44)


@dataclass(frozen=True)
class RewardConfig:
    tracking: float=8.
    heading: float=4.
    steering_rate: float=.04
    acceleration: float=.002
    excess_heading: float=4.
    excess_rate: float=.04
    failure: float=20.


REWARD=RewardConfig()


def training_case(rng):
    """Training RNG only: evaluation namespaces and their fixture files are unused."""
    return dict(id=int(rng.integers(1_000_000)),stage='v9_training_only',
        scenario=str(rng.choice(['following','merge','crossing','curved'])),
        mirror=int(rng.choice([-1,1])),speed=float(rng.choice([8.,12.,16.])),
        stiffness=float(rng.uniform(.75,1.25)),delay=float(rng.choice([0.,.05,.1])),
        lateral=float(rng.uniform(-.5,.5)),heading=float(rng.uniform(-.03,.03)),
        phase=float(rng.uniform(-5.,5.)),amplitude=float(rng.uniform(.85,1.1)),
        network='nominal',network_seed=int(rng.integers(1,100000)),
        npc_x_shift=float(rng.uniform(-5.,5.)),npc_speed_scale=float(rng.uniform(.75,1.25)))


def setup(case,mode,controller_factory=Controller,controller_kwargs=None,grid=True):
    """Same initial conditions, geometry and packet model as the common study."""
    scenario=case['scenario'];route0,_,npcs=initial(scenario,0.)
    route=StudyRoute(route0.kind,case['mirror'],case['phase'],case['amplitude'])
    y,h,_=route.geometry(0.)
    ego=np.array([0.,y+case['lateral'],h+case['heading'],case['speed'],0.,0.])
    for state in npcs.values():
        if scenario=='crossing':state[1]*=case['mirror'];state[2]*=case['mirror']
        else:
            state[1]=route.geometry(state[0])[0] if scenario in ('curved','merge') else 0.
            state[2]=route.geometry(state[0])[1] if scenario=='curved' else 0.
            state[3]=max(3.,case['speed']-4.)
    for state in npcs.values():
        state[0]+=case.get('npc_x_shift',0.)
        state[3]*=case.get('npc_speed_scale',1.)
    clock=Clock()
    params=dict(penalty=16.,adaptive=True,mpc=True,early_id=True,tracking_only=False)
    params.update(controller_kwargs or {})
    pipe=controller_factory(route,scenario,Config(horizon=2.),case['delay'],gains=(.04,0.),mode=mode,
        clock=clock,target_speed=case['speed'],deterministic_grid=(-.08,-.04,0.,.04,.08) if grid else (),**params)
    pipe.expected=set(npcs)
    return pipe,clock,ego,npcs,Network(case['network_seed'],case['network'])


def close_controller(controller):
    close=getattr(controller,'close',None)
    if close is not None:close()


class MatchedEnv(gym.Env):
    """One pending 50 ms request, actual gated rewards and the deployed hybrid."""
    def __init__(self,controller_factory=Controller,controller_kwargs=None,trace_path=None):
        super().__init__()
        self.observation_space=spaces.Box(-5.,5.,(17,),np.float32)
        self.action_space=spaces.Box(-1.,1.,(1,),np.float32)
        self.controller_factory=controller_factory;self.controller_kwargs=dict(controller_kwargs or {})
        self.trace_path=None if trace_path is None else Path(trace_path)
        self.trace=None;self.episode=-1;self.done=True;self.pipe=None;self.shadow=None
        if self.trace_path is not None:self.trace=self.trace_path.open('x')

    def reset(self,*,seed=None,options=None):
        super().reset(seed=seed)
        if self.pipe is not None:close_controller(self.pipe);close_controller(self.shadow)
        self.case=dict(options['case']) if options and 'case' in options else training_case(self.np_random)
        self.pipe,self.clock,self.ego,self.npcs,self.net=setup(self.case,'hybrid',self.controller_factory,self.controller_kwargs)
        shadow_kwargs=dict(self.controller_kwargs,adaptive=False,mpc=False)
        self.shadow,self.shadow_clock,self.shadow_ego,_,self.shadow_net=setup(self.case,'lqr',self.controller_factory,shadow_kwargs,grid=False)
        self.tick=0;self.sequence=0;self.pending=None;self.done=False;self.episode+=1
        self.net.emit(0.,self.ego,self.npcs,self.pipe.inbox)
        self.shadow_net.emit(0.,self.shadow_ego,self.npcs,self.shadow.inbox)
        self.observation_valid=False
        return self._observation(),dict(episode=self.episode)

    def _observation(self):
        value=self.pipe.features(self.clock.now)
        self.observation_valid=value is not None
        if value is None:return np.zeros(17,dtype=np.float32)
        value=np.asarray(value,dtype=np.float32)
        if value.shape!=(17,) or not np.isfinite(value).all():raise ValueError('invalid public policy observation')
        return value

    def step(self,action):
        if self.done:raise RuntimeError('reset required')
        action=np.asarray(action,dtype=float).reshape(-1)
        if action.shape!=(1,) or not np.isfinite(action).all():raise ValueError('finite scalar action required')
        now=self.clock.now;submitted=False;proposal=None
        if self.observation_valid and self.pending is None:
            self.sequence+=1;submitted=True
            proposal=Proposal(self.sequence,self.pipe.inbox.latest['ego'].observed_s,now,
                float(np.clip(action[0],-1,1))*.08,now)
            self.pending=(now+SERVICE_S,proposal)
        before=self.ego.copy();shadow_before=self.shadow_ego.copy()
        previous=self.pipe.applied;shadow_previous=self.shadow.applied
        decision=self.pipe.decide(now);shadow_decision=self.shadow.decide(now)
        self.ego=self.pipe.apply(now,self.ego,self.case['stiffness'])
        self.shadow_ego=self.shadow.apply(now,self.shadow_ego,self.case['stiffness'])
        move_npcs(self.npcs,.05,self.pipe.route,self.case['scenario'])
        truth=truth_metrics(self.ego,self.npcs,self.pipe.route,self.pipe.cfg)
        shadow_truth=truth_metrics(self.shadow_ego,self.npcs,self.shadow.route,self.shadow.cfg)
        rate=(self.pipe.applied.steering-previous.steering)/.05
        shadow_rate=(self.shadow.applied.steering-shadow_previous.steering)/.05
        failed=bool(truth['collision'] or abs(truth['error'])>1.75)
        w=REWARD
        actual_cost=w.tracking*truth['error']**2+w.heading*truth['heading_error']**2+w.steering_rate*rate**2+w.acceleration*self.pipe.applied.accel**2
        shadow_cost=w.tracking*shadow_truth['error']**2+w.heading*shadow_truth['heading_error']**2+w.steering_rate*shadow_rate**2+w.acceleration*self.shadow.applied.accel**2
        heading_excess=max(0.,truth['heading_error']**2-shadow_truth['heading_error']**2)
        rate_excess=max(0.,rate**2-shadow_rate**2)
        reward=float(shadow_cost-actual_cost-w.excess_heading*heading_excess-w.excess_rate*rate_excess-w.failure*failed)
        self.tick+=1;self.clock.now=self.tick*.05;self.shadow_clock.now=self.clock.now
        self.done=failed or self.tick>=120
        accepted=None;response_sequence=None
        if not failed:
            self.net.emit(self.clock.now,self.ego,self.npcs,self.pipe.inbox)
            self.shadow_net.emit(self.clock.now,self.shadow_ego,self.npcs,self.shadow.inbox)
            if self.pending is not None and self.pending[0]<=self.clock.now+1e-9:
                response_sequence=self.pending[1].sequence
                accepted=self.pipe.accept(self.pending[1],self.clock.now);self.pending=None
            observation=self._observation()
        else:
            self.pending=None;self.observation_valid=False;observation=np.zeros(17,dtype=np.float32)
        info=dict(**truth,selected=decision['source'],submitted=submitted,accepted=accepted,
            response_sequence=response_sequence,submission_sequence=None if proposal is None else proposal.sequence,
            decision_proposal_age=decision.get('proposal_age'),observation_valid=self.observation_valid,
            actual_cost=float(actual_cost),shadow_cost=float(shadow_cost),heading_excess=float(heading_excess),
            rate_excess=float(rate_excess),steering_rate=float(rate),shadow_rate=float(shadow_rate),
            reward=float(reward),case=self.case)
        if self.trace is not None:
            row=dict(episode=self.episode,tick=self.tick-1,time_s=now,case=self.case,
                action=float(action[0]),reward=reward,state_before=before,state_after=self.ego,
                shadow_before=shadow_before,shadow_after=self.shadow_ego,npc_truth=self.npcs,
                issued_steering=self.pipe.issued.steering,issued_accel=self.pipe.issued.accel,
                applied_steering=self.pipe.applied.steering,applied_accel=self.pipe.applied.accel,
                shadow_steering=self.shadow.applied.steering,shadow_accel=self.shadow.applied.accel,
                decision=decision,shadow_decision=shadow_decision,truth=truth,shadow_truth=shadow_truth,
                info=info,terminated=failed,truncated=bool(self.tick>=120 and not failed),observation=observation)
            self.trace.write(json.dumps(clean(row),allow_nan=False,default=lambda value: value.tolist() if isinstance(value,np.ndarray) else (_ for _ in ()).throw(TypeError(type(value).__name__)))+'\n')
            if self.done:self.trace.flush()
        return observation,reward,failed,bool(self.tick>=120 and not failed),info

    def close(self):
        if self.pipe is not None:close_controller(self.pipe);close_controller(self.shadow);self.pipe=None;self.shadow=None
        if self.trace is not None:self.trace.close();self.trace=None


def _optimizer_digest(state):
    digest=hashlib.sha256()
    def feed(value):
        if isinstance(value,dict):
            for key in sorted(value,key=str):digest.update(str(key).encode());feed(value[key])
        elif isinstance(value,(list,tuple)):
            for item in value:feed(item)
        elif hasattr(value,'detach'):
            array=value.detach().cpu().numpy();digest.update(str(array.dtype).encode());digest.update(str(array.shape).encode());digest.update(array.tobytes())
        else:digest.update(repr(value).encode())
    feed(state);return digest.hexdigest()


def train_endpoint(seed,output,controller_factory=Controller,controller_kwargs=None):
    """Explicit finite continuation entry; root must freeze the controller first."""
    assert seed in SEEDS
    import torch
    from stable_baselines3 import PPO
    torch.set_num_threads(1)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    source=ROOT/f'results/python-campaign-v2/policies/seed-{seed}/policy.zip'
    files=[*(ROOT/'tools/unified_control_v9').glob('*.py'),*(ROOT/'integrations/unified_lans').glob('*.py'),ROOT/'tools/unified_campaign/study.py',ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py']
    for version in range(4,9):files.extend((ROOT/f'tools/unified_control_v{version}').glob('*.py'))
    protocol=dict(seed=seed,new_steps=STEPS_PER_SEED,service_s=SERVICE_S,reward=asdict(REWARD),
        source_policy_sha256=sha(source),controller_kwargs=controller_kwargs or {},
        source_hashes={str(path.relative_to(ROOT)):sha(path) for path in files},
        observation_contract=FEATURES,partial_observation=True,checkpoint_selection=False)
    (output/'protocol.json').write_text(json.dumps(protocol,indent=2))
    for path in files:
        target=output/'source'/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    env=MatchedEnv(controller_factory,controller_kwargs,output/'training.jsonl')
    try:
        model=PPO.load(source,env=env,device='cpu',seed=seed)
        before=int(model.num_timesteps);loaded_hash=_optimizer_digest(model.policy.optimizer.state_dict())
        with zipfile.ZipFile(source) as archive:
            saved=torch.load(io.BytesIO(archive.read('policy.optimizer.pth')),map_location='cpu')
        assert loaded_hash==_optimizer_digest(saved),'Optimizer state did not survive checkpoint load'
        assert model.observation_space.shape==(17,) and model.action_space.shape==(1,)
        from stable_baselines3.common.callbacks import BaseCallback
        class Checkpoint(BaseCallback):
            def _on_step(self):
                if (self.num_timesteps-before)%2048==0:
                    model.save(output/f'checkpoint-{self.num_timesteps-before}.zip')
                    print('TRAIN',seed,self.num_timesteps-before,'/',STEPS_PER_SEED,flush=True)
                return True
        model.learn(total_timesteps=STEPS_PER_SEED,reset_num_timesteps=False,callback=Checkpoint())
        assert int(model.num_timesteps)==before+STEPS_PER_SEED
        model.save(output/'policy.zip')
    finally:env.close()
    manifest=dict(contract=CONTRACT,features=FEATURES,scale_rad=.08,seed=seed,
        policy_sha256=sha(output/'policy.zip'),steps=int(model.num_timesteps),new_steps=STEPS_PER_SEED,
        source_policy_sha256=sha(source),source_optimizer_sha256=loaded_hash,optimizer_restoration_verified=True,
        protocol_sha256=sha(output/'protocol.json'),training_trace_sha256=sha(output/'training.jsonl'),
        purpose='fixed_matched_delayed_hybrid_continuation_endpoint',no_endpoint_selection=True)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return manifest


def run_episode(case,mode,model=None,grid=True,seconds=6.,controller_factory=Controller,controller_kwargs=None):
    """Logical-time evaluation with the same one-request service and public inputs."""
    pipe,clock,ego,npcs,net=setup(case,mode,controller_factory,controller_kwargs,grid)
    rows=[];sequence=0;pending=None
    try:
        for tick in range(round(seconds/.05)):
            now=tick*.05;clock.now=now;net.emit(now,ego,npcs,pipe.inbox)
            if pending is not None and pending[0]<=now+1e-9:pipe.accept(pending[1],now);pending=None
            if model is not None and pending is None:
                features=pipe.features(now)
                if features is not None:
                    action,_=model.predict(features,deterministic=True);sequence+=1
                    proposal=Proposal(sequence,pipe.inbox.latest['ego'].observed_s,now,float(np.asarray(action).ravel()[0])*.08,now)
                    pending=(now+SERVICE_S,proposal)
            before=ego.copy();previous=pipe.applied;decision=pipe.decide(now)
            ego=pipe.apply(now,ego,case['stiffness']);move_npcs(npcs,.05,pipe.route,case['scenario'])
            truth=truth_metrics(ego,npcs,pipe.route,pipe.cfg)
            rows.append(dict(tick=tick,time_s=now,state_before=before.tolist(),state_after=ego.tolist(),npc_truth={k:v.tolist() for k,v in npcs.items()},**truth,**decision,
                applied_steering=pipe.applied.steering,applied_accel=pipe.applied.accel,steering_rate=(pipe.applied.steering-previous.steering)/.05))
            if truth['collision'] or abs(truth['error'])>2.5:break
    finally:close_controller(pipe)
    n=round(seconds/.05);sse=sum(row['error']**2 for row in rows)+(n-len(rows))*2.5**2
    result=dict(case=case,mode=mode,ticks=len(rows),expected_ticks=n,
        failed=len(rows)<n or any(row['collision'] or row['corridor_exceeded'] for row in rows),rmse_m=math.sqrt(sse/n),
        heading_rms=math.sqrt(sum(row['heading_error']**2 for row in rows)/len(rows)),
        rate_rms=math.sqrt(sum(row['steering_rate']**2 for row in rows)/len(rows)),progress_m=float(ego[0]),
        min_clearance=min(row['true_clearance'] for row in rows),collisions=sum(row['collision'] for row in rows),
        ppo_ticks=sum(row['source']=='ppo' for row in rows))
    return result,rows
