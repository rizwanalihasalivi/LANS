"""Bounded independent CSV/result consistency checks; no training/simulation."""
from pathlib import Path
import csv,json,math,statistics,collections,zipfile,itertools
R=Path('/workspace/LANS'); O=Path('/workspace/lans-aris-audit'); W=R/'integrations/webots'; out={'grids':{},'errors':[]}
def read(p):
    with p.open() as f:return list(csv.DictReader(f))
specs=[('research-evaluation','episodes.csv','failure_penalized_rmse_m'),('revision2-development','episodes.csv','penalized_rmse'),('revision2-test','episodes.csv','penalized_rmse'),('revision2-native-test','episodes.csv','penalized_rmse_m'),('revision3-pilots','development.csv','penalized_rmse'),('revision3-extended','development.csv','penalized_rmse'),('revision3-600k','development.csv','penalized_rmse'),('revision4-pilots','evaluation/episodes.csv','penalized_rmse'),('revision5-audit','episodes.csv','penalized_rmse'),('revision5-robust','episodes.csv','penalized_rmse')]
allrows={}
for stage,fname,metric in specs:
    rows=read(W/'results'/stage/fname);allrows[stage]=rows
    if metric not in rows[0]:metric=next(k for k in rows[0] if 'penalized' in k)
    methods=sorted(set(r['method'] if 'method' in r else r['mode'] for r in rows));methodkey='method' if 'method' in rows[0] else 'mode'
    keyfields=[k for k in ['seed','speed','speed_m_s','path','scenario','region',methodkey,'delay_ms','config_index'] if k in rows[0]]
    keys=[tuple(r[k] for k in keyfields) for r in rows]
    assert len(keys)==len(set(keys)),stage
    penalty_checks=0
    for r in rows:
        assert math.isfinite(float(r[metric])),stage
        if all(k in r for k in ['steps','scheduled_steps']):
            n,N=int(r['steps']),int(r['scheduled_steps']);raw=float(r.get('rmse',r.get('rmse_m')))
            assert 0<n<=N
            assert math.isclose(math.sqrt((n*raw**2+(N-n)*6.25)/N),float(r[metric]),rel_tol=1e-10,abs_tol=1e-10),(stage,r)
            penalty_checks+=1
    summary={m:{'n':sum(r[methodkey]==m for r in rows),'survived':sum(r[methodkey]==m and r['survived']=='True' for r in rows),'mean':statistics.mean(float(r[metric]) for r in rows if r[methodkey]==m)} for m in methods}
    result={'rows':len(rows),'keys_unique':True,'keyfields':keyfields,'penalty_recomputed':penalty_checks,'methods':summary,'metric':metric}
    if stage=='research-evaluation':
        saved=json.loads((W/'results'/stage/'summary.json').read_text())
        for m,v in summary.items():assert math.isclose(v['mean'],saved[m]['mean_penalized_rmse'],abs_tol=1e-12)
    out['grids'][stage]=result
# Historical parity and fallback on actual raw rows.
key=lambda r:tuple(r[k] for k in ('seed','speed','path','scenario'))
v4={key(r)+(r['method'],):r for r in allrows['revision4-pilots']};parity=0;severe=0
for r in allrows['revision5-audit']:
    mapping={'lqr':'lqr','legacy':'legacy_gated_reference','A100k':'A_hybrid'}
    if r['method'] in mapping:
        q=v4[key(r)+(mapping[r['method']],)]
        assert all(r[k]==q[k] for k in ['penalized_rmse','survived','steps','noise_seed']);parity+=1
    if r['scenario']=='latency100':
        assert r['penalized_rmse']==v4[key(r)+('lqr',)]['penalized_rmse'] and float(r['active_fraction'])==0;severe+=1
out['v5_reference_exact_rows']=parity;out['v5_exact_severe_rows']=severe
prev={key(r)+(r['method'],):r for r in allrows['revision3-extended']};parity=0
for r in allrows['revision3-600k']:
    if r['method']=='baseline600':continue
    q=prev[key(r)+(r['method'],)];assert all(r[k]==q[k] for k in ['penalized_rmse','survived','steps','noise_seed']);parity+=1
out['v3_reference_exact_rows']=parity
raw=read(W/'results/revision5-audit/predictor-audit.csv');out['predictor']={}
for name in sorted(set(r['method'] for r in raw)):
    rr=[r for r in raw if r['method']==name]
    out['predictor'][name]={'n':len(rr),'accepted':sum(r['reason']=='earned' for r in rr),'false_accept':sum(r['false_accept']=='True' for r in rr),'false_reject':sum(r['false_reject']=='True' for r in rr)}
reserve=json.loads((W/'research/revision4/reserved_split.json').read_text());assert not set(reserve['development_ids'])&set(reserve['reserved_ids']);assert len(reserve['development_ids'])==72 and len(reserve['reserved_ids'])==180
out['reserved_disjoint']={'development':72,'reserved':180}
# Archive supplied manuscript numbers, independently aggregate added targeted results.
base=O/'claims-attachments/LANS_JSA_Submission_Candidate_Package';rr=read(base/'LANS_targeted_ablation_results.csv');out['candidate_targeted']={}
for mode in sorted(set(r['mode'] for r in rr)):
    rs=[r for r in rr if r['mode']==mode];out['candidate_targeted'][mode]={'n':len(rs),'keys':list(rs[0]),'mean_rmse':statistics.mean(float(r['rmse_m']) for r in rs)}
# Metadata budgets/timings, without loading or retraining checkpoints.
out['training_metadata']=[]
for stage in ['research-training','revision3-pilots','revision3-extended','revision3-600k','revision4-pilots/training']:
    for p in sorted((W/'results'/stage).glob('*/complete.json')):
        d=json.loads(p.read_text());out['training_metadata'].append({'stage':stage,'path':str(p.relative_to(R)),**{k:d[k] for k in ['steps','seed','wall_s','role','candidate','arm','additional_steps'] if k in d}})
(O/'completion-check-results.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'grids':{k:{'rows':v['rows'],'means':{m:round(d['mean'],9) for m,d in v['methods'].items()}} for k,v in out['grids'].items()},'v5_parity':out['v5_reference_exact_rows'],'v3_parity':out['v3_reference_exact_rows'],'candidate':out['candidate_targeted'],'training_metadata_count':len(out['training_metadata'])},indent=2))
