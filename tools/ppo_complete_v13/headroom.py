"""Causal opened-case model optimization; diagnostic teacher, never a PPO claim."""
from pathlib import Path
import argparse,json,math,shutil
import numpy as np
from numba import njit
from scipy.optimize import minimize
from integrations.unified_lans.inference import sha
from integrations.unified_lans.run import clean
from tools.unified_control_v4.kernels import step,lqr,geometry
from .learning import ROOT,DATA,Env,HORIZON
from .plans import anchored_rollout


class SearchBudget(Exception):pass


@njit(cache=True)
def lateral_value(z,commands,accel,previous,dt,n,stiff,gains,route,feedback):
    z=z.copy();energy=0.
    for i in range(n):
        base=lqr(z,gains,int(route[0]),route[1],route[2],route[3],feedback)
        u=commands[i] if i<len(commands) else base
        u=min(.5,max(-.5,min(previous+.6*dt,max(previous-.6*dt,u))))
        z=step(z,u,accel,dt,stiff);y,_,_=geometry(z[0],int(route[0]),route[1],route[2],route[3])
        energy+=(z[1]-y)**2;previous=u
    return math.sqrt(energy/max(1,n))


def predicted_value(c,ctx,action,scale,remaining,objective,score):
    if objective=='mixed':return score.cost
    n=max(0,remaining-round(c.delay/c.cfg.dt))
    if n==0:return 0.
    cfg=c.cfg;npcs=np.asarray([(*s,u) for _,s,u in ctx.vehicles],float).reshape(-1,7);values=[]
    for model in ctx.models:
        _,commands,_=anchored_rollout(np.asarray(ctx.state),np.asarray(action,float),scale,c.correction_amplitude,
            ctx.reference_first,ctx.reference_residual,np.asarray(ctx.reference_plan),ctx.planned,
            ctx.acceleration,ctx.previous.steering,cfg.dt,round(cfg.horizon/cfg.dt),model,c._gains,c._route,npcs,
            cfg.vehicle_radius,cfg.buffer,cfg.uncertainty_rate,cfg.steering_limit,cfg.steering_rate,cfg.residual_limit,c.feedback_stiffness)
        values.append(lateral_value(np.asarray(ctx.state),commands,ctx.acceleration,ctx.previous.steering,cfg.dt,n,model,c._gains,c._route,c.feedback_stiffness))
    return float(np.mean(values))


def teacher(c,ctx,remaining=120,objective='mixed',max_evals=80):
    """SLSQP uses received-state estimates and known route only, with exact guards."""
    if objective not in ('mixed','finite_tracking'):raise ValueError('declared teacher objective required')
    zero=np.zeros(8);neutral=c.score_candidate(ctx,zero)
    diagnostic=dict(objective=objective,max_evals=max_evals,score_evaluations=0,feasible_first_changes=0,
        solver_success=False,solver_status='ineligible',selected=False)
    if not ctx.eligible or remaining<=round(c.delay/c.cfg.dt):return zero,diagnostic
    baseline=predicted_value(c,ctx,zero,0.,remaining,objective,neutral);best_value=baseline;best=zero.copy();cache={};calls=0
    lqr_ref=np.asarray(ctx.lqr_values);anchor_ref=np.asarray(ctx.reference_values)
    caps=[lqr_ref[:,0]-1e-9,1.21*lqr_ref[:,2]+2e-6,1.21*lqr_ref[:,3]+1e-5]
    if c.learned_heading_factor is not None:caps.append(c.learned_heading_factor**2*anchor_ref[:,2]+2e-6)
    if c.learned_rate_factor is not None:caps.append(c.learned_rate_factor**2*anchor_ref[:,3]+1e-5)
    norm=max(abs(baseline),1e-6)
    def evaluate(action):
        nonlocal calls,best,best_value
        a=np.clip(np.asarray(action,float),-1,1);key=a.tobytes()
        if key in cache:return cache[key]
        if calls>=max_evals:raise SearchBudget()
        score=c.score_candidate(ctx,a);calls+=1
        value=predicted_value(c,ctx,a,1.,remaining,objective,score)
        values=np.asarray(score.values);cons=[]
        for k,(candidate,cap) in enumerate(zip((values[:,0],values[:,2],values[:,3]),caps[:3])):
            cons.extend(((cap-candidate)/np.maximum(abs(cap),1e-6)).tolist())
        pos=3
        if c.learned_heading_factor is not None:
            cap=caps[pos];pos+=1;cons.extend(((cap-values[:,2])/np.maximum(abs(cap),1e-6)).tolist())
        if c.learned_rate_factor is not None:
            cap=caps[pos];cons.extend(((cap-values[:,3])/np.maximum(abs(cap),1e-6)).tolist())
        cons.extend((values[:,1]/5).tolist())
        cons.append((neutral.cost-score.cost-1e-8)/max(abs(neutral.cost),1e-6))
        if score.admissible and score.cost<neutral.cost-1e-8 and abs(score.first-ctx.reference_first)>1e-12:
            diagnostic['feasible_first_changes']+=1
            if value<best_value-1e-10:best_value=value;best=a.copy()
        cache[key]=(value,np.asarray(cons),score);return cache[key]
    status='not_started';success=False
    try:
        result=minimize(lambda a:evaluate(a)[0]/norm,zero,method='SLSQP',bounds=[(-1.,1.)]*8,
            constraints=[dict(type='ineq',fun=lambda a:evaluate(a)[1])],
            options=dict(maxiter=8,ftol=1e-9,eps=1e-4,disp=False))
        status=str(result.message);success=bool(result.success)
        # A returned but slightly infeasible numerical point can still have a
        # valid member of the owner's fixed backtracking sequence.
        for scale in c.projection_scales:
            evaluate(np.asarray(result.x)*scale)
    except SearchBudget:status='declared_score_budget_exhausted'
    except (ValueError,FloatingPointError,OverflowError) as exc:status=f'{type(exc).__name__}: {exc}'
    diagnostic.update(score_evaluations=calls,solver_success=success,solver_status=status,
        baseline_model_value=baseline,selected_model_value=best_value,selected=bool(np.any(best)),
        selected_coefficients=best.tolist())
    return best,diagnostic


def jsonable(value):
    if isinstance(value,np.ndarray):return [jsonable(v) for v in value.tolist()]
    if isinstance(value,np.generic):return jsonable(value.item())
    if isinstance(value,dict):return {str(k):jsonable(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [jsonable(v) for v in value]
    return clean(value)


def write(path,value):path.write_text(json.dumps(jsonable(value),indent=2,allow_nan=False)+'\n')


def snapshot(out):
    files=[ROOT/'tools/ppo_complete_v13'/n for n in ('learning.py','plans.py','safety.py','headroom.py','DEVELOPMENT_PROTOCOL.md')]
    files.extend((ROOT/'integrations/unified_lans').glob('*.py'))
    files.extend([ROOT/'tools/unified_control_v9/learning.py',ROOT/'tools/unified_campaign/study.py',ROOT/'tools/ppo_benefit_v10/core.py',
        ROOT/'models/bicycle_model.py',ROOT/'controllers/lqr_controller.py'])
    for version in range(4,9):files.extend((ROOT/f'tools/unified_control_v{version}').glob('*.py'))
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    for p in files:
        dest=out/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    return hashes


def run(out,ids,objective,quality,amplitude,max_evals):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    opened=ROOT/'results/ppo-explore-v12/evaluation/protocol.json';cases=json.loads(opened.read_text())['cases']
    chosen=[cases[i] for i in ids];kwargs=dict(anchor_quality_factor=None if quality=='original' else 1.,correction_amplitude=amplitude)
    protocol=dict(role='opened_case_causal_teacher_headroom_only',cases=chosen,modes=['reference','teacher'],
        objective=objective,quality=quality,controller_kwargs=kwargs,max_evals=max_evals,
        opened_input_sha256=sha(opened),source_hashes=snapshot(out),no_fresh_case_claim=True,
        limitation='Local causal model optimization diagnostic; neither a PPO result nor global upper bound.')
    write(out/'protocol.json',protocol);records=[]
    for case in chosen:
        for mode in ('reference','teacher'):
            env=Env(controller_kwargs=kwargs);obs,_=env.reset(seed=42,options={'case':case});rows=[]
            path=out/f'{case["id"]:03d}-{mode}.jsonl'
            try:
                with path.open('x') as stream:
                    while not env.done:
                        context=env.ctx
                        action,diag=(np.zeros(8),{}) if mode=='reference' else teacher(env.pipe,context,HORIZON-env.tick,objective,max_evals)
                        obs,reward,done,truncated,row=env.step(action)
                        row.update(teacher=diag,context=dict(state=context.state,previous=dict(steering=context.previous.steering,accel=context.previous.accel),
                            models=context.models,reference_values=context.reference_values,lqr_values=context.lqr_values,
                            anchor_features=context.anchor_features,planned=context.planned,eligible=context.eligible))
                        stream.write(json.dumps(jsonable(row),allow_nan=False)+'\n');rows.append(row)
            finally:env.close()
            n=len(rows);record=dict(case=case,mode=mode,ticks=n,expected_ticks=120,
                rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(120-n)*6.25)/120),
                heading_rms=float(np.sqrt(np.mean([r['heading_error']**2 for r in rows]))),rate_rms=float(np.sqrt(np.mean([r['steering_rate']**2 for r in rows]))),
                progress_m=float(rows[-1]['state_after'][0]),failed=n<120 or any(r['collision'] or r['corridor_exceeded'] for r in rows),
                collisions=sum(r['collision'] for r in rows),selected_ticks=sum(r['sequence_plan_selected'] for r in rows),raw_sha256=sha(path),
                teacher_evaluations=sum(r['teacher'].get('score_evaluations',0) for r in rows))
            records.append(record);write(path.with_suffix('.json'),record)
            print('HEADROOM',case['id'],mode,'RMSE',record['rmse_m'],'selected',record['selected_ticks'],'failed',record['failed'],flush=True)
    write(out/'summary.json',records)
    base=[r for r in records if r['mode']=='reference'];test=[r for r in records if r['mode']=='teacher']
    a=np.mean([r['rmse_m'] for r in base]);b=np.mean([r['rmse_m'] for r in test])
    assessment=dict(episodes=len(records),reference_mean_rmse_m=float(a),teacher_mean_rmse_m=float(b),gain_percent=float(100*(1-b/a)),
        failures=sum(r['failed'] for r in test),selected_ticks=sum(r['selected_ticks'] for r in test),
        heading_ratio=float(np.mean([r['heading_rms'] for r in test])/np.mean([r['heading_rms'] for r in base])),
        rate_ratio=float(np.mean([r['rate_rms'] for r in test])/np.mean([r['rate_rms'] for r in base])),
        minimum_progress_ratio=float(min(t['progress_m']/r['progress_m'] for t,r in zip(test,base))),
        scope='Opened development pilot only; mean gain is not a guaranteed optimum or a learned policy result.')
    for name,digest in protocol['source_hashes'].items():assert sha(ROOT/name)==digest,('Development source changed',name)
    write(out/'assessment.json',assessment);print(json.dumps(assessment),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--ids',type=int,nargs='+')
    p.add_argument('--objective',choices=['mixed','finite_tracking'],default='finite_tracking')
    p.add_argument('--quality',choices=['original','anchor'],default='original');p.add_argument('--amplitude',type=float,default=.08)
    p.add_argument('--max-evals',type=int,default=80)
    a=p.parse_args();ids=a.ids if a.ids is not None else [offset+i for offset in (0,18,36,54) for i in (0,8,16)]
    run(a.output,ids,a.objective,a.quality,a.amplitude,a.max_evals)


if __name__=='__main__':main()
