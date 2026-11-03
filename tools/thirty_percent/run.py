"""Seal and run 64 fixed offline shooting solves on observed development cases."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import argparse,json,math,multiprocessing as mp,shutil,time
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.physics import Command,advance,errors
from tools.unified_campaign.study import StudyRoute,initial
from tools.unified_control_v4.control import gain_table
from .optimizer import rollout,solve

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'results/thirty-percent-headroom'
SOURCE=ROOT/'results/proposal-completion-v6/confirmation'


def write(path,value):
    from integrations.unified_lans.run import clean
    path=Path(path);temp=path.with_suffix('.pending')
    temp.write_text(json.dumps(clean(value),indent=2,allow_nan=False)+'\n');temp.replace(path)


def prepare(root):
    baseline=[r for r in json.loads((SOURCE/'development_summary.json').read_text()) if r['mode']=='lqr']
    assert len(baseline)==32 and sorted(r['case']['id'] for r in baseline)==list(range(32))
    root.mkdir(parents=True,exist_ok=False);(root/'input').mkdir()
    for r in baseline:
        assert r['case']['delay']==0. and not r['failed'] and r['expected_ticks']==120
        name=f'{r["case"]["id"]:03d}-lqr-0.jsonl';path=SOURCE/'development'/name
        assert sha(path)==r['raw_sha256'];shutil.copyfile(path,root/'input'/name)
    files=[*Path(__file__).parent.glob('*.py'),Path(__file__).parent/'PROTOCOL.md',
        *(ROOT/'integrations/unified_lans').glob('*.py'),ROOT/'tools/unified_campaign/study.py',
        ROOT/'tools/unified_control_v4/control.py',ROOT/'tools/unified_control_v4/kernels.py',
        ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py']
    average=float(np.mean([r['rmse_m'] for r in baseline]))
    protocol=dict(version=1,role='PRIVILEGED_OFFLINE_DIAGNOSTIC_NOT_CONTROLLER_VALIDATION',
        requested_mean_rmse_gain_percent=30.,baseline_mean_rmse_m=average,target_mean_rmse_m=.7*average,
        cases=baseline,modes=['quality_constrained','tracking_focused'],workers=4,
        solver=dict(method='SLSQP',initialization='one zero residual',maxiter=120,ftol=1e-10,finite_difference_step=1e-5),
        baseline_source_protocol_sha256=sha(SOURCE/'protocol.json'),
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in files},
        bootstrap=dict(clusters='eight scenario/speed cells',draws=5000,seed=30413001),
        no_reserved_data=True,no_new_learning=True,no_drafts_figures_or_tables=True)
    write(root/'protocol.json',protocol)
    for p in files:
        dest=root/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    return protocol


def inputs(root,record):
    case=record['case'];raw=root/'input'/f'{case["id"]:03d}-lqr-0.jsonl';assert sha(raw)==record['raw_sha256']
    rows=[json.loads(line) for line in raw.read_text().splitlines()]
    state=np.array(rows[0]['state_before']);accel=np.array([r['applied_accel'] for r in rows])
    npcs=np.array([[r['npc_truth'][name] for name in sorted(r['npc_truth'])] for r in rows])
    kind=initial(case['scenario'])[0].kind
    route=np.array([{'straight':0,'sine':1,'lane_change':2}[kind],case['mirror'],case['phase'],case['amplitude']])
    reference=np.array([record['rmse_m']**2*len(rows),record['heading_rms']**2*len(rows),
        record['rate_rms']**2*len(rows),record['progress_m'],min(1.75-abs(r['error']) for r in rows),record['min_clearance']])
    return rows,(state,accel,npcs,case['stiffness'],gain_table(16.,1.),route),reference


def metrics(values,n,reference):
    sse,heading,slew,progress,corridor,clearance=map(float,values)
    return dict(rmse_m=math.sqrt(sse/n),heading_rms=math.sqrt(heading/n),rate_rms=math.sqrt(slew/n),
        heading_ratio=math.sqrt(heading/reference[1]),rate_ratio=math.sqrt(slew/reference[2]),
        progress_m=progress,progress_ratio=progress/reference[3],corridor_margin_m=corridor,
        minimum_clearance_m=clearance,collision=clearance<=0.,corridor_failure=corridor<0.)


def feasible(m,quality):
    physical=not m['collision'] and not m['corridor_failure'] and m['progress_ratio']>=.99-1e-12
    return physical and (not quality or (m['heading_ratio']<=1.10+1e-12 and m['rate_ratio']<=1.10+1e-12))


def save_trace(path,actions,args,record):
    from integrations.unified_lans.run import clean
    values,states,steers,bases=rollout(actions,*args);state=args[0].copy();rows=[]
    for i in range(len(actions)):
        rows.append(dict(tick=i,time_s=i*.05,state_before=state.tolist(),state_after=states[i].tolist(),
            requested_residual_rad=.08*float(actions[i]),baseline_steering=float(bases[i]),
            steering=float(steers[i]),acceleration=float(args[1][i]),
            npc_truth=args[2][i].tolist()))
        state=states[i]
    path.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
    return rows,values


def replay(rows,record):
    case=record['case'];route=StudyRoute(initial(case['scenario'])[0].kind,case['mirror'],case['phase'],case['amplitude'])
    state=np.array(rows[0]['state_before']);previous=0.;sse=0.;heading=0.;slew=0.;minimum=math.inf;corridor=math.inf
    for i,row in enumerate(rows):
        assert i==row['tick'] and row['time_s']==i*.05
        np.testing.assert_allclose(state,row['state_before'],rtol=0,atol=1e-10)
        u=row['steering'];a=row['acceleration']
        assert abs(u)<=.5+1e-12 and abs(u-previous)<=.03+1e-12 and -6<=a<=2.5
        assert abs(row['requested_residual_rad'])<=.08+1e-12
        expected=min(.5,max(-.5,min(previous+.03,max(previous-.03,row['baseline_steering']+row['requested_residual_rad']))))
        assert expected==u
        state=advance(state,Command(u,a),.05,case['stiffness'])
        np.testing.assert_allclose(state,row['state_after'],rtol=0,atol=1e-10)
        error,_=errors(state,route);sse+=error[0]**2;heading+=error[2]**2;slew+=((u-previous)/.05)**2
        corridor=min(corridor,1.75-abs(error[0]))
        for other in row['npc_truth']:minimum=min(minimum,float(np.linalg.norm(state[:2]-np.asarray(other)[:2])-4.6))
        previous=u
    return np.array([sse,heading,slew,state[0],corridor,minimum])


def worker(job):
    root,record,mode=job;root=Path(root);dest=root/f'{record["case"]["id"]:03d}-{mode}';meta=dest/'result.json'
    if meta.exists():
        result=json.loads(meta.read_text())
        assert sha(dest/'candidate.jsonl')==result['candidate_raw_sha256'] and sha(dest/'accepted.jsonl')==result['accepted_raw_sha256']
        return result
    dest.mkdir(exist_ok=False);before,args,reference=inputs(root,record);quality=mode=='quality_constrained'
    zero=np.zeros(len(before));baseline_values,baseline_states,baseline_steers,_=rollout(zero,*args)
    np.testing.assert_allclose(baseline_states,[r['state_after'] for r in before],rtol=0,atol=1e-8)
    np.testing.assert_allclose(baseline_steers,[r['applied_steering'] for r in before],rtol=0,atol=1e-8)
    np.testing.assert_allclose(baseline_values,reference,rtol=0,atol=1e-8)
    start=time.perf_counter();solution,objective=solve(*args,reference,quality);elapsed=time.perf_counter()-start
    candidate=np.asarray(solution.x);finite=bool(np.isfinite(candidate).all())
    assert finite,'Preserve nonfinite optimizer failure for diagnosis'
    proposed_rows,proposed_values=save_trace(dest/'candidate.jsonl',candidate,args,record)
    np.testing.assert_allclose(replay(proposed_rows,record),proposed_values,rtol=0,atol=1e-8)
    proposed_metrics=metrics(proposed_values,len(before),reference)
    accepted=bool(solution.success) and feasible(proposed_metrics,quality)
    applied=candidate if accepted else zero
    accepted_rows,accepted_values=save_trace(dest/'accepted.jsonl',applied,args,record)
    np.testing.assert_allclose(replay(accepted_rows,record),accepted_values,rtol=0,atol=1e-8)
    result=dict(case=record['case'],mode=mode,reference=record,
        solver=dict(success=bool(solution.success),status=int(solution.status),message=str(solution.message),iterations=int(solution.nit),
                    evaluations=objective.evaluations,elapsed_s=elapsed),
        candidate_feasible=feasible(proposed_metrics,quality),accepted=accepted,
        fallback_reason='' if accepted else ('optimizer_unsuccessful' if not solution.success else 'actual_constraints_violated'),
        candidate_metrics=proposed_metrics,metrics=metrics(accepted_values,len(before),reference),
        candidate_actions=candidate.tolist(),accepted_actions=applied.tolist(),
        candidate_raw_sha256=sha(dest/'candidate.jsonl'),accepted_raw_sha256=sha(dest/'accepted.jsonl'),
        physical_replay_passed=True,role='PRIVILEGED_OFFLINE_DIAGNOSTIC')
    write(meta,result);return result


def summarize(root,records,protocol):
    output=[]
    for mode in protocol['modes']:
        rr=sorted([r for r in records if r['mode']==mode],key=lambda r:r['case']['id'])
        assert len(rr)==32 and [r['case']['id'] for r in rr]==list(range(32))
        cells={}
        for r in rr:cells.setdefault((r['case']['scenario'],r['case']['speed']),[]).append([r['reference']['rmse_m'],r['metrics']['rmse_m']])
        pairs=np.array([np.mean(v,axis=0) for v in cells.values()]);assert len(pairs)==8
        rng=np.random.default_rng(30413001);draw=rng.integers(8,size=(5000,8));boot=pairs[draw].mean(axis=1)
        gain=100*(1-pairs[:,1].mean()/pairs[:,0].mean());interval=np.quantile(100*(1-boot[:,1]/boot[:,0]),[.025,.975])
        heading=np.mean([r['metrics']['heading_rms'] for r in rr])/np.mean([r['reference']['heading_rms'] for r in rr])
        rate=np.mean([r['metrics']['rate_rms'] for r in rr])/np.mean([r['reference']['rate_rms'] for r in rr])
        physical=all(feasible(r['metrics'],False) for r in rr)
        output.append(dict(mode=mode,cases=32,accepted_solves=sum(r['accepted'] for r in rr),
            mean_rmse_m=float(np.mean([r['metrics']['rmse_m'] for r in rr])),gain_percent=float(gain),ci95_percent=interval.tolist(),
            heading_mean_ratio=float(heading),rate_mean_ratio=float(rate),physical_checks_passed=physical,
            original_mean_quality_passed=bool(heading<=1.10+1e-12 and rate<=1.10+1e-12),
            thirty_percent_mean_target_met=bool(gain>=30.),
            candidate_mean_rmse_m=float(np.mean([r['candidate_metrics']['rmse_m'] for r in rr])),
            nonconverged_candidates=sum(not r['solver']['success'] for r in rr),
            conclusion_scope='approximate privileged offline feasible plans; neither a global optimum nor deployed hybrid evidence'))
    write(root/'summary.json',output);write(root/'all_results.json',records)
    print(json.dumps(output,indent=2),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',default=str(OUTPUT));args=parser.parse_args();root=Path(args.output)
    protocol=prepare(root) if not root.exists() else json.loads((root/'protocol.json').read_text())
    for name,h in protocol['source_hashes'].items():assert sha(ROOT/name)==h,('source changed',name)
    jobs=[(str(root),r,mode) for mode in protocol['modes'] for r in protocol['cases']]
    # Compile canonical-module kernels once before multiprocessing; no hidden
    # optimization or case selection occurs during warmup.
    _,warm,reference=inputs(root,protocol['cases'][0]);rollout(np.zeros(120),*warm)
    records=[]
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn')) as pool:
        for future in as_completed([pool.submit(worker,j) for j in jobs]):
            result=future.result();records.append(result)
            print('HEADROOM',len(records),'/',len(jobs),result['mode'],result['case']['id'],'accepted',result['accepted'],flush=True)
    summarize(root,records,protocol)


if __name__=='__main__':main()
