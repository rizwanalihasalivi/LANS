"""Frozen prospective whole-run comparisons against all seven declared references."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict,replace
from pathlib import Path
import argparse,json,multiprocessing as mp,shutil
import numpy as np
from integrations.unified_lans.physics import Config
from integrations.unified_lans.inference import sha,load_policy
from integrations.unified_lans.run import clean
from tools.unified_campaign import study
from tools.unified_campaign.campaign import assess
from tools.unified_control_v4 import campaign as audit_tools
from tools.unified_control_v6.control import Controller as Legacy
from .control import Controller

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'results/causal-v8/confirmation'
MODES=['lqr','fixed','deterministic','optimized','adaptive','ppo','hybrid','legacy_hybrid']
REFERENCES=[mode for mode in MODES if mode!='hybrid']
SEEDS=[42,43,44]
BOOTSTRAP_SEED=82413001
STAGES=['regression-development','regression-stress','development','stress']
_models=None


def choice():
    selected=json.loads((ROOT/'results/causal-v8/calibration/selection.json').read_text())['selected']
    assert selected is not None,'No fixed training candidate passed the quality/progress selector'
    return selected


def make_controller(*args,adaptive=False,mpc=False,selection=None,**kwargs):
    selected=choice() if selection is None else selection;args=list(args)
    if kwargs.pop('penalty',16.)!=16.:raise ValueError('all comparisons require calibrated shared R=16')
    if len(args)>2:args[2]=replace(args[2],horizon=selected['horizon'])
    elif kwargs.get('cfg') is not None:kwargs['cfg']=replace(kwargs['cfg'],horizon=selected['horizon'])
    cls=Legacy if selected['factor'] is None else Controller
    if selected['factor'] is not None:
        kwargs.update(quality_factor=selected['factor'],early_id=selected['early_id'],tracking_only=selected['tracking_only'])
    return cls(*args,penalty=16.,adaptive=adaptive,mpc=mpc,**kwargs)


def cases(stage):
    if stage.startswith('regression'):return audit_tools.cases(stage)
    if stage=='stress':
        result=[]
        for s in range(4):
            for j,profile in enumerate(['delayed','loss','reordered','blackout','ego_blackout','command_delay']):
                c=study.make_case('development',s*8)
                c.update(id=s*6+j,stage='v8_stress',speed=12.,phase=18.,amplitude=1.2,
                    lateral=.3*c['mirror'],heading=.005*c['mirror'],stiffness=.8,
                    network='nominal' if profile=='command_delay' else profile,
                    delay=.1 if profile=='command_delay' else 0.,network_seed=83413000+s*6+j)
                result.append(c)
        return result
    assert stage in ('development','reserved')
    reserved=stage=='reserved';rng=np.random.default_rng(96413000 if reserved else 82413000);result=[]
    for i in range(32):
        c=study.make_case('reserved' if reserved else 'development',i)
        c.update(stage='v8_'+stage,lateral=float(rng.uniform(.15,.45))*c['mirror'],heading=float(rng.uniform(-.015,.015)),
            phase=28. if reserved else 18.,amplitude=1.3 if reserved else 1.2,
            network_seed=(97413000 if reserved else 84413000)+i)
        result.append(c)
    return result


def write(path,value):
    path=Path(path);temporary=path.with_suffix('.pending')
    temporary.write_text(json.dumps(clean(value),indent=2,allow_nan=False)+'\n');temporary.replace(path)


def source_files():
    files=[*Path(__file__).parent.glob('*.py'),Path(__file__).parent/'PROTOCOL.md',
        *(ROOT/'integrations/unified_lans').glob('*.py'),ROOT/'tools/unified_campaign/study.py',
        ROOT/'tools/unified_campaign/campaign.py',ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py']
    for version in range(4,8):files.extend((ROOT/f'tools/unified_control_v{version}').glob('*.py'))
    return sorted(set(files))


def prepare(root):
    root.mkdir(parents=True,exist_ok=False);selected=choice();files=source_files()
    protocol=dict(version=8,selected=selected,config=asdict(Config(horizon=selected['horizon'])),
        calibration_sha256=sha(ROOT/'results/causal-v8/calibration/selection.json'),modes=MODES,seeds=SEEDS,seconds=6.,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in files},
        models={s:sha(ROOT/f'results/python-campaign-v2/policies/seed-{s}/policy.zip') for s in SEEDS},
        original_gate=audit_tools.OLD_PROTOCOL['gate'],requested_gain_percent=30.,required_references=REFERENCES,
        new_training_steps=0,total_prospective_episodes=848,
        development=dict(namespace=82413000,phase=18.,amplitude=1.2),reserved=dict(namespace=96413000,phase=28.,amplitude=1.3),
        bootstrap=dict(seed=BOOTSTRAP_SEED,draws=5000,clusters='scenario-speed; actor/mirror/stiffness averaged within cluster'),
        primary_metric='whole six-second failure-penalized mean episode RMSE',
        legacy_reference='unchanged v6 adaptive+mpc, original three policies, corrected shared traffic supervisor',
        shared_supervisor_fix='conflict-time uses the maximum of axis interval starts; applies to every comparator',
        all_endpoints_no_seed_selection=True,secondary_phase_cannot_replace_primary=True)
    write(root/'protocol.json',protocol)
    for path in files:
        target=root/'source'/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    return protocol


def check(root):
    protocol=json.loads((root/'protocol.json').read_text())
    for name,h in protocol['source_hashes'].items():assert sha(ROOT/name)==h,('source changed',name)
    for seed,h in protocol['models'].items():assert sha(ROOT/f'results/python-campaign-v2/policies/seed-{seed}/policy.zip')==h
    assert sha(ROOT/'results/causal-v8/calibration/selection.json')==protocol['calibration_sha256']
    return protocol


def initialize():
    import torch
    global _models
    torch.set_num_threads(1);_models={s:load_policy(ROOT/f'results/python-campaign-v2/policies/seed-{s}') for s in SEEDS}


def worker(job):
    root,stage,case,mode,actor=job;root=Path(root);key=f'{case["id"]:03d}-{mode}-{actor}'
    raw=root/stage/(key+'.jsonl');meta=root/stage/(key+'.json')
    if meta.exists():
        record=json.loads(meta.read_text())
        assert record['case']==case and record['mode']==mode and record['actor']==actor
        assert sha(raw)==record['raw_sha256'] and record['protocol_sha256']==sha(root/'protocol.json')
        return stage,record
    assert not raw.exists(),('Preserve interrupted evidence',raw)
    selected=json.loads((root/'protocol.json').read_text())['selected']
    if mode=='legacy_hybrid':selected=dict(name='legacy-v6-reference',horizon=2.,factor=None,early_id=False,tracking_only=False)
    adaptive=mode in ('adaptive','hybrid','legacy_hybrid');mpc=mode in ('optimized','adaptive','hybrid','legacy_hybrid')
    def factory(*args,**kwargs):return make_controller(*args,selection=selected,adaptive=adaptive,mpc=mpc,**kwargs)
    study.Pipeline=factory
    study_mode='hybrid' if mode=='legacy_hybrid' else ('deterministic' if mode in ('optimized','adaptive') else mode)
    record,rows=study.run_episode(case,study_mode,_models.get(actor),grid=mpc,seconds=6.)
    record['mode']=mode
    raw.write_text(''.join(json.dumps(clean(row),allow_nan=False)+'\n' for row in rows))
    record.update(actor=actor,raw_sha256=sha(raw),protocol_sha256=sha(root/'protocol.json'));write(meta,record)
    return stage,record


def all_comparisons(records):
    ids=sorted({r['case']['id'] for r in records});assert len(ids)==32
    lookup={(r['case']['id'],r['mode'],r['actor']):r for r in records}
    assert len(lookup)==448
    metrics={}
    for mode in MODES:
        rr=[r for r in records if r['mode']==mode]
        metrics[mode]=dict(episodes=len(rr),mean_rmse_m=float(np.mean([r['rmse_m'] for r in rr])),
            mean_heading_rms=float(np.mean([r['heading_rms'] for r in rr])),
            mean_rate_rms=float(np.mean([r['rate_rms'] for r in rr])),
            mean_progress_m=float(np.mean([r['progress_m'] for r in rr])),
            minimum_clearance_m=float(min(r['min_clearance'] for r in rr)),
            failures=sum(r['failed'] for r in rr),collision_episodes=sum(r['collisions']>0 for r in rr))
    comparisons={}
    for mode in REFERENCES:
        clusters={};progress=[]
        for i in ids:
            actors=SEEDS if mode in ('ppo','legacy_hybrid') else [0]
            references=[lookup[(i,mode,seed)] for seed in actors]
            hybrid=[lookup[(i,'hybrid',seed)] for seed in SEEDS]
            baseline=float(np.mean([r['rmse_m'] for r in references]));value=float(np.mean([r['rmse_m'] for r in hybrid]))
            case=references[0]['case'];clusters.setdefault((case['scenario'],case['speed']),[]).append([baseline,value])
            progress.extend(r['progress_m']/float(np.mean([b['progress_m'] for b in references])) for r in hybrid)
        pairs=np.array([np.mean(v,axis=0) for v in clusters.values()]);assert len(pairs)==8
        draw=np.random.default_rng(BOOTSTRAP_SEED).integers(len(pairs),size=(5000,len(pairs)));boot=pairs[draw].mean(axis=1)
        interval=np.quantile(100*(1-boot[:,1]/boot[:,0]),[.025,.975]);means=pairs.mean(axis=0)
        comparisons[mode]=dict(reference_mean_rmse_m=float(means[0]),hybrid_mean_rmse_m=float(means[1]),
            gain_percent=float(100*(1-means[1]/means[0])),ci95_percent=interval.tolist(),clusters=8,
            mean_heading_ratio=metrics['hybrid']['mean_heading_rms']/metrics[mode]['mean_heading_rms'],
            mean_rate_ratio=metrics['hybrid']['mean_rate_rms']/metrics[mode]['mean_rate_rms'],
            minimum_cell_actor_progress_ratio=float(min(progress)),
            mean_gain_at_least_30=bool(100*(1-means[1]/means[0])>=30.),lower_ci_at_least_30=bool(interval[0]>=30.))
    return dict(comparisons=comparisons,metrics=metrics,bootstrap_seed=BOOTSTRAP_SEED,
        scope='All seven references; whole episodes; correlated finite grid; point estimates and confidence claims distinguished.')


def requested_target(gate,comparisons,safety):
    all_means=all(c['mean_gain_at_least_30'] for c in comparisons['comparisons'].values())
    all_ci=all(c['lower_ci_at_least_30'] for c in comparisons['comparisons'].values())
    return dict(passed=bool(gate['passed'] and safety and all_means),target_percent=30.,
        original_gate_passed=gate['passed'],regression_and_stress_safety_passed=safety,
        all_reference_mean_gains_at_least_30=all_means,
        all_reference_lower_ci_at_least_30=all_ci,required_references=REFERENCES,
        note='Mean threshold achievement is not a claim that confidence bounds also exceed 30%.')


def evaluate(root,stages):
    jobs=[];results={stage:[] for stage in stages}
    for stage in stages:
        (root/stage).mkdir(exist_ok=True)
        modes=MODES if stage in ('development','reserved') else ['lqr','optimized','hybrid']
        for case in cases(stage):
            for mode in modes:
                for actor in SEEDS if mode in ('ppo','hybrid','legacy_hybrid') else [0]:jobs.append((str(root),stage,case,mode,actor))
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn'),initializer=initialize) as pool:
        for done,future in enumerate(as_completed([pool.submit(worker,job) for job in jobs]),1):
            stage,record=future.result();results[stage].append(record)
            if done%32==0 or done==len(jobs):print('V8 PROSPECTIVE',done,'/',len(jobs),flush=True)
    for stage,records in results.items():
        records.sort(key=lambda r:(r['case']['id'],r['mode'],r['actor']))
        write(root/f'{stage}_summary.json',records);audit_tools.audit(root,stage,records);audit_tools.summary(root,stage,records)
        if stage in ('development','reserved'):write(root/f'{stage}_all_comparisons.json',all_comparisons(records))
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',default=str(OUTPUT));args=parser.parse_args();root=Path(args.output)
    if not root.exists():prepare(root)
    check(root);evaluate(root,STAGES)
    gate=json.loads((root/'development_gate.json').read_text())
    comparisons=json.loads((root/'development_all_comparisons.json').read_text())
    safe=all(json.loads((root/f'{stage}_safety.json').read_text())['passed'] for stage in STAGES)
    target=requested_target(gate,comparisons,safe);write(root/'requested_target.json',target)
    if target['passed']:evaluate(root,['reserved'])
    write(root/'STATUS.json',dict(original_development_gate_passed=gate['passed'],requested_30_percent_passed=target['passed'],
        reserved='completed' if target['passed'] else 'NOT_RUN',formal_wall_worker='NOT_RUN',webots='NOT_RUN'))
    print('REQUESTED TARGET',json.dumps(target),flush=True)


if __name__=='__main__':main()
