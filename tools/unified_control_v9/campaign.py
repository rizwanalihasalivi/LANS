"""Frozen development and once-only independent final validation."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import json,shutil,multiprocessing as mp
import numpy as np
from integrations.unified_lans.inference import sha,load_policy
from integrations.unified_lans.run import clean
from tools.unified_campaign.study import make_case
from tools.unified_control_v4 import campaign as audit_tools
from tools.unified_control_v8.control import Controller as Legacy
from .control import Controller
from .baselines import Controller as Geometric
from .learning import run_episode
from .train import selected_kwargs

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/publication-v9/confirmation'
MODES=['lqr','fixed','deterministic','optimized','adaptive','legacy_optimized','legacy_adaptive','stanley','pure_pursuit','ppo','frozen_hybrid','hybrid','legacy_hybrid']
ACTOR_MODES=('ppo','frozen_hybrid','hybrid','legacy_hybrid')
SEEDS=(42,43,44)
_models=None


def cases(stage):
    if stage.startswith('regression'):return audit_tools.cases(stage)
    if stage=='stress':
        from tools.unified_control_v8.campaign import cases as prior_cases
        result=prior_cases('stress')
        for c in result:c.update(stage='v9_stress',phase=20.,amplitude=1.25,network_seed=14913000+c['id'])
        return result
    assert stage in ('development','final')
    rng=np.random.default_rng(11913000 if stage=='development' else 12913000);result=[]
    for i in range(32 if stage=='development' else 64):
        if stage=='development':
            c=make_case('development',i)
            c.update(phase=20.,amplitude=1.25,cluster_network='nominal',npc_x_shift=float(rng.uniform(-3.,3.)),npc_speed_scale=float(rng.uniform(.85,1.15)))
        else:
            scenario=i//16;speed_stratum=(i//8)%2;network_stratum=(i//4)%2;rep=i%4
            c=make_case('development',scenario*8)
            profile=['delayed','loss','reordered','blackout','ego_blackout','command_delay'][(rep+scenario)%6] if network_stratum else 'nominal'
            c.update(mirror=int(rng.choice([-1,1])),speed=float(rng.uniform(12. if speed_stratum else 8.,16. if speed_stratum else 12.)),
                stiffness=float(rng.uniform(.75,1.25)),phase=float(rng.uniform(-8.,28.)),amplitude=float(rng.uniform(.9,1.3)),
                network='nominal' if profile=='command_delay' else profile,delay=.1 if profile=='command_delay' else 0.,
                cluster_network='impaired' if network_stratum else 'nominal',npc_x_shift=float(rng.uniform(-5.,5.)),npc_speed_scale=float(rng.uniform(.75,1.25)))
        c.update(id=i,stage='v9_'+stage,lateral=float(rng.uniform(.15,.45))*c['mirror'],heading=float(rng.uniform(-.02,.02)),network_seed=int(rng.integers(1_000_000_000,2_000_000_000)))
        result.append(c)
    return result


def write(path,value):path.write_text(json.dumps(clean(value),indent=2,allow_nan=False)+'\n')


def prepare():
    OUT.mkdir(parents=True,exist_ok=False)
    # Freeze every computation dependency. Independent verifier and native/live
    # adapters can be completed separately without changing this experiment.
    names=['__init__.py','campaign.py','control.py','runtime.py','learning.py','train.py','baselines.py',
        'PROTOCOL.md','EVALUATION_PROTOCOL.md','BASELINE_PROVENANCE.md']
    files=[*(Path(__file__).parent/name for name in names),*(ROOT/'integrations/unified_lans').glob('*.py'),ROOT/'tools/unified_campaign/study.py',ROOT/'tools/unified_campaign/campaign.py',ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py']
    for v in range(4,9):files.extend((ROOT/f'tools/unified_control_v{v}').glob('*.py'))
    p=dict(selected=selected_kwargs(),selection_sha256=sha(ROOT/'results/publication-v9/calibration/selection.json'),
        geometric=json.loads((ROOT/'results/publication-v9/baseline-calibration/selection.json').read_text())['selected'],
        models={f'{family}-{seed}':sha(ROOT/f'results/{directory}/seed-{seed}/policy.zip') for family,directory in [('old','python-campaign-v2/policies'),('new','publication-v9/policies')] for seed in SEEDS},
        cases={stage:cases(stage) for stage in ['regression-development','regression-stress','development','stress','final']},
        total_episodes=2416,source_hashes={str(p.relative_to(ROOT)):sha(p) for p in files},
        modes=MODES,seeds=SEEDS,seconds=6.,bootstrap_seed=13913000,final_once_no_tuning=True)
    write(OUT/'protocol.json',p)
    for path in files:
        dest=OUT/'source'/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    return p


def initialize():
    import torch
    global _models
    torch.set_num_threads(1)
    _models={(family,s):load_policy(ROOT/f'results/{directory}/seed-{s}') for family,directory in [('old','python-campaign-v2/policies'),('new','publication-v9/policies')] for s in SEEDS}


def worker(job):
    stage,case,mode,actor=job;p=json.loads((OUT/'protocol.json').read_text());key=f'{case["id"]:03d}-{mode}-{actor}'
    raw=OUT/stage/(key+'.jsonl');meta=raw.with_suffix('.json')
    if meta.exists():
        r=json.loads(meta.read_text());assert r['case']==case and r['protocol_sha256']==sha(OUT/'protocol.json') and r['raw_sha256']==sha(raw)
        return stage,r
    assert not raw.exists(),('Preserve interrupted trace',raw)
    kwargs=dict(p['selected'],adaptive=mode in ('adaptive','hybrid','frozen_hybrid'),mpc=mode in ('optimized','adaptive','hybrid','frozen_hybrid'))
    cls=Controller
    if mode in ('legacy_optimized','legacy_adaptive','legacy_hybrid'):
        cls=Legacy;kwargs=dict(adaptive=mode!='legacy_optimized',mpc=True,quality_factor=1.1,early_id=True,tracking_only=False)
    if mode in ('stanley','pure_pursuit'):
        def cls(*args,**kw):
            for k in ('early_id','tracking_only'):kw.pop(k,None)
            return Geometric(*args,method=mode,parameter=p['geometric'][mode]['parameter'],**kw)
        kwargs=dict(adaptive=False,mpc=False)
    label='hybrid' if mode in ('hybrid','frozen_hybrid','legacy_hybrid') else ('deterministic' if mode in ('optimized','adaptive','legacy_optimized','legacy_adaptive') else ('lqr' if mode in ('stanley','pure_pursuit') else mode))
    model=_models.get(('old' if mode in ('frozen_hybrid','legacy_hybrid') else 'new',actor))
    r,rows=run_episode(case,label,model,grid=kwargs.get('mpc',False),seconds=6.,controller_factory=cls,controller_kwargs=kwargs)
    raw.write_text(''.join(json.dumps(clean(row),allow_nan=False)+'\n' for row in rows))
    r.update(mode=mode,actor=actor,raw_sha256=sha(raw),protocol_sha256=sha(OUT/'protocol.json'));write(meta,r);return stage,r


def assess(records):
    ids=sorted({r['case']['id'] for r in records});lookup={(r['case']['id'],r['mode'],r['actor']):r for r in records}
    assert len(lookup)==21*len(ids)
    metrics={mode:{name:float(np.mean([r[field] for r in records if r['mode']==mode])) for name,field in [('rmse_m','rmse_m'),('heading_rms','heading_rms'),('rate_rms','rate_rms'),('progress_m','progress_m')]} for mode in MODES}
    comparisons={}
    for mode in [m for m in MODES if m!='hybrid']:
        clusters={};progress=[]
        for i in ids:
            refs=[lookup[(i,mode,s)] for s in (SEEDS if mode in ACTOR_MODES else [0])];hybrid=[lookup[(i,'hybrid',s)] for s in SEEDS];c=refs[0]['case']
            key=(c['scenario'],int(c['speed']>=12),c['cluster_network'])
            clusters.setdefault(key,[]).append([np.mean([r['rmse_m'] for r in refs]),np.mean([r['rmse_m'] for r in hybrid])])
            progress.extend(r['progress_m']/np.mean([b['progress_m'] for b in refs]) for r in hybrid)
        pairs=np.array([np.mean(v,axis=0) for v in clusters.values()]);means=pairs.mean(axis=0)
        draw=np.random.default_rng(13913000).integers(len(pairs),size=(5000,len(pairs)));boot=pairs[draw].mean(axis=1)
        comparisons[mode]=dict(gain_percent=float(100*(1-means[1]/means[0])),ci95_percent=np.quantile(100*(1-boot[:,1]/boot[:,0]),[.025,.975]).tolist(),clusters=len(pairs),
            heading_ratio=metrics['hybrid']['heading_rms']/metrics[mode]['heading_rms'],rate_ratio=metrics['hybrid']['rate_rms']/metrics[mode]['rate_rms'],minimum_progress_ratio=float(min(progress)))
    reasons=[]
    for ref,target in [('lqr',5.),('optimized',1.)]:
        if comparisons[ref]['gain_percent']<target:reasons.append('mean_gain_'+ref)
        if comparisons[ref]['ci95_percent'][0]<=0:reasons.append('confidence_'+ref)
    for actor in SEEDS:
        rr=[lookup[(i,'hybrid',actor)] for i in ids];base=[lookup[(i,'lqr',0)] for i in ids]
        if np.mean([r['rmse_m'] for r in rr])>=np.mean([r['rmse_m'] for r in base]):reasons.append(f'actor_{actor}_no_gain')
        for metric in ('heading_rms','rate_rms'):
            if np.mean([r[metric] for r in rr])>1.1*np.mean([r[metric] for r in base])+1e-12:reasons.append(f'actor_{actor}_{metric}')
        if any(r['failed'] for r in rr):reasons.append(f'actor_{actor}_failure')
        if any(r['progress_m']<.99*b['progress_m'] for r,b in zip(rr,base)):reasons.append(f'actor_{actor}_progress')
    return dict(metrics=metrics,comparisons=comparisons,original_gate_passed=not reasons,reasons=reasons,
        no_quality_regression=all(comparisons['lqr'][key]<=1.+1e-12 for key in ['heading_ratio','rate_ratio']),
        requested_30_all_references=not reasons and all(c['gain_percent']>=30 for c in comparisons.values()),
        ci_lower_30_all_references=not reasons and all(c['ci95_percent'][0]>=30 for c in comparisons.values()),
        failures={m:sum(r['failed'] for r in records if r['mode']==m) for m in MODES})


def main():
    p=prepare() if not OUT.exists() else json.loads((OUT/'protocol.json').read_text())
    for name,h in p['source_hashes'].items():assert sha(ROOT/name)==h,('source changed',name)
    jobs=[];results={stage:[] for stage in p['cases']}
    for stage,fixtures in p['cases'].items():
        (OUT/stage).mkdir(exist_ok=True)
        for case in fixtures:
            for mode in MODES if stage in ('development','final') else ['lqr','optimized','hybrid']:
                for actor in SEEDS if mode in ACTOR_MODES else [0]:jobs.append((stage,case,mode,actor))
    assert len(jobs)==2416
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn'),initializer=initialize) as pool:
        for i,f in enumerate(as_completed([pool.submit(worker,j) for j in jobs]),1):
            stage,r=f.result();results[stage].append(r)
            if i%32==0:print('PUBLICATION VALIDATION',i,'/2416',flush=True)
    for stage,rr in results.items():
        rr.sort(key=lambda r:(r['case']['id'],r['mode'],r['actor']));write(OUT/f'{stage}_summary.json',rr)
        if stage in ('development','final'):write(OUT/f'{stage}_assessment.json',assess(rr))
    write(OUT/'STATUS.json',dict(all_2416_completed=True,final_once_complete=True,native='NOT_RUN',actual_runtime='NOT_RUN'))


if __name__=='__main__':main()
