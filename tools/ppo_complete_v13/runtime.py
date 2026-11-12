"""Actual bounded PPO worker with original sensor times and measured IPC.

Only startup/close block without a control deadline. Submission and polling do
not wait; an owner decides whether a reply fits the current context and budget.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
from queue import Empty,Full
import hashlib,json,math,multiprocessing as mp,time
import numpy as np


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
    return h.hexdigest()


@dataclass(frozen=True)
class PolicyRequest:
    sequence:int
    observed_s:float
    submitted_s:float
    wall_observed:float
    wall_submitted:float
    observation:tuple

    @property
    def identity(self):
        return (self.sequence,self.observed_s,self.submitted_s,self.wall_observed,self.wall_submitted)


@dataclass(frozen=True)
class RuntimeAction:
    sequence:int
    observed_s:float
    submitted_s:float
    wall_observed:float
    wall_submitted:float
    worker_started_wall:float
    worker_finished_wall:float
    action:tuple

    @property
    def identity(self):
        return (self.sequence,self.observed_s,self.submitted_s,self.wall_observed,self.wall_submitted)

    @property
    def prediction_ms(self):return 1000*(self.worker_finished_wall-self.worker_started_wall)


def fresh(action,now,delay,wall_now,ttl=.15):
    """Age includes actuator delay and the actual original source-wall age."""
    values=(now,delay,wall_now,ttl,action.observed_s,action.submitted_s,action.wall_observed)
    if not all(math.isfinite(x) for x in values) or delay<0 or not 0<ttl<=.15:return False
    return (0<=action.observed_s<=action.submitted_s<=now+1e-9
        and 0<=now+delay-action.observed_s<ttl-1e-9
        and 0<=wall_now-action.wall_observed
        and wall_now+delay-action.wall_observed<ttl-1e-9)


def load_policy(folder,contract,observation_dim,action_dim=8,bc=False):
    from stable_baselines3 import PPO
    folder=Path(folder);record=json.loads((folder/'manifest.json').read_text())
    if record.get('contract')!=contract:raise ValueError('policy encoder/decoder contract mismatch')
    if record.get('observation_dim')!=observation_dim or record.get('action_dim')!=action_dim:
        raise ValueError('manifest observation/action dimensions mismatch')
    name='bc-policy.zip' if bc else 'policy.zip';key='bc_policy_sha256' if bc else 'policy_sha256'
    if record.get(key)!=sha(folder/name):raise ValueError('policy hash mismatch')
    learner=record.get('learner_class','PPO')
    if learner=='IndependentPPO':
        from .learner import IndependentPPO
        loader=IndependentPPO
    elif learner=='PPO':loader=PPO
    else:raise ValueError('unsupported saved learner class')
    if contract=='v13-current-anchor55-correction8-finite120-v1' and learner!='IndependentPPO':
        raise ValueError('v13 policy requires its explicit independent-optimizer learner')
    model=loader.load(folder/name,device='cpu')
    if model.observation_space.shape!=(observation_dim,) or model.action_space.shape!=(action_dim,):
        raise ValueError('actual policy observation/action dimensions mismatch')
    if not np.all(model.action_space.low==-1) or not np.all(model.action_space.high==1):
        raise ValueError('normalized bounded action required')
    return model


def _worker(folder,contract,observation_dim,action_dim,bc,incoming,outgoing,stall_s):
    try:
        import torch
        torch.set_num_threads(1);start=time.monotonic()
        model=load_policy(folder,contract,observation_dim,action_dim,bc)
        value,_=model.predict(np.zeros(observation_dim,np.float32),deterministic=True)
        if not np.isfinite(value).all():raise ValueError('nonfinite policy startup')
        outgoing.put(('ready',dict(startup_s=time.monotonic()-start,observation_dim=observation_dim,action_dim=action_dim)))
        while True:
            request=incoming.get()
            if request is None:return
            if not isinstance(request,PolicyRequest):raise TypeError('typed policy request required')
            started=time.monotonic()
            value,_=model.predict(np.asarray(request.observation,np.float32),deterministic=True)
            value=np.asarray(value).ravel()
            if value.shape!=(action_dim,) or not np.isfinite(value).all() or np.max(abs(value))>1.+1e-12:
                raise ValueError('invalid policy action')
            if stall_s:time.sleep(stall_s)
            ended=time.monotonic()
            outgoing.put(('action',RuntimeAction(*request.identity,started,ended,tuple(float(x) for x in value))))
    except Exception as error:outgoing.put(('error',type(error).__name__+': '+str(error)))


class PolicyWorker:
    """At most one pending request. A late response never becomes a new frame."""
    def __init__(self,folder,contract,observation_dim,action_dim=8,bc=False,stall_s=0.):
        if not math.isfinite(stall_s) or stall_s<0:raise ValueError('nonnegative diagnostic stall required')
        if type(observation_dim) is not int or observation_dim<=0 or type(action_dim) is not int or action_dim<=0:
            raise ValueError('positive integer dimensions required')
        context=mp.get_context('spawn');self.incoming=context.Queue(maxsize=1);self.outgoing=context.Queue(maxsize=2)
        self.process=context.Process(target=_worker,args=(str(folder),contract,observation_dim,action_dim,bc,self.incoming,self.outgoing,stall_s),daemon=True)
        self.observation_dim=observation_dim;self.action_dim=action_dim;self.sequence=0;self.pending=None
        self.failed=False;self.error='';self.closed=False;self.startup=None;self.process.start()
        try:
            kind,payload=self.outgoing.get(timeout=45.)
            if kind!='ready':raise RuntimeError(str(payload))
            self.startup=payload
        except BaseException:self.close();raise

    def submit(self,query,observed_s,submitted_s,wall_observed):
        if self.closed or self.failed or self.pending is not None:return False
        if not self.process.is_alive():self.failed=True;self.error='policy worker exited';return False
        value=np.asarray(query,np.float32)
        if value.shape!=(self.observation_dim,) or not np.isfinite(value).all():
            raise ValueError('finite versioned observation required')
        wall=time.monotonic()
        if not all(math.isfinite(x) for x in (observed_s,submitted_s,wall_observed)):
            raise ValueError('finite original timestamps required')
        if not 0<=observed_s<=submitted_s or not 0<=wall_observed<=wall+1e-9:
            raise ValueError('invalid original timestamps')
        request=PolicyRequest(self.sequence+1,float(observed_s),float(submitted_s),float(wall_observed),wall,tuple(float(x) for x in value))
        try:self.incoming.put_nowait(request)
        except Full:return False
        self.sequence+=1;self.pending=request;return True

    def poll(self):
        if self.closed:return None
        try:kind,payload=self.outgoing.get_nowait()
        except Empty:
            if not self.process.is_alive():self.failed=True;self.error='policy worker exited'
            return None
        pending=self.pending;self.pending=None
        if (kind!='action' or not isinstance(payload,RuntimeAction) or pending is None
            or payload.identity!=pending.identity or len(payload.action)!=self.action_dim
            or not np.isfinite(payload.action).all() or max(abs(x) for x in payload.action)>1.+1e-12
            or payload.worker_started_wall<payload.wall_submitted
            or payload.worker_finished_wall<payload.worker_started_wall):
            self.failed=True;self.error=str(payload) if kind=='error' else 'policy response identity/shape/timing mismatch';return None
        return payload

    def close(self):
        if self.closed:return
        self.closed=True
        if self.process.is_alive():
            try:self.incoming.put_nowait(None)
            except Full:pass
            self.process.join(timeout=1.)
            if self.process.is_alive():self.process.terminate();self.process.join(timeout=2.)
        else:self.process.join(timeout=1.)
        self.pending=None
        for channel in (self.incoming,self.outgoing):channel.cancel_join_thread();channel.close()

    def __enter__(self):return self
    def __exit__(self,*args):self.close()


def owner_tick(owner,now,query_builder,proposal_type,*,worker=None,wall_observed=None,
               release_wall=None,scheduled_release_wall=None,deadline_s=.05,finish_reserve_s=.015):
    """Serial prepare, actual IPC, guarded finish in one measured owner slot.

    query_builder(context) must use only the received data/current causal anchor.
    Caller supplies the original frame's wall time. Late prior-context responses
    are discarded; no query is generated on terminal steps by this function.
    """
    if not 0<deadline_s<=.05 or not 0<=finish_reserve_s<deadline_s:
        raise ValueError('valid original owner deadline and finish reserve required')
    started=time.monotonic();release=started if release_wall is None else release_wall
    if not math.isfinite(release) or release>started+1e-9:raise ValueError('invalid actual release time')
    deadline=release+deadline_s;context=owner.prepare(now);prepared=time.monotonic()
    discarded=worker.poll() if worker is not None else None
    submitted=False;request=None;reply=None;proposal=None;query=None;reason='policy_disabled';wait_started=prepared
    if worker is not None:
        if wall_observed is None or not math.isfinite(wall_observed) or not 0<=wall_observed<=prepared+1e-9:
            raise ValueError('original received-frame wall timestamp is required')
        if prepared>=deadline-finish_reserve_s:reason='prepare_used_inference_budget'
        elif worker.failed:reason='policy_worker_failed'
        elif worker.pending is not None:reason='older_context_request_still_pending'
        else:
            query=query_builder(context)
            if query is None:reason='no_causal_query'
            else:
                submitted=worker.submit(query,context.observed_s,now,wall_observed)
                request=worker.pending if submitted else None;reason='current_context_reply_not_ready'
                if submitted:
                    while time.monotonic()<deadline-finish_reserve_s:
                        reply=worker.poll()
                        if reply is not None or worker.failed:break
                        time.sleep(.0001)
                    if reply is not None:
                        if reply.identity!=request.identity:raise AssertionError('request identity changed after worker validation')
                        proposal=proposal_type(reply.sequence,reply.observed_s,reply.submitted_s,reply.wall_observed,reply.action)
                        reason='current_context_reply'
    finished_wait=time.monotonic()
    # The owner must check deadline once more immediately before changing its
    # provisional command. This also handles expensive projection after a reply.
    row=owner.finish(context,proposal,deadline_wall=deadline);issued=time.monotonic()
    selected=bool(row.get('ppo_selected',row.get('sequence_plan_selected',False)))
    postcheck_fallback=False
    if selected and (reply is None or issued>deadline or not fresh(reply,now,owner.delay,issued,owner.cfg.proposal_ttl)):
        row=owner.restore_baseline(context,'runtime_deadline_or_expiry_after_finish',row)
        postcheck_fallback=True;selected=False;issued=time.monotonic()
    row.update(complete_decision_ms=1000*(issued-release),owner_prepare_ms=1000*(prepared-started),
        policy_slot_ms=1000*(finished_wait-wait_started),owner_finish_ms=1000*(issued-finished_wait),
        owner_release_wall=release,owner_deadline_wall=deadline,owner_issued_wall=issued,
        owner_response_miss=issued>deadline,policy_submitted=submitted,policy_reply_reason=reason,
        policy_worker_failed=False if worker is None else worker.failed,
        discarded_prior_reply_sequence=None if discarded is None else discarded.sequence,
        reply_sequence=None if reply is None else reply.sequence,
        policy_prediction_ms=None if reply is None else reply.prediction_ms,
        policy_roundtrip_ms=None if reply is None else 1000*(finished_wait-reply.wall_submitted),
        proposal_source_wall=None if reply is None else reply.wall_observed,
        proposal_wall_age_at_issue=None if reply is None else issued+owner.delay-reply.wall_observed,
        proposal_logical_age_at_issue=None if reply is None else now+owner.delay-reply.observed_s,
        runtime_observation=None if query is None else np.asarray(query,float).tolist(),
        runtime_action=None if reply is None else list(reply.action),runtime_selected=selected,
        runtime_reply=None if reply is None else asdict(reply),
        runtime_postcheck_fallback=postcheck_fallback)
    if selected:
        assert reply is not None and fresh(reply,now,owner.delay,issued,owner.cfg.proposal_ttl)
        assert issued<=deadline
    if scheduled_release_wall is not None:
        row.update(scheduled_release_wall=scheduled_release_wall,
            release_lateness_ms=1000*max(0.,release-scheduled_release_wall),
            scheduled_owner_response_ms=1000*(issued-scheduled_release_wall),
            scheduled_owner_response_miss=issued>scheduled_release_wall+deadline_s)
    return row,context,reply


def profile(cases,output,*,policy=None,mode='adaptive',controller_kwargs=None,steps=120,role='runtime_engineering'):
    """Paced, actual-IPC owner timing with a separately logged Python plant.

    No timing is inferred from simulation time. Startup/JIT is outside the
    measured mission and explicitly recorded. Every slot, including misses,
    failed inference and conservative fallbacks, remains in the raw output.
    This measures host engineering timing; it is not native vehicle transfer
    or a worst-case execution-time certificate.
    """
    from contextlib import ExitStack
    from .learning import controller_class,observe,RunningStats,CONTRACT,ROOT
    from .plans import CorrectionProposal
    from integrations.unified_lans.simulation import move_npcs,truth_metrics
    from integrations.unified_lans.run import clean
    from tools.unified_control_v9.learning import setup
    from tools.ppo_benefit_v10.core import PARAMS
    if mode not in ('lqr','adaptive','ppo'):raise ValueError('explicit matched runtime mode required')
    if type(steps) is not int or not 1<=steps<=120:raise ValueError('1..120 measured slots required')
    if mode=='ppo' and policy is None:raise ValueError('PPO runtime requires a frozen policy folder')
    cases=[dict(c) for c in cases];assert cases
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    files=[*Path(__file__).parent.glob('*.py'),ROOT/'integrations/unified_lans/controller.py',
        ROOT/'integrations/unified_lans/physics.py',ROOT/'integrations/unified_lans/simulation.py',
        ROOT/'tools/unified_control_v9/learning.py']
    for version in range(4,9):files.extend((ROOT/f'tools/unified_control_v{version}').glob('*.py'))
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    for p in files:
        target=output/'source'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(p.read_bytes())
    policy_path=None if policy is None else Path(policy).resolve()
    policy_sha=None if policy_path is None else sha(policy_path/'policy.zip')
    protocol=dict(role=role,mode=mode,cases=cases,slots_per_case=steps,owner_deadline_s=.05,
        finish_reserve_s=.015,policy=None if policy_path is None else str(policy_path),policy_sha256=policy_sha,
        source_hashes=hashes,real_policy_process=mode=='ppo',plant='separate_python_bicycle_outside_owner_timer',
        timing='actual time.monotonic with paced release; all misses retained',
        limitation='Observed host timing, not WCET or native vehicle validation; do not run concurrent training/timing load.')
    (output/'protocol.json').write_text(json.dumps(protocol,indent=2,allow_nan=False)+'\n')
    records=[];startup_start=time.monotonic()
    with ExitStack() as stack:
        worker=stack.enter_context(PolicyWorker(policy_path,CONTRACT,55)) if mode=='ppo' else None
        kwargs=dict(PARAMS,adaptive=mode!='lqr',mpc=mode!='lqr');kwargs.update(controller_kwargs or {})
        # Warm all reachable numerical signatures before the measured release.
        # These synthetic packets never enter the measured traces or scores.
        for case in cases:
            warm,clock,state,npcs,net=setup(case,'lqr' if mode=='lqr' else 'deterministic',controller_class(),kwargs,grid=mode!='lqr')
            for i in range(3):
                now=i*.05;clock.now=now;net.emit(now,state,npcs,warm.inbox)
                ctx=warm.prepare(now);warm.score_candidate(ctx,np.zeros(8))
                warm.score_candidate(ctx,np.full(8,.1));warm.finish(ctx)
                state=warm.apply(now,state,case['stiffness']);move_npcs(npcs,.05,warm.route,case['scenario'])
        startup_s=time.monotonic()-startup_start
        for index,case in enumerate(cases):
            for name,digest in hashes.items():assert sha(ROOT/name)==digest,('Runtime source changed',name)
            if policy_path is not None:assert sha(policy_path/'policy.zip')==policy_sha
            c,clock,state,npcs,net=setup(case,'lqr' if mode=='lqr' else 'deterministic',controller_class(),kwargs,grid=mode!='lqr')
            c.clock=time.monotonic;running=RunningStats();last=np.zeros(8);walls={};rows=[]
            path=output/f'case-{index:03d}.jsonl';schedule=time.monotonic()+.02
            with path.open('x') as stream:
                for tick in range(steps):
                    scheduled=schedule+tick*.05;left=scheduled-time.monotonic()
                    if left>0:time.sleep(left)
                    release=time.monotonic();now=tick*.05;clock.now=now
                    before=state.copy();net.emit(now,state,npcs,c.inbox);walls[net.sequence]=release
                    packet=c.inbox.latest.get('ego');source_wall=release if packet is None else walls[packet.sequence]
                    def query(ctx):
                        value,valid=observe(c,ctx,running,last)
                        return value if valid else None
                    decision,ctx,reply=owner_tick(c,now,query,CorrectionProposal,worker=worker,
                        wall_observed=source_wall,release_wall=release,scheduled_release_wall=scheduled)
                    if reply is not None:running.note_proposal(reply);last=np.asarray(reply.action)
                    previous=c.applied;state=c.apply(now,state,case['stiffness']);move_npcs(npcs,.05,c.route,case['scenario'])
                    truth=truth_metrics(state,npcs,c.route,c.cfg)
                    row=dict(**decision,**truth,tick=tick,time_s=now,case=case,original_frame_wall=source_wall,
                        source_ego_sequence=None if packet is None else packet.sequence,
                        source_ego_observed_s=None if packet is None else packet.observed_s,
                        state_before=before.tolist(),state_after=state.tolist(),
                        npc_truth={k:v.tolist() for k,v in npcs.items()},applied_steering=c.applied.steering,
                        applied_accel=c.applied.accel,steering_rate=(c.applied.steering-previous.steering)/.05)
                    stream.write(json.dumps(clean(row),allow_nan=False)+'\n');stream.flush();rows.append(row)
                    if truth['collision'] or truth['corridor_exceeded']:break
            result=dict(case=case,mode=mode,ticks=len(rows),expected_ticks=steps,
                response_misses=sum(r['owner_response_miss'] for r in rows),
                scheduled_response_misses=sum(r['scheduled_owner_response_miss'] for r in rows),
                selected_ticks=sum(r['runtime_selected'] for r in rows),
                policy_reply_count=sum(r['runtime_reply'] is not None for r in rows),
                failed=any(r['collision'] or r['corridor_exceeded'] for r in rows),raw_sha256=sha(path))
            records.append(result);print('ACTUAL RUNTIME',index+1,'/',len(cases),'misses',result['response_misses'],flush=True)
    summary=dict(role=role,cases=len(records),records=records,startup_outside_timing_s=startup_s,
        samples=sum(r['ticks'] for r in records),expected_samples=len(cases)*steps,
        response_misses=sum(r['response_misses'] for r in records),
        scheduled_response_misses=sum(r['scheduled_response_misses'] for r in records),
        verified=False,qualified=False,limitation=protocol['limitation'])
    (output/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    verification=verify_profile(output)
    return summary,verification


def verify_profile(output):
    """Recompute timestamps, misses, strict age and deterministic worker actions."""
    from .learning import ROOT,CONTRACT
    output=Path(output);p=json.loads((output/'protocol.json').read_text());s=json.loads((output/'summary.json').read_text())
    for name,digest in p['source_hashes'].items():
        assert sha(output/'source'/name)==digest and sha(ROOT/name)==digest,('Runtime source hash',name)
    model=None
    if p['policy'] is not None:
        assert sha(Path(p['policy'])/'policy.zip')==p['policy_sha256'];model=load_policy(p['policy'],CONTRACT,55)
    samples=0;misses=0;scheduled_misses=0;selected=0;times=[];scheduled_times=[]
    for index,record in enumerate(s['records']):
        path=output/f'case-{index:03d}.jsonl';assert sha(path)==record['raw_sha256']
        rows=[json.loads(line) for line in path.read_text().splitlines()];assert len(rows)==record['ticks']
        for row in rows:
            release=row['owner_release_wall'];deadline=row['owner_deadline_wall'];issued=row['owner_issued_wall']
            assert abs(deadline-release-.05)<1e-8 and issued>=release
            assert abs(row['complete_decision_ms']-1000*(issued-release))<1e-8
            assert row['owner_response_miss']==(issued>deadline)
            scheduled=row['scheduled_release_wall']
            assert abs(row['scheduled_owner_response_ms']-1000*(issued-scheduled))<1e-8
            assert row['scheduled_owner_response_miss']==(issued>scheduled+.05)
            reply=row['runtime_reply']
            if reply is not None:
                assert reply['wall_observed']==row['original_frame_wall']
                assert reply['observed_s']==row['source_ego_observed_s']
                assert reply['sequence']==row['reply_sequence']
                assert reply['wall_observed']<=reply['wall_submitted']<=reply['worker_started_wall']<=reply['worker_finished_wall']<=issued
                prediction=model.predict(np.asarray(row['runtime_observation'],np.float32),deterministic=True)[0]
                np.testing.assert_allclose(reply['action'],prediction,rtol=0,atol=1e-7)
            if row['runtime_selected']:
                assert reply is not None and issued<=deadline
                action=RuntimeAction(**dict(reply,action=tuple(reply['action'])))
                assert fresh(action,row['time_s'],row['case']['delay'],issued)
                assert row['source']=='ppo_anchor'
            samples+=1;misses+=row['owner_response_miss'];scheduled_misses+=row['scheduled_owner_response_miss'];selected+=row['runtime_selected']
            times.append(row['complete_decision_ms']);scheduled_times.append(row['scheduled_owner_response_ms'])
        assert record['response_misses']==sum(r['owner_response_miss'] for r in rows)
        assert record['scheduled_response_misses']==sum(r['scheduled_owner_response_miss'] for r in rows)
    assert samples==s['samples'] and misses==s['response_misses'] and scheduled_misses==s['scheduled_response_misses']
    result=dict(passed=True,samples=samples,response_misses=misses,scheduled_response_misses=scheduled_misses,
        selected_ticks=selected,all_requests_original_timestamps=True,all_selected_before_deadline=True,
        full_expected_sample_count=samples==s['expected_samples'],source_sha256=sha(__file__),
        protocol_sha256=sha(output/'protocol.json'),summary_sha256=sha(output/'summary.json'),
        timing_gate_passed=samples==s['expected_samples'] and misses==0 and scheduled_misses==0,
        response_ms=dict(median=float(np.median(times)),p95=float(np.quantile(times,.95)),p99=float(np.quantile(times,.99)),maximum=float(max(times))),
        scheduled_response_ms=dict(median=float(np.median(scheduled_times)),p95=float(np.quantile(scheduled_times,.95)),p99=float(np.quantile(scheduled_times,.99)),maximum=float(max(scheduled_times))),
        qualified=False,scope='Runtime record/timestamp/action replay, distinct from performance qualification and WCET.')
    (output/'verification.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result
