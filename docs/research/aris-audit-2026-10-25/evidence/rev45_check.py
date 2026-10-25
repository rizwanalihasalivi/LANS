"""Read-only independent revision4/5 artifact audit. No project writes."""
from pathlib import Path
import csv,gzip,json,math,hashlib,itertools,zipfile,pickle,statistics
import numpy as np
from stable_baselines3 import PPO

ROOT=Path('/workspace/LANS/integrations/webots')
RESEARCH=ROOT/'research'
OUT=Path('/workspace/lans-aris-audit')
result={}
def rows(p):
    with p.open() as f:return list(csv.DictReader(f))
def key(r):return tuple(r[k] for k in ('seed','speed','path','scenario'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

folders=[p for p in (ROOT/'results').iterdir() if p.name.startswith(('revision4','revision5'))]
allfiles=sorted(p for d in folders for p in d.rglob('*') if p.is_file())
result['files']=len(allfiles)
result['by_extension']={e:sum(p.suffix==e for p in allfiles) for e in sorted({p.suffix for p in allfiles})}
source_checks=[]
for p in allfiles:
    if '/source/' in str(p):
        relative=str(p).split('/source/',1)[1];original=RESEARCH/relative
        assert original.exists(),str(p)
        source_checks.append((str(p),p.read_bytes()==original.read_bytes()))
result['source_copies']={'count':len(source_checks),'all_identical_to_current':all(v for _,v in source_checks),'different':[p for p,v in source_checks if not v]}
decoded=[]
for p in allfiles:
    if p.suffix=='.json':json.loads(p.read_text());decoded.append(str(p))
    elif p.suffix=='.zip':
        with zipfile.ZipFile(p) as z:assert z.testzip() is None
    elif p.suffix=='.log':
        text=p.read_text();assert 'Traceback (most recent call last)' not in text,str(p)
result['json_parsed']=len(decoded)

grids={}
for name in ('revision4-pilots','revision5-audit','revision5-audit-invalid-config','revision5-robust'):
    d=ROOT/'results'/name
    path=d/'evaluation/episodes.csv' if name=='revision4-pilots' else d/'episodes.csv'
    data=rows(path);grids[name]=data
    methods=sorted({r['method'] for r in data})
    expected=set(itertools.product(('101','202'),('15','20','25'),('sine120','dlc220'),('nominal','tire_mismatch','low_friction','sensor_stress','latency20','latency100'),methods))
    keys=[key(r)+(r['method'],) for r in data]
    assert len(keys)==len(set(keys)) and set(keys)==expected
    for r in data:
        assert math.isfinite(float(r['penalized_rmse']))
        assert float(r['max_rate'])<=.3500001
        n,N=int(r['steps']),int(r['scheduled_steps'])
        score=math.sqrt((float(r['rmse'])**2*n+(N-n)*6.25)/N)
        assert math.isclose(score,float(r['penalized_rmse']),rel_tol=1e-12,abs_tol=1e-12)
        assert (n==N) if r['survived']=='True' else n<=N
    gridsummary={m:{'mean_penalized_rmse':statistics.mean(float(r['penalized_rmse']) for r in data if r['method']==m),'survived':sum(r['survived']=='True' for r in data if r['method']==m),'episodes':sum(r['method']==m for r in data)} for m in methods}
    result[name]={'rows':len(data),'means':gridsummary}
    report=(d/'report.md').read_text()
    if name in ('revision4-pilots','revision5-audit'):
        assert all(f"{v['mean_penalized_rmse']:.6f}" in report for v in gridsummary.values())

v4={(key(r)+(r['method'],)):r for r in grids['revision4-pilots']}
v5=grids['revision5-audit'];mapping={'lqr':'lqr','legacy':'legacy_gated_reference','A100k':'A_hybrid'}
parity=0
for r in v5:
    if r['method'] in mapping:
        q=v4[key(r)+(mapping[r['method']],)]
        assert all(r[k]==q[k] for k in ('penalized_rmse','survived','steps','noise_seed'))
        parity+=1
    if r['scenario']=='latency100':
        q=v4[key(r)+('lqr',)]
        assert r['penalized_rmse']==q['penalized_rmse'] and float(r['active_fraction'])==0
result['historical_reference_rows_exact']=parity
invalid=grids['revision5-audit-invalid-config']
result['invalid_lqr_diff_count']=sum(r['penalized_rmse']!=v4[key(r)+('lqr',)]['penalized_rmse'] for r in invalid if r['method']=='lqr')

done=json.loads((ROOT/'results/revision5-audit/complete.json').read_text())
for n,d in done['source_hashes'].items():assert digest(RESEARCH/n)==d
for seed,hashes in done['model_hashes'].items():
    paths={'legacy':ROOT/f'results/research-training/residual-{0 if seed=="101" else 1}/policy.zip','A100k':ROOT/f'results/revision4-pilots/training/A-{seed}/policy.zip'}
    for n,h in hashes.items():assert digest(paths[n])==h
result['v5_recorded_source_model_checks']=True

audit=rows(ROOT/'results/revision5-audit/predictor-audit.csv')
assert len(audit)==15648
assert len({(r['seed'],r['speed'],r['path'],r['scenario'],r['tick'],r['method']) for r in audit})==len(audit)
counts={}
for m in sorted({r['method'] for r in audit}):
    a=[r for r in audit if r['method']==m]
    counts[m]={'rows':len(a),'accepted':sum(r['reason']=='earned' for r in a),'false_accepts':sum(r['false_accept']=='True' for r in a),'cost_rejects':sum(r['reason']=='cost' for r in a),'false_rejects':sum(r['false_reject']=='True' for r in a),'safety_withheld_helpful':sum(r['safety_withheld_helpful']=='True' for r in a)}
    for r in a:
        choices=json.loads(r['choices']);assert len(choices)==3
        assert all(math.isfinite(c[k]) for c in choices for k in ('predicted_delta','ideal_state_predicted_delta','realized_delta'))
result['predictor_counts']=counts

traces=[]
for p in (ROOT/'results/revision4-pilots/evaluation/traces').glob('*.csv.gz'):
    with gzip.open(p,'rt') as f:data=list(csv.DictReader(f))
    stem=p.name.removesuffix('.csv.gz');r=next(r for r in grids['revision4-pilots'] if r['seed']=='101' and r['speed']=='25' and r['path']=='dlc220' and stem==r['method']+'-'+r['scenario'])
    assert len(data)==int(r['steps'])
    err=np.array([float(x['error_m']) for x in data]);assert math.isclose(float(np.sqrt(np.mean(err**2))),float(r['rmse']),rel_tol=1e-12)
    for x in data:
        assert math.isclose(float(x['state_time_s'])-float(x['command_time_s']),.01,abs_tol=1e-12)
        if float(x['weight'])>0:assert float(x['predicted_candidate_cost'])<float(x['predicted_lqr_cost']) and x['reason']=='earned' and float(x['age_s'])<.05
    traces.append(str(p))
result['traces_recomputed']=len(traces)

models=[]
for p in sorted((ROOT/'results/revision4-pilots/training').glob('*/policy.zip')):
    meta=json.loads(p.with_name('complete.json').read_text());model=PPO.load(p,device='cpu')
    assert model.num_timesteps==meta['steps']==100000 and model.seed==meta['seed']
    assert model.observation_space.shape==(9,) and model.action_space.shape==(1,)
    assert digest(p)==meta['policy_sha256']
    optimizer_steps=sorted({int(v['step'].item()) for v in model.policy.optimizer.state_dict()['state'].values()});assert optimizer_steps==[5000]
    with p.with_name('normalization.pkl').open('rb') as f:norm=pickle.load(f)
    assert not norm.norm_obs and norm.norm_reward and abs(norm.ret_rms.count-100000)<.001
    for n,d in meta['source_sha256'].items():assert digest(RESEARCH/n)==d
    monitors=[]
    for monitor in p.parent.glob('*.monitor.csv'):
        with monitor.open() as f:next(f);monitors.extend(csv.DictReader(f))
    completed=sum(int(r['l']) for r in monitors)
    assert 0<=100000-completed<6400
    models.append({'arm':meta['arm'],'seed':meta['seed'],'steps':model.num_timesteps,'optimizer_steps':optimizer_steps,'completed_episode_steps':completed,'completed_episode_gate_fraction':sum(float(r['episode_gate_fraction'])*int(r['l']) for r in monitors)/completed,'completed_episode_mean_bonus':sum(float(r['episode_mean_bonus'])*int(r['l']) for r in monitors)/completed})
result['training_models']=models
reserved=json.loads((RESEARCH/'revision4/reserved_split.json').read_text())
assert len(set(reserved['development_ids']))==72 and len(set(reserved['reserved_ids']))==180
assert not set(reserved['development_ids']) & set(reserved['reserved_ids'])
assert set(reserved['development_ids'])=={int(r['noise_seed']) for r in grids['revision4-pilots']}
result['reserved_disjoint']=True

(OUT/'rev45-check-results.json').write_text(json.dumps(result,indent=2)+'\n')
(OUT/'rev45-artifacts-machine-checked.txt').write_text('\n'.join(map(str,allfiles))+'\n')
print(json.dumps(result,indent=2))
