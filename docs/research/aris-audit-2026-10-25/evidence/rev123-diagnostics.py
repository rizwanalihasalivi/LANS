"""Independent read-only evidence checks for the ARIS rev1-3 review."""
import csv, gzip, hashlib, itertools, json, math, pickle, sys
from pathlib import Path
from statistics import mean, stdev
import torch
from stable_baselines3 import PPO

ROOT=Path('/workspace/LANS/integrations/webots')
OUT=Path('/workspace/lans-aris-audit')
RESEARCH=ROOT/'research'
torch.set_num_threads(1)
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    with p.open() as f: return list(csv.DictReader(f))

report={'checkpoints':[], 'grids':{}, 'source_comparison':[], 'representative_traces':[]}
stages={'research-training':1000000,'revision3-pilots':100000,'revision3-extended':300000,'revision3-600k':600000}
for stage,steps in stages.items():
    for folder in sorted((ROOT/'results'/stage).iterdir()):
        if not (folder/'policy.zip').is_file(): continue
        meta=json.loads((folder/'complete.json').read_text())
        model=PPO.load(folder/'policy.zip',device='cpu')
        assert model.num_timesteps==meta['steps']==steps
        assert model.seed==meta['seed']
        assert sha(folder/'policy.zip')==meta['policy_sha256']
        for name,digest in meta['source_sha256'].items():
            archived=folder/'source'/name
            assert sha(archived)==digest
            active=RESEARCH/name
            report['source_comparison'].append({'stage':stage,'checkpoint':folder.name,'source':name,'same_as_current':active.is_file() and sha(active)==digest})
        with (folder/'normalization.pkl').open('rb') as f: norm=pickle.load(f)
        assert norm.norm_obs is False and norm.norm_reward is True
        assert abs(norm.ret_rms.count-steps-.0001)<1e-5
        counters=sorted({int(v['step'].item()) for v in model.policy.optimizer.state_dict()['state'].values()})
        assert counters==[steps//20]
        done=0
        for p in folder.glob('*.monitor.csv'):
            with p.open() as f: next(f);done+=sum(int(r['l']) for r in csv.DictReader(f))
        additional=meta.get('additional_steps',steps)
        assert 0<=additional-done<6400
        report['checkpoints'].append({'stage':stage,'checkpoint':folder.name,'seed':model.seed,'steps':steps,'optimizer_steps':counters,'reward_normalization_count':norm.ret_rms.count,'completed_monitor_steps':done,'additional_steps':additional})
        del model,norm

base=json.loads((RESEARCH/'revision2/protocol.json').read_text())
grids=[('research-evaluation','episodes.csv','failure_penalized_rmse_m'),('revision2-development','episodes.csv','penalized_rmse'),('revision2-test','episodes.csv','penalized_rmse'),('revision3-pilots','development.csv','penalized_rmse'),('revision3-extended','development.csv','penalized_rmse'),('revision3-600k','development.csv','penalized_rmse')]
for stage,filename,metric in grids:
    folder=ROOT/'results'/stage; rows=read(folder/filename)
    assert all(math.isfinite(float(r[metric])) for r in rows)
    for r in rows:
        assert 0<int(r['steps'])<=int(r['scheduled_steps'])
        if r['survived']=='True':assert int(r['steps'])==int(r['scheduled_steps'])
        raw=float(r.get('rmse_m',r.get('rmse')))
        independent=math.sqrt((raw**2*int(r['steps'])+(int(r['scheduled_steps'])-int(r['steps']))*6.25)/int(r['scheduled_steps']))
        assert abs(independent-float(r[metric]))<1e-12
    names=sorted(set(r['method'] for r in rows))
    if stage=='research-evaluation':
        keys=[(int(r['seed']),int(r['speed_m_s']),r['path'],int(r['delay_ms']),r['method']) for r in rows]
        expected=set(itertools.product(range(5),(15,20,25),('dlc220','sine120','sine160'),(0,20,100),names))
    elif stage=='revision2-development':
        keys=[(int(r['seed']),int(r['speed']),r['path'],r['scenario'],r['method'],int(r['config_index'])) for r in rows]
        expected={(s,v,'sine120',region,m,c) for s,v,region in itertools.product((0,1),(15,25),base['scenarios']) for m in ('lqr','gated_residual') for c in ((0,) if m=='lqr' else (0,1,2))}
    else:
        seeds=range(5) if stage=='revision2-test' else (101,202)
        keys=[(int(r['seed']),int(r['speed']),r['path'],r['scenario'],r['method']) for r in rows]
        expected=set(itertools.product(seeds,(15,20,25),base['paths'],base['scenarios'],names))
    assert len(keys)==len(set(keys))==len(expected) and set(keys)==expected
    aggregates={m:{'n':sum(r['method']==m for r in rows),'survived':sum(r['method']==m and r['survived']=='True' for r in rows),'mean':mean(float(r[metric]) for r in rows if r['method']==m)} for m in names}
    if stage=='research-evaluation':
        saved=json.loads((folder/'summary.json').read_text())
        for m in names:
            assert abs(aggregates[m]['mean']-saved[m]['mean_penalized_rmse'])<1e-12
            seedmeans=[mean(float(r[metric]) for r in rows if r['method']==m and int(r['seed'])==s) for s in range(5)]
            assert abs(stdev(seedmeans)-saved[m]['sample_sd_across_seeds'])<1e-12
    if stage=='revision2-test':
        saved=json.loads((folder/'verification.json').read_text())
        for region in base['scenarios']:
            diffs=[mean(float(r[metric]) for r in rows if r['scenario']==region and int(r['seed'])==s and r['method']=='gated_residual')-mean(float(r[metric]) for r in rows if r['scenario']==region and int(r['seed'])==s and r['method']=='lqr') for s in range(5)]
            assert max(abs(a-b) for a,b in zip(diffs,saved['comparisons'][region]['paired_seed_differences']))<1e-12
    report['grids'][stage]={'n':len(rows),'survived':sum(r['survived']=='True' for r in rows),'aggregates':aggregates,'unique_complete_grid':True}
    for p in sorted((folder/'traces').glob('*.csv.gz')):
        with gzip.open(p,'rt') as f: trace=list(csv.DictReader(f))
        assert trace
        errors=[float(r['error_m']) for r in trace]
        assert all(math.isfinite(x) for x in errors)
        report['representative_traces'].append({'path':str(p),'rows':len(trace),'rmse':math.sqrt(mean(x*x for x in errors))})

old=read(ROOT/'results/revision3-extended/development.csv');new=read(ROOT/'results/revision3-600k/development.csv')
key=lambda r:(r['seed'],r['speed'],r['path'],r['scenario'],r['method'])
prior={key(r):r for r in old};count=0
for r in new:
    if r['method']=='baseline600':continue
    assert all(r[k]==prior[key(r)][k] for k in ['penalized_rmse','rmse','survived','steps','scheduled_steps','noise_seed']);count+=1
report['exact_300k_600k_reference_cells']=count
report['planned_v3_final_artifacts_present']={name:(ROOT/'results'/name).exists() for name in ['revision3-training','revision3-test','revision3-native-smoke']}
(OUT/'rev123-diagnostics.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'checkpoints':len(report['checkpoints']),'grid_counts':{k:v['n'] for k,v in report['grids'].items()},'trace_count':len(report['representative_traces']),'source_comparisons':len(report['source_comparison']),'source_differences':sum(not x['same_as_current'] for x in report['source_comparison']),'reference_cells':count,'planned_artifacts':report['planned_v3_final_artifacts_present']},indent=2))
