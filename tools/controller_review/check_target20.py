"""Strict research-target checker; diagnostics never stand in for missing baselines."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
ROOT=Path(__file__).resolve().parents[2]

def evaluate(rows,source='ppo_rk'):
    sources=('lqr','student_rk','planner_rk','ppo_euler');mean=lambda rr,key:statistics.mean(float(r[key]) for r in rr)
    selected=[r for r in rows if r['source']==source];reasons=[];gains={};lqr=[r for r in rows if r['source']=='lqr']
    if not selected or not lqr:raise ValueError('Complete candidate and baseline matrix required')
    for ref in sources:
        other=[r for r in rows if r['source']==ref]
        assert len(other)==len(selected),'Unmatched episode counts'
        key=lambda r:(r['pair'],r['speed'],r['path'],r['mirror'],r['scenario'],r['noise_id'])
        assert {key(r) for r in selected}=={key(r) for r in other},'Unmatched information/episode conditions'
        gain=100*(1-mean(selected,'rmse_m')/mean(other,'rmse_m'));gains[ref]=gain
        if mean(selected,'rmse_m')>.8*mean(other,'rmse_m'):reasons.append('less_than_20pct_vs_'+ref)
        for pair in sorted({r['pair'] for r in selected}):
            aa=[r for r in selected if r['pair']==pair];bb=[r for r in other if r['pair']==pair]
            if mean(aa,'rmse_m')>=mean(bb,'rmse_m'):reasons.append('nonpositive_pair_gain_'+str(pair)+'_vs_'+ref)
    for metric in ('heading_rmse_rad','rate_rms_rad_s'):
        if mean(selected,metric)>1.05*mean(lqr,metric):reasons.append('more_than_5pct_'+metric)
    a=[r for r in selected if r['scenario']=='nominal'];b=[r for r in lqr if r['scenario']=='nominal']
    assert a and b
    if mean(a,'rmse_m')>1.02*mean(b,'rmse_m'):reasons.append('nominal_more_than_2pct_worse_lqr')
    if any(r['survived']!='True' for r in selected):reasons.append('candidate_survival_loss')
    return dict(matched_diagnostic_pass=not reasons,gains_pct=gains,reasons=reasons)

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();a.run=a.run.resolve();rows=list(csv.DictReader((a.run/'episodes.csv').open()));result=evaluate(rows)
    result.update(full_twenty_percent_claim=False,missing_comparators=['both fixed residual controls in this new numerical controller grid','full matched robust published vehicle controller/MPC'],scope='Stricter supplemental target check includes nominal and per-pair guards omitted from the narrow diagnostic boolean; it never relaxes the frozen protocol or promotes a controller.',actual_laptop=False,reserved_unopened=True)
    missed=[]
    for f in (a.run/'timing/on').glob('seed-*/*-ticks.csv'):
        for row in csv.DictReader(f.open()):
            if row['deadline_miss']=='True':
                missed.append(dict(trace=str(f.relative_to(a.run)),tick=int(row['tick']),release_lateness_ms=int(row['release_lateness_ns'])/1e6,processing_ms=int(row['control_ns'])/1e6,thread_cpu_ms=int(row['control_cpu_ns'])/1e6,budget_skipped=row['decision_skipped']=='True'))
    result['deadline_attribution']=missed
    result['deadline_interpretation']='A release already beyond10ms is a miss before current control work. Unrecorded prior-cycle post-commit work, timer wakeup and host scheduling cannot be separated by these traces; no unique root cause or hard real-time guarantee is asserted.'
    prior=ROOT/'docs/research/reviewer-pipeline-v9'
    frozen=subprocess.check_output(['git','show','5f80922:docs/research/reviewer-pipeline-v9/evidence-hashes.json'],cwd=ROOT)
    assert frozen==(prior/'evidence-hashes.json').read_bytes(),'Prior model/data provenance seal changed'
    expected=json.loads(frozen)['sha256'];model_hashes={}
    for seed in (701,802,903):
        for name in (f'actors/student-{seed}.npz',f'actors/causal_history-{seed}.npz',f'runtime-actors/causal_history/model-{seed}.npz'):
            digest=hashlib.sha256((prior/name).read_bytes()).hexdigest();assert digest==expected[name],name;model_hashes[name]=digest
    result['actual_input_model_hashes']=model_hashes
    result['model_provenance']='Checked against immutable prior v9 evidence seal from git commit5f80922; supplemental check closes the new diagnostic manifest output-model dependency gap.'
    result['hashes']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in (Path(__file__),a.run/'episodes.csv',a.run/'summary.json',a.run/'decision.json')}
    file=a.run.with_name(a.run.name+'-target20.json')
    if file.exists():assert result==json.loads(file.read_text()),'Supplemental target inputs changed'
    else:file.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
