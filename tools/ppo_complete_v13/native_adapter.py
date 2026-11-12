"""Physically native ego and moving traffic; no Python plant integration."""
from contextlib import ExitStack
from pathlib import Path
import json,math,time
import numpy as np
from integrations.unified_lans.physics import Config,Command,errors
from integrations.unified_lans.simulation import Network,truth_metrics
from tools.unified_campaign.study import StudyRoute
from tools.unified_control_v9.native_adapter import Frame
from tools.ppo_benefit_v10.core import PARAMS
from .actuation import TorqueActuator
from .learning import controller_class,observe,RunningStats,CONTRACT
from .plans import CorrectionProposal
from .runtime import PolicyWorker,owner_tick,sha
from .headroom import write,jsonable


def body_state(node):
    pos=node.getPosition();matrix=node.getOrientation();velocity=node.getVelocity()
    yaw=math.atan2(matrix[3],matrix[0]);c,s=math.cos(yaw),math.sin(yaw)
    result=np.array([pos[0]+1.4*c,pos[1]+1.4*s,yaw,velocity[0]*c+velocity[1]*s,
        -velocity[0]*s+velocity[1]*c,velocity[5]],float)
    if not np.isfinite(result).all():raise ValueError('nonfinite native pose/velocity')
    return result


def steering(left,right):
    a,b=float(left.getValue()),float(right.getValue());ta,tb=math.tan(a),math.tan(b)
    # Invert Ackermann geometry to the same virtual bicycle angle used by the
    # controller. The mean physical wheel angle is a different quantity.
    value=-math.atan(2*ta*tb/(ta+tb)) if abs(ta+tb)>1e-10 else -.5*(a+b)
    if not math.isfinite(value):raise ValueError('nonfinite measured steering')
    return value


def make_controller(case,mode):
    cfg=Config(horizon=2.);route=StudyRoute(case['route_kind'],case['mirror'],case['phase'],case['amplitude'])
    params=dict(PARAMS,adaptive=mode!='lqr',mpc=mode!='lqr');params.update(case['controller_kwargs'])
    controller=controller_class()(route,case['scenario'],cfg,case['delay'],gains=(.04,0.),
        mode='lqr' if mode=='lqr' else 'deterministic',clock=time.monotonic,target_speed=case['speed'],
        deterministic_grid=() if mode=='lqr' else (-.08,-.04,0.,.04,.08),penalty=16.,**params)
    controller.expected=set(case['initial_npcs']);return controller


def warm_math(case):
    from tools.unified_campaign.study import Clock
    from integrations.unified_lans.traffic import Packet
    from tools.unified_control_v4.control import gain_table
    for i in range(14,27):gain_table(16.,i/20)
    c=make_controller(case,case['mode']);clock=Clock();c.clock=clock
    state=np.asarray(case['initial_ego']);npcs={n:np.asarray(z) for n,z in case['initial_npcs'].items()}
    # Startup-only synthetic trajectories warm model identification and every
    # current-anchor signature, including the native Python-float timestamps.
    # These values never advance a native car or enter any measured score.
    for i in range(40):
        now=float(i*.05);clock.now=now
        c.inbox.ingest(Packet('ego',i,now,tuple(state)),now)
        for name,z in npcs.items():c.inbox.ingest(Packet(name,i,now,tuple(z)),now)
        ctx=c.prepare(now);c.score_candidate(ctx,np.full(8,-.01));c.finish(ctx)
        state=c.predict(state,c.issued,.05)
        for z in npcs.values():z[0]+=.05*z[3]*math.cos(z[2]);z[1]+=.05*z[3]*math.sin(z[2])


def native_main(driver,case):
    out=Path(case['output']);cfg=Config(horizon=2.);dt=driver.getBasicTimeStep()/1000
    assert abs(dt-.001)<1e-12;substeps=round(cfg.dt/dt)
    node=driver.getSelf();left=driver.getDevice('left_steer_sensor');right=driver.getDevice('right_steer_sensor')
    left.enable(1);right.enable(1)
    for name in ('left_steer','right_steer'):
        motor=driver.getDevice(name);motor.setControlPID(1/dt,0,0);motor.setVelocity(cfg.steering_rate)
    npcs={name:driver.getFromDef(defname) for name,defname in case['npc_defs'].items()}
    if any(n is None for n in npcs.values()):raise ValueError('physical NPC node missing')
    startup=time.monotonic()
    if not case.get('warmup_only'):warm_math(case)
    with ExitStack() as cleanup:
        learned=case['mode'] in ('ppo','bc','continued_bc')
        worker=cleanup.enter_context(PolicyWorker(case['policy'],CONTRACT,55,bc=case['mode']=='bc')) if learned else None
        c=make_controller(case,case['mode']);route=c.route
        driver.setSteeringAngle(0.);driver.setBrakeIntensity(0.);driver.setCruisingSpeed(case['speed']*3.6)
        for _ in range(round(10/dt)):
            if driver.step()==-1:raise RuntimeError('native stopped during physical warmup')
        initial=body_state(node);frame=Frame(initial,route,case['lateral'],case['heading'])
        if case.get('warmup_only'):
            scene=dict(warmup_only=True,fixture_sha256=case['fixture_sha256'],ego_native=initial,
                npc_native={name:body_state(n) for name,n in npcs.items()},physical_warmup_steps=round(10/dt),
                simulation_time_s=driver.getTime(),role='Policy-free native initial-scene calibration; no controller outcome or pose writes')
            write(out/'scene-state.json',scene)
            result=dict(completed=True,warmup_only=True,policy_tested=False,physics_steps=round(10/dt),
                role=case['role'],scene_state_sha256=sha(out/'scene-state.json'))
            write(out/'summary.json',result);return result
        if not case.get('scene_calibration'):raise ValueError('Measured native episode requires policy-free initial-scene calibration')
        # Start positions were selected from a separate policy-free native
        # warmup displacement. All cars arrive here through physical motion;
        # no pose/velocity/force is overwritten, even before measurement.
        initial_traffic={}
        for name,n in npcs.items():
            actual=frame.transform(body_state(n));initial_traffic[name]=actual.tolist()
            if np.linalg.norm(actual[:2]-np.asarray(case['initial_npcs'][name])[:2])>.1:
                raise RuntimeError('native traffic initialization was not synchronized before measurement')
        origin=driver.getTime()
        write(out/'initialization.json',dict(frame=frame.metadata(),simulation_origin_s=origin,
            initial_ego=frame.transform(initial),initial_traffic=initial_traffic,
            initial_equivalent_bicycle_steering=steering(left,right),
            initialization_synchronization_physics_steps=0,
            npc_pose_initializations={name:0 for name in npcs},ego_pose_overwritten=False,
            npc_pose_overwritten_during_measurement=False,ego_python_integrated=False,npc_python_integrated=False))
        running=RunningStats();last_action=np.zeros(8);network=Network(case['network_seed'],case['network'])
        actuator=TorqueActuator();steer_target=steering(left,right);last_desired=Command();last_measured=steer_target
        active_command=Command()
        rows=[];walls={};wall_origin=time.monotonic();startup_s=wall_origin-startup
        with (out/'ticks.jsonl').open('x') as trace:
            for i in range(120):
                now=i*cfg.dt;release=time.monotonic();capture_wall=time.monotonic()
                before=frame.transform(body_state(node))
                traffic_before={name:frame.transform(body_state(n)) for name,n in npcs.items()}
                network.emit(now,before,traffic_before,c.inbox);walls[network.sequence]=capture_wall
                packet=c.inbox.latest.get('ego');source_wall=capture_wall if packet is None else walls[packet.sequence]
                def query(ctx):
                    value,valid=observe(c,ctx,running,last_action)
                    return value if valid else None
                decision,context,reply=owner_tick(c,now,query,CorrectionProposal,worker=worker,
                    wall_observed=source_wall,release_wall=release,scheduled_release_wall=wall_origin+now)
                if reply is not None:running.note_proposal(reply);last_action=np.asarray(reply.action)
                while c.pending and c.pending[0][0]<=now+1e-9:_,active_command=c.pending.pop(0)
                command=active_command;command_rate=(command.steering-last_desired.steering)/cfg.dt;last_desired=command
                initial_truth=truth_metrics(before,traffic_before,route,cfg)
                minimum=initial_truth['true_clearance'];peak_error=abs(initial_truth['error'])
                collision=bool(initial_truth['collision']);corridor=bool(initial_truth['corridor_exceeded'])
                rate_max=0.;rate_energy=0.;steers=[];accels=[];actuation_rows=[]
                speed_before=float(before[3])
                for substep in range(substeps):
                    previous_target=steer_target
                    steer_target=float(np.clip(command.steering,steer_target-cfg.steering_rate*dt,steer_target+cfg.steering_rate*dt))
                    driver.setSteeringAngle(-steer_target)
                    metadata=actuator.update(driver,float(speed_before),command.accel,dt)
                    if driver.step()==-1:raise RuntimeError('native stopped during measured physics')
                    after=frame.transform(body_state(node));traffic={name:frame.transform(body_state(n)) for name,n in npcs.items()}
                    truth=truth_metrics(after,traffic,route,cfg);measured=steering(left,right)
                    measured_rate=(measured-last_measured)/dt;last_measured=measured
                    rate_max=max(rate_max,abs(measured_rate));rate_energy+=measured_rate**2;minimum=min(minimum,truth['true_clearance'])
                    peak_error=max(peak_error,abs(truth['error']));collision|=bool(truth['collision']);corridor|=bool(truth['corridor_exceeded'])
                    steers.append(measured);accels.append((after[3]-speed_before)/dt)
                    actuation_rows.append(dict(substep=substep,simulation_time_s=driver.getTime(),state=after,
                        traffic=traffic,equivalent_bicycle_steering=measured,actuator_target=steer_target,
                        actuator_target_rate=(steer_target-previous_target)/dt,measured_steering_rate=measured_rate,
                        clearance=truth['true_clearance'],error=truth['error'],achieved_accel_m_s2=accels[-1],**metadata))
                    speed_before=float(after[3])
                measured_end=steering(left,right)
                c.history.append((now,now+cfg.dt,Command(float(np.mean(steers)),float(np.mean(accels)))))
                c.history=[h for h in c.history if h[1]>=now-c.backup_limit_s-cfg.ego_ttl]
                c.applied=Command(measured_end,float(np.mean(accels)))
                row=dict(**decision,tick=i,time_s=now,simulation_before_s=origin+now,simulation_after_s=driver.getTime(),
                    lqr_model_values=[list(v) for v in context.lqr_values],
                    anchor_model_values=[list(v) for v in context.reference_values],
                    state_before=before,state_after=after,npc_truth_before=traffic_before,npc_truth=traffic,
                    applied_steering=command.steering,applied_accel=command.accel,steering_rate=command_rate,
                    measured_equivalent_steering=measured_end,measured_steering_rate_max=rate_max,
                    measured_steering_rate_rms=float(math.sqrt(rate_energy/substeps)),
                    original_frame_wall=source_wall,source_ego_sequence=None if packet is None else packet.sequence,
                    source_ego_observed_s=None if packet is None else packet.observed_s,
                    actual_accel_mean=float(np.mean(accels)),native_error=float(truth['error']),error=float(truth['error']),
                    heading_error=float(truth['heading_error']),true_clearance=minimum,max_interval_error=peak_error,
                    collision=collision,corridor_exceeded=corridor,physics=actuation_rows,
                    native_ego_physics=True,native_traffic_physics=True,python_ego_integrated=False,
                    pose_overwritten_during_measurement=False,cycle_ms=1000*(time.monotonic()-release))
                rows.append(row)
                if collision or corridor:break
                wait=wall_origin+(i+1)*cfg.dt-time.monotonic()
                if wait>0:time.sleep(wait)
            # The bounded6s native mission retains all6,000 physical samples
            # in memory. Serialize complete raw evidence after measurement so
            # omitted JSON/disk work cannot hide inside an understated cycle.
            serialization_started=time.monotonic()
            for row in rows:trace.write(json.dumps(jsonable(row),allow_nan=False)+'\n')
            trace.flush();serialization_s=time.monotonic()-serialization_started
        n=len(rows);result=dict(case=case,ticks=n,expected_ticks=120,failed=n<120 or any(r['collision'] or r['corridor_exceeded'] for r in rows),
            rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(120-n)*6.25)/120),
            heading_rms=float(np.sqrt(np.mean([r['heading_error']**2 for r in rows]))),
            commanded_rate_rms=float(np.sqrt(np.mean([r['steering_rate']**2 for r in rows]))),
            rate_rms=float(np.sqrt(np.mean([r['measured_steering_rate_rms']**2 for r in rows]))),progress_m=float(rows[-1]['state_after'][0]),
            collisions=sum(r['collision'] for r in rows),corridor_failures=sum(r['corridor_exceeded'] for r in rows),
            owner_response_misses=sum(r['owner_response_miss'] for r in rows),
            scheduled_response_misses=sum(r.get('scheduled_owner_response_miss',False) for r in rows),
            owner_max_ms=max(r['complete_decision_ms'] for r in rows),cycle_max_ms=max(r['cycle_ms'] for r in rows),
            policy_selected_ticks=sum(r['sequence_plan_selected'] for r in rows),
            minimum_true_clearance=min(r['true_clearance'] for r in rows),startup_outside_measured_s=startup_s,
            raw_serialization_after_measurement_s=serialization_s,
            native_ego_physics=True,native_traffic_physics=True,python_ego_integrated=False,npc_python_integrated=False,
            collision_assessed=True,collision_geometry='Unchanged 2.3m body circles on native poses at every1ms physics step',
            mesh_contact_collision_assessed=False,raw_sha256=sha(out/'ticks.jsonl'),role=case['role'])
        write(out/'summary.json',result);return result
