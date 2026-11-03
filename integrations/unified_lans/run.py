"""One command exercises the complete integrated control path and saves raw telemetry."""
import argparse
from contextlib import nullcontext
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import platform
import time
import numpy as np
from .controller import Pipeline
from .physics import Config
from .inference import AsyncPPO, sha
from .learning import calibrate, train
from .simulation import initial, move_npcs, Network, truth_metrics
from .traffic import contact_time, conflict_time, Supervisor


def clean(value):
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,(float,np.floating)):return float(value) if math.isfinite(value) else None
    if isinstance(value,np.bool_):return bool(value)
    return value


def write(path, value):
    path.write_text(json.dumps(clean(value),indent=2,allow_nan=False)+'\n')


CASES=[('following','nominal',0.,'',1.),('merge','nominal',0.,'',1.),
       ('crossing','nominal',0.,'',1.),('curved','nominal',0.,'',1.),
       ('following','delayed',.1,'',1.),('merge','loss',0.,'',1.),
       ('crossing','reordered',0.,'',1.),('following','blackout',0.,'',1.),
       ('curved','ego_blackout',0.,'',1.),('curved','nominal',0.,'stall',1.),
       ('curved','nominal',0.,'crash',1.),('curved','nominal',0.,'',.8)]


def episode(case, mode, policy, output, gains, seconds, seed, paced):
    scenario,network_profile,delay,fault,stiffness=case
    cfg=Config();route,ego,npcs=initial(scenario)
    pipe=Pipeline(route,scenario,cfg,delay,gains,mode);pipe.expected=set(npcs)
    network=Network(seed,network_profile);rows=[];accepted=0;rejected=0;proposed=0;delivered=0
    worker_ctx=AsyncPPO(policy,.3 if fault=='stall' else 0.) if mode in ('hybrid','ppo') else nullcontext(None)
    output.mkdir(parents=True,exist_ok=False)
    with worker_ctx as worker:
        started=time.monotonic();previous_acc=0.
        for tick in range(round(seconds/cfg.dt)):
            now=tick*cfg.dt
            network.emit(now,ego,npcs,pipe.inbox)
            if worker is not None:
                if fault=='crash' and now>=1. and worker.process.is_alive():
                    worker.process.terminate();worker.process.join(timeout=2)
                response=worker.poll()
                if response is not None:
                    delivered+=1
                    if pipe.accept(response,now):accepted+=1
                    else:rejected+=1
                features=pipe.features(now)
                packet=pipe.inbox.latest.get('ego')
                if packet is not None and features is not None:
                    proposed+=int(worker.submit(features,packet.observed_s,now))
            before=ego.copy();previous=pipe.applied
            # Evaluation-only current-truth hazard reference never enters the controller.
            reference_ttc=min(min(contact_time(ego,n,2*cfg.vehicle_radius+cfg.buffer),
                                  conflict_time(ego,n,2*cfg.vehicle_radius+cfg.buffer)) for n in npcs.values())
            reference_clearance=min(np.linalg.norm(n[:2]-ego[:2])-2*cfg.vehicle_radius-cfg.buffer for n in npcs.values())
            reference_hazard=reference_ttc<=Supervisor.THRESHOLDS[scenario][1] or reference_clearance<=0
            decision=pipe.decide(now,worker_failed=bool(worker and worker.failed))
            ego=pipe.apply(now,ego,stiffness)
            move_npcs(npcs,cfg.dt,route,scenario)
            truth=truth_metrics(ego,npcs,route,cfg)
            row=dict(tick=tick,time_s=now,**decision,**truth,
                     state_before=before.tolist(),state_after=ego.tolist(),
                     npc_truth={k:v.tolist() for k,v in npcs.items()},
                     ego_measurement_s=pipe.inbox.latest['ego'].observed_s if 'ego' in pipe.inbox.latest else None,
                     neighbor_measurement_s={k:p.observed_s for k,p in pipe.inbox.latest.items() if k!='ego'},
                     applied_steering=pipe.applied.steering,applied_accel=pipe.applied.accel,
                     steering_rate=(pipe.applied.steering-previous.steering)/cfg.dt,
                     jerk=(pipe.applied.accel-previous_acc)/cfg.dt,
                     worker_failed=bool(worker and worker.failed))
            row.update(reference_ttc=reference_ttc,reference_hazard=bool(reference_hazard))
            previous_acc=pipe.applied.accel;rows.append(row)
            if truth['collision'] or abs(truth['error'])>2.5:break
            if paced:
                remaining=started+(tick+1)*cfg.dt-time.monotonic()
                if remaining>0:time.sleep(remaining)
    raw=output/'ticks.jsonl'
    raw.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
    tp=sum(r['risk']!='SAFE' and r['reference_hazard'] for r in rows)
    fp=sum(r['risk']!='SAFE' and not r['reference_hazard'] for r in rows)
    fn=sum(r['risk']=='SAFE' and r['reference_hazard'] for r in rows)
    summary=dict(case_dir=output.name,scenario=scenario,network=network_profile,command_delay_s=delay,fault=fault,stiffness=stiffness,
                 mode=mode,seed=seed,ticks=len(rows),expected_ticks=round(seconds/cfg.dt),wall_paced=paced,
                 collision=any(r['collision'] for r in rows),corridor_exceeded=any(r['corridor_exceeded'] for r in rows),
                 completed_duration=len(rows)==round(seconds/cfg.dt),
                 rmse_m=float(np.sqrt(np.mean([r['error']**2 for r in rows]))),
                 max_error_m=max(abs(r['error']) for r in rows),
                 minimum_clearance_m=min(r['true_clearance'] for r in rows),
                 steering_rate_rms=float(np.sqrt(np.mean([r['steering_rate']**2 for r in rows]))),
                 jerk_rms=float(np.sqrt(np.mean([r['jerk']**2 for r in rows]))),
                 interventions=sum(r['risk']!='SAFE' for r in rows),
                 warning_tp_ticks=tp,warning_fp_ticks=fp,warning_fn_ticks=fn,
                 warning_precision=tp/(tp+fp) if tp+fp else None,
                 warning_recall=tp/(tp+fn) if tp+fn else None,
                 warning_reference='current-truth CV hazard proxy; not future collision ground truth',
                 travel_m=float(ego[0]),elapsed_sim_s=len(rows)*cfg.dt,
                 first_brake_s=next((r['time_s'] for r in rows if r['applied_accel']<-.1),None),
                 ppo_selected=sum(r['source']=='ppo' for r in rows),
                 deterministic_selected=sum(r['source']=='deterministic' for r in rows),
                 proposed=proposed,delivered=delivered,accepted=accepted,rejected=rejected,
                 network_dropped=network.dropped,out_of_order_or_invalid_rejected=pipe.inbox.rejected,
                 deadline_misses=sum(r['control_ms']>1000*cfg.dt for r in rows),
                 control_p95_ms=float(np.percentile([r['control_ms'] for r in rows],95)),raw_sha256=sha(raw))
    write(output/'summary.json',summary)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    t=sub.add_parser('train');t.add_argument('--output',required=True);t.add_argument('--steps',type=int,default=2048)
    t.add_argument('--seeds',type=int,nargs='+',default=[42,43,44])
    c=sub.add_parser('calibrate');c.add_argument('--output',required=True)
    r=sub.add_parser('run');r.add_argument('--output',required=True);r.add_argument('--policy')
    r.add_argument('--calibration');r.add_argument('--seconds',type=float,default=3.)
    r.add_argument('--mode',choices=['lqr','fixed','deterministic','ppo','hybrid'],default='hybrid')
    r.add_argument('--suite',action='store_true');r.add_argument('--compare',action='store_true')
    r.add_argument('--fast',action='store_true',help='unpaced simulation; async delivery statistics are not wall-paced timing evidence')
    r.add_argument('--seed',type=int,default=700)
    a=parser.parse_args()
    if a.command=='train':
        if a.steps<128 or len(set(a.seeds))!=len(a.seeds):parser.error('use >=128 steps and unique seeds')
        train(a.output,a.seeds,a.steps);return
    if a.command=='calibrate':print(calibrate(a.output));return
    if not math.isfinite(a.seconds) or a.seconds<=0:parser.error('positive finite duration required')
    if (a.mode in ('ppo','hybrid') or a.compare) and not a.policy:parser.error('--policy is required for PPO/hybrid')
    if round(a.seconds/.05)<1:parser.error('duration must span at least one tick')
    gains=(.02,.02)
    if a.calibration:
        selected=json.loads(Path(a.calibration).read_text())['selected'];gains=(selected['ky'],selected['kpsi'])
    output=Path(a.output);output.mkdir(parents=True,exist_ok=False)
    source={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}
    write(output/'provenance.json',dict(config=asdict(Config()),sources=source,python=platform.python_version(),
        policy_manifest=sha(Path(a.policy)/'manifest.json') if a.policy else None,
        gains=gains,seed=a.seed,scope='new integration validation, not historical confirmation or safety certification'))
    summaries=[]
    for index,case in enumerate(CASES if a.suite else CASES[:1]):
        for mode in (['lqr','fixed','deterministic','ppo','hybrid'] if a.compare else [a.mode]):
            result=episode(case,mode,a.policy,output/f'{index:02d}-{mode}',gains,a.seconds,a.seed+index,not a.fast)
            summaries.append(result)
            print(json.dumps(clean(result),allow_nan=False),flush=True)
    write(output/'summary.json',summaries)


if __name__=='__main__':main()
