"""Six fixed joint sequential-conic steps per diagnostic mode, no case selection."""
from pathlib import Path
import json,math,shutil,time
import numpy as np
from integrations.unified_lans.inference import sha
from .run import ROOT,inputs,metrics,save_trace,replay,write
from .optimizer import rollout
from .conic import solve_joint,project_commands

SOURCE=ROOT/'results/thirty-percent-headroom'
OUTPUT=ROOT/'results/thirty-percent-conic'


def score(values,references,quality):
    per_case=[metrics(v,120,r) for v,r in zip(values,references)]
    physical=all(not m['collision'] and not m['corridor_failure'] and m['progress_ratio']>=.99-1e-12 for m in per_case)
    heading=sum(m['heading_rms'] for m in per_case)/sum(math.sqrt(r[1]/120) for r in references)
    rate=sum(m['rate_rms'] for m in per_case)/sum(math.sqrt(r[2]/120) for r in references)
    return dict(mean_rmse_m=float(np.mean([m['rmse_m'] for m in per_case])),physical_passed=physical,
        heading_mean_ratio=heading,rate_mean_ratio=rate,
        original_mean_quality_passed=bool(heading<=1.10+1e-12 and rate<=1.10+1e-12),
        feasible=bool(physical and (not quality or (heading<=1.10+1e-12 and rate<=1.10+1e-12))),per_case=per_case)


def prepare(root):
    root.mkdir(exist_ok=False);original=json.loads((SOURCE/'protocol.json').read_text())
    files=[*Path(__file__).parent.glob('*.py'),Path(__file__).parent/'CONIC_PROTOCOL.md',Path(__file__).parent/'requirements.txt',
        *(ROOT/'integrations/unified_lans').glob('*.py'),ROOT/'tools/unified_campaign/study.py',
        ROOT/'tools/unified_control_v4/control.py',ROOT/'tools/unified_control_v4/kernels.py',
        ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py']
    protocol=dict(role='PRIVILEGED_OFFLINE_DIAGNOSTIC_NOT_CONTROLLER_VALIDATION',cases=original['cases'],
        baseline_mean_rmse_m=original['baseline_mean_rmse_m'],target_mean_rmse_m=original['target_mean_rmse_m'],
        modes=['quality_constrained','tracking_focused'],steps=6,line_search=[1.,.5,.25,.125,.0625],
        clarabel_version='0.9.0',clarabel_max_iter=100,tolerances=1e-8,
        input_protocol_sha256=sha(SOURCE/'protocol.json'),
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in files},
        bootstrap=dict(unit='eight scenario/speed clusters',draws=5000,seed=30413001),
        no_reserved_data=True,no_drafts_figures_or_tables=True)
    write(root/'protocol.json',protocol)
    for p in files:
        dest=root/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    return protocol


def main():
    root=OUTPUT;protocol=prepare(root)
    data=[];references=[]
    for record in protocol['cases']:
        _,args,reference=inputs(SOURCE,record);data.append(args);references.append(reference)
    summaries=[];all_results=[]
    for mode in protocol['modes']:
        quality=mode=='quality_constrained';directory=root/mode;directory.mkdir()
        actions=[np.zeros(120) for _ in data];values=[rollout(x,*args)[0] for x,args in zip(actions,data)]
        current=score(values,references,quality);assert current['feasible']
        for iteration in range(6):
            problems=[]
            for x,args,reference in zip(actions,data,references):
                _,states,commands,_=rollout(x,*args)
                problems.append(dict(initial=args[0],accels=args[1],npcs=args[2],stiff=args[3],gains=args[4],route=args[5],
                    states=states,commands=commands,reference=reference,trust=.05*.8**iteration))
            started=time.perf_counter();proposal,info=solve_joint(problems,quality);elapsed=time.perf_counter()-started
            log=dict(iteration=iteration,solver=info,elapsed_s=elapsed,before=current,trials=[],selected_fraction=None)
            selected_actions=None;selected_score=current
            if info['status']=='Solved' and proposal is not None and np.isfinite(proposal).all():
                log['proposed_commands']=proposal.tolist()
                for fraction in protocol['line_search']:
                    candidate=[];candidate_values=[]
                    for p,target,args in zip(problems,proposal,data):
                        commands=p['commands']+fraction*(target-p['commands'])
                        x=project_commands(commands,args[0],args[1],args[3],args[4],args[5])
                        candidate.append(x);candidate_values.append(rollout(x,*args)[0])
                    trial=score(candidate_values,references,quality);log['trials'].append(dict(fraction=fraction,**trial))
                    if trial['feasible'] and trial['mean_rmse_m']<selected_score['mean_rmse_m']-1e-12:
                        selected_actions=candidate;selected_score=trial;log['selected_fraction']=fraction
            if selected_actions is not None:actions=selected_actions;current=selected_score
            log['after']=current;write(directory/f'iteration-{iteration}.json',log)
            print('JOINT CONIC',mode,iteration+1,'/6',info['status'],'mean RMSE',current['mean_rmse_m'],flush=True)
        records=[]
        for case,x,args,reference in zip(protocol['cases'],actions,data,references):
            raw=directory/f'{case["case"]["id"]:03d}.jsonl';rows,value=save_trace(raw,x,args,case)
            np.testing.assert_allclose(replay(rows,case),value,rtol=0,atol=1e-8)
            record=dict(case=case['case'],mode=mode,reference=case,metrics=metrics(value,120,reference),
                actions=x.tolist(),raw_sha256=sha(raw),physical_replay_passed=True,role='PRIVILEGED_OFFLINE_DIAGNOSTIC')
            write(raw.with_suffix('.json'),record);records.append(record)
        cells={}
        for r in records:cells.setdefault((r['case']['scenario'],r['case']['speed']),[]).append([r['reference']['rmse_m'],r['metrics']['rmse_m']])
        pairs=np.array([np.mean(v,axis=0) for v in cells.values()]);rng=np.random.default_rng(30413001)
        draw=rng.integers(8,size=(5000,8));boot=pairs[draw].mean(axis=1);gain=100*(1-current['mean_rmse_m']/protocol['baseline_mean_rmse_m'])
        summary=dict(mode=mode,cases=32,mean_rmse_m=current['mean_rmse_m'],gain_percent=gain,
            ci95_percent=np.quantile(100*(1-boot[:,1]/boot[:,0]),[.025,.975]).tolist(),
            heading_mean_ratio=current['heading_mean_ratio'],rate_mean_ratio=current['rate_mean_ratio'],
            physical_checks_passed=current['physical_passed'],original_mean_quality_passed=current['original_mean_quality_passed'],
            thirty_percent_mean_target_met=bool(gain>=30.),
            role='privileged offline nonlinear-validated witness; not deployed hybrid/PPO or global optimality proof')
        summaries.append(summary);all_results.extend(records);write(directory/'summary.json',summary)
    write(root/'summary.json',summaries);write(root/'all_results.json',all_results)
    print(json.dumps(summaries,indent=2),flush=True)


if __name__=='__main__':main()
