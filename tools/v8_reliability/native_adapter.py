"""Native Webots sensor/actuator bridge; Python prediction never advances ego.

The Driver is supplied by the tiny Webots entry point. Keeping construction out
of module scope makes spawned MPC/PPO workers safe to import this module.
"""
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
import json,math,time,resource
import numpy as np
from integrations.unified_lans.physics import Config,Command,errors
from integrations.unified_lans.traffic import Packet
from integrations.unified_lans.inference import AsyncPPO,sha
from integrations.unified_lans.run import clean
from tools.unified_campaign.study import StudyRoute
from tools.unified_control_v4.control import gain_table,GRID
from .traffic_guard import Controller, Synchronous
from tools.unified_control_v8.control import Controller as OriginalV8
from .timing import Schedule,control_affinity


class Frame:
    """Fixed map transform after physical warmup; never changes vehicle pose."""
    def __init__(self,initial,route,lateral,heading):
        y,h,_=route.geometry(0.)
        self.origin=np.asarray(initial[:2],float).copy()
        self.angle=float(h+heading-initial[2]);self.offset=np.array([0.,y+lateral])
        c,s=math.cos(self.angle),math.sin(self.angle)
        self.rotation=np.array([[c,-s],[s,c]])
    def transform(self,state):
        result=np.asarray(state,float).copy()
        result[:2]=self.rotation@(result[:2]-self.origin)+self.offset
        result[2]=math.atan2(math.sin(result[2]+self.angle),math.cos(result[2]+self.angle))
        return result
    def metadata(self):
        return dict(origin_world_cg_m=self.origin.tolist(),angle_rad=self.angle,
                    offset_map_m=self.offset.tolist(),physical_pose_changed=False)


def measured_state(node,left,right):
    pos=node.getPosition();rotation=node.getOrientation();velocity=node.getVelocity()
    yaw=math.atan2(rotation[3],rotation[0]);c,s=math.cos(yaw),math.sin(yaw)
    state=np.array([pos[0]+1.4*c,pos[1]+1.4*s,yaw,
        velocity[0]*c+velocity[1]*s,-velocity[0]*s+velocity[1]*c,velocity[5]])
    steering=-(left.getValue()+right.getValue())/2
    if not np.isfinite(state).all() or not math.isfinite(steering):raise ValueError('nonfinite native sensor')
    return state,float(steering)


def native_main(driver,case):
    out=Path(case['output']);out.mkdir(parents=True,exist_ok=True)
    cfg=Config(horizon=2.);physics_dt=driver.getBasicTimeStep()/1000
    substeps=round(cfg.dt/physics_dt)
    assert abs(physics_dt*substeps-cfg.dt)<1e-10 and physics_dt==.001
    node=driver.getSelf();left=driver.getDevice('left_steer_sensor');right=driver.getDevice('right_steer_sensor')
    left.enable(round(physics_dt*1000));right.enable(round(physics_dt*1000))
    for name in ('left_steer','right_steer'):driver.getDevice(name).setControlPID(1/physics_dt,0,0)
    route=StudyRoute(case['route'],1,case['phase'],case['amplitude'])
    scenario='curved' if case['route']=='sine' else 'following'
    params=dict(case['controller_kwargs'],adaptive=case['mode']=='hybrid',mpc=case['mode']=='hybrid')
    execution=case.get('execution','process')
    cls=Controller if execution=='process' else (OriginalV8 if execution=='original-v8' else Synchronous)
    if execution=='process':params['planner_backend']='process'
    def make_controller(selected_route=route):
        selected_scenario='following' if selected_route.kind=='straight' else scenario
        c=cls(selected_route,selected_scenario,cfg,0.,gains=(.04,0.),mode=case['mode'],clock=time.monotonic,
            target_speed=case['speed'],deterministic_grid=GRID if case['mode']=='hybrid' else (),penalty=16.,**params)
        c.expected=set();return c
    startup=time.perf_counter()
    for stiffness in [i/20 for i in range(14,27)]:gain_table(16.,stiffness)
    # Exercise admission on a fixed feasible startup fixture. A curved case's
    # legitimately infeasible solver response must not disable its fallback.
    warm=make_controller(StudyRoute('straight',1,0.,1.))
    try:
        y,h,_=warm.route.geometry(0.)
        # Warm returned-plan projection/admission too, not only request submit.
        # Synthetic startup packets never move the physical car or enter scores.
        for i in range(8):
            now=i*cfg.dt
            warm.inbox.ingest(Packet('ego',i,now,(0.,y+.3,h+.005,case['speed'],0.,0.)),now)
            warm.decide(now)
            time.sleep(cfg.dt)
        if warm.planner is not None and hasattr(warm.planner,'backend'):assert warm.planner.accepted>0,'Native startup never exercised returned planner response'
        (out/'startup-admission.json').write_text(json.dumps(dict(warm_route='fixed_straight_fixture',
            actual_scoring_route=route.kind,actual_case_fallback_permitted=True,
            returned_plans_accepted=getattr(warm.planner,'accepted',None)),indent=2)+'\n')
    finally:getattr(warm,'close',lambda:None)()
    with ExitStack() as cleanup:
        controller=make_controller();cleanup.callback(getattr(controller,'close',lambda:None))
        worker=AsyncPPO(case['policy']) if case['mode']=='hybrid' else None
        if worker is not None:cleanup.callback(worker.close)
        owned=[getattr(getattr(controller.planner,'backend',None),'process',None),worker.process if worker is not None else None]
        affinity=cleanup.enter_context(control_affinity(owned))
        startup_s=time.perf_counter()-startup
        driver.setSteeringAngle(0.);driver.setCruisingSpeed(case['speed']*3.6)
        for _ in range(round(10/physics_dt)):
            if driver.step()==-1:raise RuntimeError('native simulator stopped during warmup')
        initial,_=measured_state(node,left,right)
        frame=Frame(initial,route,case['lateral'],case['heading'])
        initial_mapped=frame.transform(initial);simulation_origin=driver.getTime()
        (out/'map-frame.json').write_text(json.dumps(frame.metadata(),indent=2)+'\n')
        p=node.getField('physics').getSFNode()
        vehicle=dict(chassis_mass_kg=p.getField('mass').getSFFloat(),
            chassis_center_of_mass_m=p.getField('centerOfMass').getMFVec3f(0),
            chassis_inertia=p.getField('inertiaMatrix').getMFVec3f(0),
            nominal_total_mass_kg=1650,nominal_total_cg_x_m=1.4,nominal_total_yaw_inertia=4224,
            physics_step_s=physics_dt,control_period_s=cfg.dt,
            measured_warmup_speed_m_s=float(initial[3]),initial_map_state=initial_mapped.tolist(),
            startup_outside_timing_s=startup_s,config=asdict(cfg),affinity=affinity,native_actuator_rate_limit_rad_s=.59)
        (out/'vehicle.json').write_text(json.dumps(vehicle,indent=2)+'\n')
        rows=[];timing=[];actuator=0.;previous_measured=0.;schedule=Schedule(cfg.dt);start=schedule.origin;failure=None
        with (out/'ticks.jsonl').open('x') as trace:
            for i in range(round(case['duration']/cfg.dt)):
                schedule.wait(i)
                now=i*cfg.dt;tick_start=time.perf_counter();tick_release=time.monotonic()
                cpu_start=time.process_time();usage_before=resource.getrusage(resource.RUSAGE_SELF)
                world_before,measured_before=measured_state(node,left,right)
                before=frame.transform(world_before)
                if before[3]<0:raise ValueError('negative native forward speed')
                assert controller.inbox.ingest(Packet('ego',i,now,tuple(before)),now)
                accepted=None;submitted=False;reply_sequence=None
                if worker is not None:
                    reply=worker.poll()
                    if reply is not None:accepted=controller.accept(reply,now);reply_sequence=reply.sequence
                    features=controller.features(now)
                    if features is not None:submitted=worker.submit(features,now,now)
                previous=controller.applied;decision=controller.decide(now,False if worker is None else worker.failed)
                response_ms=1000*(time.perf_counter()-tick_start)
                response_cpu_ms=1000*(time.process_time()-cpu_start)
                scheduled_response_ms=1000*(time.monotonic()-(start+now))
                # Consume the common command FIFO without calling Pipeline.apply:
                # only Webots integrates the actual ego body and tire contacts.
                while controller.pending and controller.pending[0][0]<=now+1e-9:
                    _,controller.applied=controller.pending.pop(0)
                command=controller.applied
                cruise_target=float(np.clip(before[3]+command.accel*cfg.dt,0.,case['speed']))
                max_measured_rate=0.;max_actuator_rate=0.;actuator_before=actuator
                physics_start=time.perf_counter()
                for _ in range(substeps):
                    old=actuator
                    actuator=float(np.clip(command.steering,actuator-.59*physics_dt,actuator+.59*physics_dt))
                    max_actuator_rate=max(max_actuator_rate,abs(actuator-old)/physics_dt)
                    driver.setSteeringAngle(-actuator);driver.setCruisingSpeed(cruise_target*3.6)
                    if driver.step()==-1:raise RuntimeError('native simulator stopped within measured episode')
                    measured=-(left.getValue()+right.getValue())/2
                    max_measured_rate=max(max_measured_rate,abs(measured-previous_measured)/physics_dt)
                    previous_measured=measured
                physics_wall_ms=1000*(time.perf_counter()-physics_start)
                controller.history.append((now,now+cfg.dt,command))
                controller.history=[h for h in controller.history if h[1]>=now-2*cfg.ego_ttl]
                world_after,measured_after=measured_state(node,left,right);after=frame.transform(world_after)
                e,_=errors(after,route);cycle_ms=1000*(time.perf_counter()-tick_start)
                row=dict(**decision,tick=i,time_s=now,sim_time_before_s=simulation_origin+now,
                    sim_time_after_s=driver.getTime(),state_before=before.tolist(),state_after=after.tolist(),
                    world_state_before=world_before.tolist(),world_state_after=world_after.tolist(),
                    measured_steering_before=measured_before,measured_steering_after=measured_after,
                    actuator_before=actuator_before,actuator_after=actuator,max_actuator_rate=max_actuator_rate,
                    max_measured_rate=max_measured_rate,applied_steering=command.steering,applied_accel=command.accel,
                    steering_rate=(command.steering-previous.steering)/cfg.dt,cruise_target_m_s=cruise_target,
                    error=float(e[0]),heading_error=float(e[2]),corridor_exceeded=bool(abs(e[0])>1.75),
                    collision_assessed=False,accepted=accepted,submitted=submitted,reply_sequence=reply_sequence,
                    worker_failed=False if worker is None else worker.failed,response_ms=response_ms,prelog_cycle_ms=cycle_ms,
                    response_cpu_ms=response_cpu_ms,native_physics_wall_ms=physics_wall_ms,
                    release_lateness_ms=1000*(tick_release-(start+now)),scheduled_response_ms=scheduled_response_ms,
                    prelog_schedule_lateness_ms=1000*(time.monotonic()-(start+(i+1)*cfg.dt)))
                trace_start=time.perf_counter()
                trace.write(json.dumps(clean(row),allow_nan=False)+'\n');trace.flush();rows.append(row)
                trace_write_ms=1000*(time.perf_counter()-trace_start)
                usage_after=resource.getrusage(resource.RUSAGE_SELF);owner_cpu_ms=1000*(time.process_time()-cpu_start)
                complete_cycle_ms=1000*(time.perf_counter()-tick_start)
                scheduled_cycle_ms=1000*(time.monotonic()-(start+i*cfg.dt))
                timing.append(dict(tick=i,complete_cycle_ms=complete_cycle_ms,scheduled_cycle_ms=scheduled_cycle_ms,
                    owner_cpu_ms=owner_cpu_ms,response_cpu_ms=response_cpu_ms,native_physics_wall_ms=physics_wall_ms,
                    trace_write_ms=trace_write_ms,voluntary_context_switches=usage_after.ru_nvcsw-usage_before.ru_nvcsw,
                    involuntary_context_switches=usage_after.ru_nivcsw-usage_before.ru_nivcsw))
                if abs(e[0])>2.5:failure='tracking_envelope';break
                # Next release stays on the original schedule even after a miss.
        (out/'timing.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in timing))
        expected=round(case['duration']/cfg.dt)
        result=dict(case=case,ticks=len(rows),expected_ticks=expected,completed=len(rows)==expected,
            controller_revision=2,
            failure=failure,role='native_single_vehicle_transfer_not_full_traffic_validation',
            rmse_m=float(np.sqrt((sum(r['error']**2 for r in rows)+(expected-len(rows))*6.25)/expected)),
            heading_rmse_rad=float(np.sqrt(np.mean([r['heading_error']**2 for r in rows]))),
            steering_rate_rms=float(np.sqrt(np.mean([r['steering_rate']**2 for r in rows]))),
            corridor_exceedances=sum(r['corridor_exceeded'] for r in rows),
            max_error_m=max(abs(r['error']) for r in rows),progress_m=rows[-1]['state_after'][0],
            response_misses=sum(r['response_ms']>50 for r in rows),cycle_misses=sum(r['complete_cycle_ms']>50 for r in timing),
            scheduled_response_misses=sum(r['scheduled_response_ms']>50 for r in rows),
            scheduled_cycle_misses=sum(r['scheduled_cycle_ms']>50 for r in timing),
            response_max_ms=max(r['response_ms'] for r in rows),cycle_max_ms=max(r['complete_cycle_ms'] for r in timing),
            ppo_ticks=sum(r['source']=='ppo' for r in rows),mpc_ticks=sum(bool(r.get('planned_candidate_selected',False)) for r in rows),
            max_command_rate=max(abs(r['steering_rate']) for r in rows),
            max_actuator_rate=max(r['max_actuator_rate'] for r in rows),
            max_measured_rate=max(r['max_measured_rate'] for r in rows),
            raw_sha256=sha(out/'ticks.jsonl'),timing_sha256=sha(out/'timing.jsonl'),
            timing_definition='complete cycle through inline trace write/flush; fixed scheduled releases; timing sidecar serialized after episode',
            policies_unchanged=True)
        (out/'summary.json').write_text(json.dumps(clean(result),indent=2)+'\n')
        return result
