"""Training-only causal plan-search probe before committing a new PPO budget."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import json,math,multiprocessing as mp,shutil
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.run import clean
from integrations.unified_lans.simulation import move_npcs,truth_metrics
from tools.unified_control_v4.calibrate import cases
from tools.unified_control_v8.control import Controller as Base
from tools.unified_control_v9.learning import setup
from tools.ppo_benefit_v10.core import predicted_application,PARAMS
from .control import Controller,PlanProposal

ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'results/ppo-plan-v11/probe'


def dump(path,value):path.write_text(json.dumps(clean(value),indent=2,allow_nan=False)+'\n')


def teacher(c,now):
    if .05+c.delay>=.15-1e-9:return tuple(np.zeros(8)),dict(reason='strict_expiry',eligible_trials=0)
    z=predicted_application(c,now)
    if z is None:return tuple(np.zeros(8)),dict(reason='missing_ego',eligible_trials=0)
    old=c.supervisor.state;risk=c.supervisor.assess(z,c.inbox,c.expected,now+.05,now+.05+c.delay);c.supervisor.state=old
    if risk.state=='DANGER':return tuple(np.zeros(8)),dict(reason='danger',eligible_trials=0)
    accel=c.supervisor.acceleration(float(np.clip(.8*(c.target_speed-z[3]),-6,2.5)),risk)
    knobs=np.zeros(8);value,margin,_,_=c.score_plan(z,knobs,0,accel,c.issued,risk.vehicles)
    best=value if margin>=0 else math.inf;eligible=0
    for _ in range(2):
        for amplitude in (.02,.005):
            for knot in range(8):
                chosen=knobs.copy();score=best
                for sign in (-1.,1.):
                    candidate=knobs.copy();candidate[knot]=np.clip(candidate[knot]+sign*amplitude/.08,-1,1)
                    cost,clear,_,_=c.score_plan(z,candidate,0,accel,c.issued,risk.vehicles)
                    eligible+=clear>=0
                    if clear>=0 and cost<score-1e-8:chosen=candidate;score=cost
                knobs=chosen;best=score
    return tuple(float(x) for x in knobs),dict(reason='causal_searched',eligible_trials=eligible,estimated_application_state=z.tolist(),predicted_cost=best if math.isfinite(best) else None)


def prepare():
    DATA.mkdir(parents=True,exist_ok=False)
    files=[*Path(__file__).parent.glob('*.py'),Path(__file__).parent/'PROTOCOL.md',
        ROOT/'tools/ppo_benefit_v10/core.py',ROOT/'tools/unified_control_v9/learning.py',
        *(ROOT/'integrations/unified_lans').glob('*.py'),ROOT/'tools/unified_campaign/study.py',
        ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py']
    for v in range(4,9):files.extend((ROOT/f'tools/unified_control_v{v}').glob('*.py'))
    protocol=dict(cases=cases(),modes=['lqr','adaptive','sequence_teacher'],episodes=192,training_only=True,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in files})
    dump(DATA/'protocol.json',protocol)
    for path in files:
        target=DATA/'source'/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    return protocol


def run(case,mode,steps=120):
    cls=Controller if mode=='sequence_teacher' else Base
    pipe,clock,ego,npcs,net=setup(case,'lqr' if mode=='lqr' else 'deterministic',cls,
        dict(PARAMS,adaptive=mode!='lqr',mpc=mode!='lqr'),grid=mode!='lqr')
    pending=None;rows=[];sequence=0
    for tick in range(steps):
        now=tick*.05;clock.now=now;net.emit(now,ego,npcs,pipe.inbox);accepted=None
        if pending is not None:accepted=pipe.accept_plan(pending,now);pending=None
        decision=pipe.decide(now);label=None;info=None
        if mode=='sequence_teacher':
            label,info=teacher(pipe,now);sequence+=1
            pending=PlanProposal(sequence,pipe.inbox.latest['ego'].observed_s,now,now,label)
        before=ego.copy();previous=pipe.applied;ego=pipe.apply(now,ego,case['stiffness'])
        move_npcs(npcs,.05,pipe.route,case['scenario']);truth=truth_metrics(ego,npcs,pipe.route,pipe.cfg)
        rows.append(dict(tick=tick,time_s=now,state_before=before.tolist(),state_after=ego.tolist(),**truth,**decision,
            npc_truth={k:v.tolist() for k,v in npcs.items()},applied_steering=pipe.applied.steering,applied_accel=pipe.applied.accel,
            steering_rate=(pipe.applied.steering-previous.steering)/.05,label=label,teacher_info=info,accepted=accepted))
        if truth['collision'] or abs(truth['error'])>2.5:break
    result=dict(case=case,mode=mode,ticks=len(rows),expected_ticks=steps,
        failed=len(rows)<steps or any(r['collision'] or r['corridor_exceeded'] for r in rows),
        rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(steps-len(rows))*6.25)/steps),
        heading_rms=float(np.sqrt(np.mean([r['heading_error']**2 for r in rows]))),
        rate_rms=float(np.sqrt(np.mean([r['steering_rate']**2 for r in rows]))),progress_m=float(ego[0]),
        collisions=sum(r['collision'] for r in rows),plan_ticks=sum(r.get('sequence_plan_selected',False) for r in rows))
    return result,rows


def worker(job):
    case,mode=job;record,rows=run(case,mode);path=DATA/f'{case["id"]:03d}-{mode}.jsonl'
    assert not path.exists();path.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
    record.update(raw_sha256=sha(path),protocol_sha256=sha(DATA/'protocol.json'));dump(path.with_suffix('.json'),record);return record


def main():
    protocol=prepare();jobs=[(c,m) for c in protocol['cases'] for m in protocol['modes']];records=[]
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn')) as pool:
        for f in as_completed([pool.submit(worker,j) for j in jobs]):
            records.append(f.result())
            if len(records)%12==0:print('PLAN HEADROOM',len(records),'/192',flush=True)
    records.sort(key=lambda r:(r['case']['id'],r['mode']));dump(DATA/'summary.json',records)
    metrics={mode:{key:float(np.mean([r[key] for r in records if r['mode']==mode])) for key in
        ('rmse_m','heading_rms','rate_rms','progress_m')} for mode in protocol['modes']}
    refs={m:{r['case']['id']:r for r in records if r['mode']==m} for m in protocol['modes']};candidate=refs['sequence_teacher']
    assessment=dict(metrics=metrics,gain_vs_adaptive_percent=100*(1-metrics['sequence_teacher']['rmse_m']/metrics['adaptive']['rmse_m']),
        gain_vs_lqr_percent=100*(1-metrics['sequence_teacher']['rmse_m']/metrics['lqr']['rmse_m']),
        failures={m:sum(r['failed'] for r in records if r['mode']==m) for m in protocol['modes']},
        minimum_lqr_progress_ratio=min(r['progress_m']/refs['lqr'][i]['progress_m'] for i,r in candidate.items()),
        heading_ratio=metrics['sequence_teacher']['heading_rms']/metrics['lqr']['heading_rms'],
        rate_ratio=metrics['sequence_teacher']['rate_rms']/metrics['lqr']['rate_rms'],
        selected_plan_ticks=sum(r['plan_ticks'] for r in candidate.values()),ppo_training_steps=0)
    dump(DATA/'assessment.json',assessment);print(json.dumps(assessment),flush=True)


if __name__=='__main__':main()
