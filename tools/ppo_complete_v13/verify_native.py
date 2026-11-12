"""Independent recorded-pose and timing audit of physical Webots episodes.

This never advances a Python plant. It recomputes geometry and measurements
from native1ms pose samples and checks the frozen executable/model artifacts.
Verification success is separate from safety, runtime or performance success.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import statistics

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
DT=.001
CONTROL_DT=.05
HORIZON=120


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
    return h.hexdigest()


def close(actual,expected,label,tol=1e-8):
    assert math.isfinite(float(actual)) and math.isfinite(float(expected)),label
    assert math.isclose(actual,expected,rel_tol=1e-10,abs_tol=tol),(label,actual,expected)


def vector(actual,expected,label,tol=1e-8):
    a=np.asarray(actual,float);b=np.asarray(expected,float)
    assert a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all(),label
    assert np.allclose(a,b,rtol=1e-10,atol=tol),(label,a,b)


def state(value):
    z=np.asarray(value,float)
    assert z.shape==(6,) and np.isfinite(z).all(),'finite native six-state sample required'
    return z


def route_geometry(case,x):
    """Independent elementary route calculation, without producer geometry."""
    q=x+case['phase'];kind=case['route_kind'];scale=case['mirror']*case['amplitude']
    if kind=='straight':y=derivative=0.
    elif kind=='sine':
        omega=2*math.pi/120;y=1.5*math.sin(omega*q);derivative=1.5*omega*math.cos(omega*q)
    elif kind=='lane_change':
        t=math.tanh((q-30)/12);y=1.75*(1+t);derivative=1.75*(1-t*t)/12
    else:raise AssertionError(('undeclared route kind',kind))
    return scale*y,math.atan(scale*derivative)


def pose_metrics(case,ego,traffic):
    z=state(ego);y,heading=route_geometry(case,float(z[0]))
    error=float(z[1]-y);heading_error=math.atan2(math.sin(z[2]-heading),math.cos(z[2]-heading))
    assert set(traffic)==set(case['initial_npcs']),'native traffic sample omitted or added a vehicle'
    clearance=min(float(np.linalg.norm(state(n)[:2]-z[:2])-4.6) for n in traffic.values())
    return dict(error=error,heading_error=heading_error,clearance=clearance,
        collision=clearance<=0.,corridor=abs(error)>1.75)


def check_initialization(case,initialization):
    """A Supervisor write followed by a stale first packet cannot qualify."""
    assert set(initialization['initial_traffic'])==set(case['initial_npcs'])
    npc_speed_errors={};npc_position_errors={}
    for name,desired in case['initial_npcs'].items():
        actual=state(initialization['initial_traffic'][name]);target=state(desired)
        distance=float(np.linalg.norm(actual[:2]-target[:2]))
        assert distance<=.1,('unsynchronized initial native traffic position',name,distance)
        heading=math.atan2(math.sin(actual[2]-target[2]),math.cos(actual[2]-target[2]))
        assert abs(heading)<=.01,('initial native traffic heading',name,heading)
        npc_speed_errors[name]=float(actual[3]-target[3]);npc_position_errors[name]=distance
    initial=state(initialization['initial_ego']);target=state(case['initial_ego'])
    vector(initial[:3],target[:3],'fixed native ego map frame',tol=1e-7)
    ego_speed_error=float(initial[3]-target[3])
    assert initialization['ego_pose_overwritten'] is False
    assert initialization['npc_pose_overwritten_during_measurement'] is False
    assert initialization['ego_python_integrated'] is False and initialization['npc_python_integrated'] is False
    initialization_count=0 if case.get('scene_calibration') else 1
    assert initialization['npc_pose_initializations']=={n:initialization_count for n in case['initial_npcs']}
    assert initialization['frame']['physical_pose_changed'] is False
    assert 'initial_equivalent_bicycle_steering' in initialization,'initial native steering sensor was not retained'
    return dict(ego_speed_error_m_s=ego_speed_error,npc_speed_errors_m_s=npc_speed_errors,
        npc_position_errors_m=npc_position_errors,
        maximum_absolute_speed_error_m_s=max([abs(ego_speed_error),*(abs(v) for v in npc_speed_errors.values())]),
        all_initial_speeds_within_01_m_s=abs(ego_speed_error)<=.1 and all(abs(v)<=.1 for v in npc_speed_errors.values()),
        npc_pose_initializations=initialization_count,
        scope='Raw initial-state fidelity diagnostic; native initialization transient is retained and no new qualification threshold is silently introduced.')


def check_scene_calibration(folder,case,protocol):
    """Verify the policy-free displacement used to set initial WORLD fields."""
    if not case.get('scene_calibration'):return None
    calibration=Path(case['scene_calibration']);scene_path=calibration/'scene-state.json'
    assert digest(scene_path)==protocol['scene_calibration_sha256'],'native initial-scene calibration changed'
    scene=json.loads(scene_path.read_text());p=json.loads((calibration/'protocol.json').read_text())
    c=json.loads((calibration/'case.json').read_text());s=json.loads((calibration/'summary.json').read_text())
    provenance=json.loads((calibration/'provenance.json').read_text())
    assert c['warmup_only'] is True and scene['warmup_only'] is True and s['warmup_only'] is True
    assert c['mode']=='lqr' and c['policy'] is None and s['policy_tested'] is False
    assert c['role']=='policy_free_native_initial_scene_calibration'
    assert p['policy_sha256'] is None and p['scene_calibration_sha256'] is None
    assert p['source_hashes']==protocol['source_hashes'],'different native code used for scene displacement and measured roles'
    assert p['protos']==protocol['protos'] and p['physical_vehicle']==protocol['physical_vehicle']
    assert scene['physical_warmup_steps']==s['physics_steps']==10000 and s['completed'] is True
    close(scene['simulation_time_s'],10.,'physical initial-scene warmup duration')
    assert scene['fixture_sha256']==case['fixture_sha256']==c['fixture_sha256']
    producer_keys={'output','mode','role','route_kind','policy','controller_kwargs','warmup_only',
        'scene_calibration','fixture_sha256','initial_ego','initial_npcs','npc_defs'}
    fixture={k:v for k,v in case.items() if k not in producer_keys}
    expected=hashlib.sha256(json.dumps(fixture,sort_keys=True).encode()).hexdigest()
    assert expected==case['fixture_sha256'],'scene displacement belongs to a different fixture'
    assert digest(calibration/'case.json')==p['case_sha256']
    assert digest(calibration/'protocol.json')==provenance['protocol_sha256']
    assert digest(calibration/'summary.json')==provenance['summary_sha256']
    assert digest(scene_path)==provenance['raw_sha256']==s['scene_state_sha256']
    assert digest(calibration/'project/worlds/episode.wbt')==p['world_sha256']
    for name,expected in p['source_hashes'].items():assert digest(calibration/'source'/name)==expected,('native scene source',name)
    for name,expected in p['protos'].items():assert digest(calibration/'project'/name)==expected,('native scene PROTO',name)
    ego=state(scene['ego_native']);map_origin=np.asarray(case['initial_ego'][:2],float)
    angle=case['initial_ego'][2]-ego[2];co,si=math.cos(angle),math.sin(angle)
    rotation=np.array([[co,-si],[si,co]])
    measured_world=(Path(folder)/'project/worlds/episode.wbt').read_text()
    calibration_world=(calibration/'project/worlds/episode.wbt').read_text()
    for index,(name,initial) in enumerate(case['initial_npcs'].items()):
        native=state(scene['npc_native'][name]);target=ego[:2]+rotation.T@(np.asarray(initial[:2])-map_origin)
        original_translation=np.array([-100.-20*index,100.+30*index]);expected=original_translation+target-native[:2]
        defname=case['npc_defs'][name]
        pattern=r'DEF '+re.escape(defname)+r' Car \{\s*translation\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)'
        actual=re.search(pattern,measured_world);before=re.search(pattern,calibration_world)
        assert actual and before,'retained initial world has no physical NPC'
        vector([float(actual[1]),float(actual[2])],expected,'policy-free native initial WORLD translation')
        vector([float(before[1]),float(before[2])],original_translation,'calibration original physical NPC world translation')
    return dict(verified=True,scene_state_sha256=digest(scene_path),fixture_sha256=case['fixture_sha256'],
        physical_warmup_steps=10000,policy_tested=False,npc_pose_writes=0,
        scope='Pinned policy-free measured displacement and independent initial world-position arithmetic; warmup trajectory itself is not retained.')


def physical_interval(case,row,previous_state,previous_traffic,previous_measured,previous_target,origin):
    """Recompute all substep collisions, including those between endpoints."""
    vector(row['state_before'],previous_state,'native ego interval continuity')
    assert set(row['npc_truth_before'])==set(previous_traffic)
    for name,z in previous_traffic.items():vector(row['npc_truth_before'][name],z,'native traffic interval continuity')
    physics=row['physics'];assert len(physics)==50,'every native1ms sample must be retained'
    initial_metrics=pose_metrics(case,previous_state,previous_traffic)
    minimum=initial_metrics['clearance'];peak=abs(initial_metrics['error'])
    collision=initial_metrics['collision'];corridor=initial_metrics['corridor'];rates=[];accelerations=[];errors=[]
    prior=state(previous_state);traffic=previous_traffic
    for index,sample in enumerate(physics):
        assert sample['substep']==index
        close(sample['simulation_time_s'],origin+row['time_s']+(index+1)*DT,'native1ms clock')
        actual=state(sample['state']);traffic=sample['traffic'];metrics=pose_metrics(case,actual,traffic)
        close(sample['clearance'],metrics['clearance'],'native sample circle clearance')
        close(sample['error'],metrics['error'],'native sample corridor error')
        measured=float(sample['equivalent_bicycle_steering']);assert math.isfinite(measured)
        measured_rate=(measured-previous_measured)/DT
        close(sample['measured_steering_rate'],measured_rate,'actual measured steering derivative')
        target=float(sample['actuator_target']);target_rate=(target-previous_target)/DT
        close(sample['actuator_target_rate'],target_rate,'native target slew')
        assert abs(target)<=.5+1e-9 and abs(target_rate)<=.6+1e-8,'commanded actuator bounds'
        expected=float(np.clip(row['applied_steering'],previous_target-.6*DT,previous_target+.6*DT))
        close(target,expected,'continuous native steering target')
        close(sample['measured_speed_m_s'],prior[3],'causal pre-step native speed')
        acceleration=float((actual[3]-prior[3])/DT)
        close(sample['achieved_accel_m_s2'],acceleration,'native forward acceleration derivative')
        close(sample['requested_accel'],row['applied_accel'],'desired acceleration through native drivetrain')
        close(sample['bounded_requested_accel'],row['applied_accel'],'original acceleration bounds')
        assert sample['actuation_method']=='torque_pi' and sample['engine_model_used'] is True
        assert 0<=sample['throttle']<=1 and 0<=sample['brake_intensity']<=1
        assert not (sample['throttle']>0 and sample['brake_intensity']>0),'simultaneous native engine and braking'
        rates.append(measured_rate);accelerations.append(acceleration);errors.append(metrics['error'])
        minimum=min(minimum,metrics['clearance']);peak=max(peak,abs(metrics['error']))
        collision|=metrics['collision'];corridor|=metrics['corridor']
        previous_target=target;previous_measured=measured;prior=actual
    vector(row['state_after'],prior,'native endpoint comes from last physics sample')
    for name,z in traffic.items():vector(row['npc_truth'][name],z,'native traffic endpoint')
    last=pose_metrics(case,prior,traffic)
    close(row['error'],last['error'],'endpoint tracking score')
    close(row['native_error'],last['error'],'native endpoint score')
    close(row['heading_error'],last['heading_error'],'native endpoint heading')
    close(row['true_clearance'],minimum,'minimum interval collision clearance')
    close(row['max_interval_error'],peak,'maximum interval corridor error')
    assert row['collision']==collision and row['corridor_exceeded']==corridor,'intersample native safety result'
    close(row['measured_equivalent_steering'],previous_measured,'actual measured endpoint steering')
    close(row['measured_steering_rate_max'],max(abs(r) for r in rates),'actual native peak steering rate')
    close(row['measured_steering_rate_rms'],math.sqrt(statistics.mean(r*r for r in rates)),'actual native RMS steering rate')
    close(row['actual_accel_mean'],statistics.mean(accelerations),'actual native mean acceleration')
    return dict(state=prior,traffic=traffic,measured=previous_measured,target=previous_target,
        rates=rates,errors=errors,accelerations=accelerations)


def check_timing(row,case,model):
    release=row['owner_release_wall'];deadline=row['owner_deadline_wall'];issued=row['owner_issued_wall']
    assert issued>=release
    close(deadline-release,.05,'original owner deadline')
    close(row['complete_decision_ms'],1000*(issued-release),'actual owner response time')
    assert row['cycle_ms']>=row['complete_decision_ms']-1e-8,'native cycle excludes owner work'
    assert row['owner_response_miss']==(issued>deadline)
    scheduled=row['scheduled_release_wall']
    close(row['scheduled_owner_response_ms'],1000*(issued-scheduled),'scheduled owner response time')
    assert row['scheduled_owner_response_miss']==(issued>scheduled+.05)
    source=row['original_frame_wall'];assert 0<=source<=issued
    if case['network']=='nominal':
        assert row['source_ego_sequence']==row['tick']+1
        close(row['source_ego_observed_s'],row['time_s'],'nominal source timestamp')
        assert source>=release,'nominal original capture precedes sensor reads in this owner slot'
    reply=row['runtime_reply']
    if reply is not None:
        assert model is not None,'native neural reply requires frozen policy'
        assert reply['wall_observed']==source and reply['observed_s']==row['source_ego_observed_s']
        assert reply['sequence']==row['reply_sequence']
        assert source<=reply['wall_submitted']<=reply['worker_started_wall']<=reply['worker_finished_wall']<=issued
        observation=np.asarray(row['runtime_observation'],np.float32)
        action=np.asarray(reply['action'],float)
        assert observation.shape==(55,) and np.isfinite(observation).all() and max(abs(observation))<=5
        assert action.shape==(8,) and np.isfinite(action).all() and max(abs(action))<=1
        prediction=model.predict(observation,deterministic=True)[0]
        vector(action,prediction,'actual frozen native policy action',tol=1e-7)
        vector(row['runtime_action'],action,'retained worker action')
        close(row['proposal_wall_age_at_issue'],issued+case['delay']-source,'original source-wall proposal age')
        close(row['proposal_logical_age_at_issue'],row['time_s']+case['delay']-reply['observed_s'],'logical proposal age')
    selected=bool(row['runtime_selected'])
    assert selected==bool(row['sequence_plan_selected']),'selected-action accounting changed after deadline check'
    if selected:
        assert reply is not None and row['source']=='ppo_anchor' and issued<=deadline
        assert 0<=row['time_s']+case['delay']-reply['observed_s']<.15-1e-9
        assert 0<=issued+case['delay']-source<.15-1e-9
        assert not row['runtime_postcheck_fallback']
        assert row['projection_scale'] in (1.,.5,.25,.125,.0625),'undeclared owner projection'
        candidate=np.asarray(row['applied_score_values'],float)
        lqr=np.asarray(row['lqr_model_values'],float);anchor=np.asarray(row['anchor_model_values'],float)
        assert candidate.shape==lqr.shape==anchor.shape==(3,4)
        assert np.isfinite(candidate).all() and np.isfinite(lqr).all() and np.isfinite(anchor).all()
        assert np.all(candidate[:,1]>=0.),'recorded robust native physical-margin admission'
        assert np.all(candidate[:,0]<lqr[:,0]-1e-9),'recorded all-model original LQR cost gate'
        assert np.all(candidate[:,2]<=1.21*lqr[:,2]+2e-6),'recorded all-model original heading gate'
        assert np.all(candidate[:,3]<=1.21*lqr[:,3]+1e-5),'recorded all-model original rate gate'
        close(row['sequence_cost'],float(np.mean(candidate[:,0])),'recorded mean admitted model cost')
        close(row['anchor_reference_cost'],float(np.mean(anchor[:,0])),'recorded exact current anchor cost')
        assert row['sequence_cost']<row['anchor_reference_cost']-1e-8,'recorded strict anchored admission benefit'


def verify(folder):
    folder=Path(folder).resolve();protocol=json.loads((folder/'protocol.json').read_text())
    case=json.loads((folder/'case.json').read_text());summary=json.loads((folder/'summary.json').read_text())
    init=json.loads((folder/'initialization.json').read_text());provenance=json.loads((folder/'provenance.json').read_text())
    assert case==summary['case'] and digest(folder/'case.json')==protocol['case_sha256']
    assert protocol['native_ego_physics'] is True and protocol['native_traffic_physics'] is True
    assert protocol['traffic_state_integrated_in_python'] is False
    close(protocol['physics_step_s'],DT,'frozen native physics timestep')
    close(protocol['controller_step_s'],CONTROL_DT,'frozen native owner timestep')
    assert digest(folder/'protocol.json')==provenance['protocol_sha256']
    assert digest(folder/'summary.json')==provenance['summary_sha256']
    assert digest(folder/'ticks.jsonl')==provenance['raw_sha256']==summary['raw_sha256']
    assert digest(folder/'project/worlds/episode.wbt')==protocol['world_sha256']
    assert len(protocol['protos'])==5,'full physical PROTO set required'
    for name,expected in protocol['protos'].items():assert digest(folder/'project'/name)==expected,('native PROTO',name)
    for name,expected in protocol['source_hashes'].items():assert digest(folder/'source'/name)==expected,('retained native executable source',name)
    initial_fidelity=check_initialization(case,init)
    scene_calibration=check_scene_calibration(folder,case,protocol)
    calibration=ROOT/'results/ppo-complete-v13/native-actuator-calibration-v3/verification.json'
    assert digest(calibration)==protocol['torque_actuator_calibration_sha256'],'frozen common drivetrain calibration changed'
    model=None;learned=case['mode'] in ('ppo','bc','continued_bc')
    if learned:
        from .runtime import load_policy
        from .learning import CONTRACT
        policy=Path(case['policy']);name='bc-policy.zip' if case['mode']=='bc' else 'policy.zip'
        assert digest(policy/name)==protocol['policy_sha256']==provenance['policy_sha256']
        assert digest(policy/'manifest.json')==protocol['policy_manifest_sha256'],'native model manifest changed'
        assert digest(folder/'policy-manifest.json')==protocol['policy_manifest_sha256'],'retained native model manifest changed'
        model=load_policy(policy,CONTRACT,55,bc=case['mode']=='bc')
    else:assert protocol['policy_sha256'] is None and provenance['policy_sha256'] is None
    rows=[json.loads(line) for line in (folder/'ticks.jsonl').open()];n=len(rows)
    assert 1<=n<=HORIZON and n==summary['ticks'] and summary['expected_ticks']==HORIZON
    before=state(init['initial_ego']);traffic=init['initial_traffic'];origin=init['simulation_origin_s']
    measured=float(init['initial_equivalent_bicycle_steering']);target=measured
    queue=[];active=np.zeros(2);previous_issued=np.zeros(2);previous_desired=np.zeros(2)
    all_rates=[];all_errors=[];all_accelerations=[]
    for tick,row in enumerate(rows):
        assert row['tick']==tick;close(row['time_s'],tick*CONTROL_DT,'native owner tick')
        close(row['simulation_before_s'],origin+tick*CONTROL_DT,'native simulation start of slot')
        close(row['simulation_after_s'],origin+(tick+1)*CONTROL_DT,'native simulation end of slot')
        assert row['native_ego_physics'] is True and row['native_traffic_physics'] is True
        assert row['python_ego_integrated'] is False and row['pose_overwritten_during_measurement'] is False
        command=np.array([row['issued_steering'],row['issued_accel']],float)
        assert np.isfinite(command).all() and abs(command[0])<=.5+1e-9 and -6-1e-9<=command[1]<=2.5+1e-9
        assert abs(command[0]-previous_issued[0])<=.6*CONTROL_DT+1e-9,'original issued steering slew bound'
        assert abs(row.get('residual',0.))<=.08+1e-9,'original residual authority'
        queue.append((row['time_s']+case['delay'],command))
        while queue and queue[0][0]<=row['time_s']+1e-9:_,active=queue.pop(0)
        vector([row['applied_steering'],row['applied_accel']],active,'native desired FIFO command')
        close(row['steering_rate'],(active[0]-previous_desired[0])/CONTROL_DT,'desired command steering derivative')
        previous_desired=active.copy();previous_issued=command
        check_timing(row,case,model)
        interval=physical_interval(case,row,before,traffic,measured,target,origin)
        before=interval['state'];traffic=interval['traffic'];measured=interval['measured'];target=interval['target']
        all_rates.extend(interval['rates']);all_errors.extend(interval['errors']);all_accelerations.extend(interval['accelerations'])
        if tick<n-1:assert not row['collision'] and not row['corridor_exceeded'],'native trajectory continued past termination'
    failed=n<HORIZON or any(r['collision'] or r['corridor_exceeded'] for r in rows)
    if n<HORIZON:assert rows[-1]['collision'] or rows[-1]['corridor_exceeded'],'unexplained native early exit'
    assert bool(summary['failed'])==failed
    recomputed=dict(rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(HORIZON-n)*6.25)/HORIZON),
        heading_rms=math.sqrt(statistics.mean(r['heading_error']**2 for r in rows)),
        commanded_rate_rms=math.sqrt(statistics.mean(r['steering_rate']**2 for r in rows)),
        rate_rms=math.sqrt(statistics.mean(r*r for r in all_rates)),progress_m=float(before[0]),
        minimum_true_clearance=min(r['true_clearance'] for r in rows),
        owner_max_ms=max(r['complete_decision_ms'] for r in rows),cycle_max_ms=max(r['cycle_ms'] for r in rows))
    for name,value in recomputed.items():close(summary[name],value,'native summary '+name)
    counts=dict(collisions=sum(r['collision'] for r in rows),corridor_failures=sum(r['corridor_exceeded'] for r in rows),
        owner_response_misses=sum(r['owner_response_miss'] for r in rows),
        scheduled_response_misses=sum(r['scheduled_owner_response_miss'] for r in rows),
        policy_selected_ticks=sum(r['runtime_selected'] for r in rows))
    for name,value in counts.items():assert summary[name]==value,('native summary count',name)
    assert summary['native_ego_physics'] and summary['native_traffic_physics'] and summary['collision_assessed']
    assert summary['python_ego_integrated'] is False and summary['npc_python_integrated'] is False
    assert summary['mesh_contact_collision_assessed'] is False
    return dict(verified=True,qualification=False,case_id=case['id'],mode=case['mode'],role=case['role'],
        ticks=n,raw_physics_steps=len(all_rates),**recomputed,**counts,failed=failed,
        safety_gate_passed=not failed,timing_gate_passed=n==HORIZON and counts['owner_response_misses']==0 and counts['scheduled_response_misses']==0,
        measured_steering_rate_max=max(abs(r) for r in all_rates),
        measured_accel_min=min(all_accelerations),measured_accel_max=max(all_accelerations),
        measured_physics_lateral_rms=math.sqrt(statistics.mean(e*e for e in all_errors)),
        protocol_sha256=digest(folder/'protocol.json'),summary_sha256=digest(folder/'summary.json'),
        raw_sha256=digest(folder/'ticks.jsonl'),verifier_sha256=digest(__file__),
        policy_sha256=protocol['policy_sha256'],initial_state_fidelity=initial_fidelity,scene_calibration=scene_calibration,
        scope='Recorded native1ms circle/corridor geometry, actuator/command FIFO, actual timestamps and frozen policy inference; no Python plant replay or Webots re-execution.',
        limitations=['Native integration and absence of pose/velocity/force overwrites are pinned executable-source/producer provenance, not inferred from scalar error traces.',
            'Original2.3m circle geometry is checked on physical poses; mesh-contact collision and worst-case execution time are not certified.',
            'Initial warmup is not fully traced; initial settled sensor samples and fixed map-frame initialization are checked.',
            'Any native initial speed mismatch from the Python fixture is reported explicitly; numerical verification is not an exact-initial-state or simulator-equivalence claim.',
            'Commanded acceleration and target slew bounds are checked separately from physically realized overshoot and tire dynamics.',
            'All-model admission inequalities are checked on retained predicted model values; the native model rollouts are not independently recomputed here.',
            'This arithmetic audit does not establish PPO performance superiority or overall framework qualification.'])


def main():
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--output',type=Path);args=p.parse_args()
    try:result=verify(args.folder)
    except (AssertionError,KeyError,ValueError,FileNotFoundError) as exc:
        result=dict(verified=False,qualification=False,error=f'{type(exc).__name__}: {exc}',
            verifier_sha256=digest(__file__),scope='Raw audit rejected; do not count this episode as verified native evidence.')
    if args.output:
        with args.output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(result,indent=2,allow_nan=False),flush=True)
    if not result['verified']:raise SystemExit(1)


if __name__=='__main__':main()
