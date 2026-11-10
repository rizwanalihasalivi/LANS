"""Produce a technical JSON index from completed, independently audited evidence."""
from pathlib import Path
import json,math,re
import numpy as np
from integrations.unified_lans.inference import sha

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'results/publication-v9'


def load(path):return json.loads(path.read_text())


def main():
    audit=load(DATA/'verification.json')
    assert audit['all_requested_stages_verified']
    for name,digest in audit['input_hashes'].items():assert sha(ROOT/name)==digest,('Changed audited input',name)
    stages=audit['stages'];comparison={s:load(DATA/f'confirmation/{s}_assessment.json') for s in ('development','final')}
    safety={}
    for stage in ('regression-development','regression-stress','development','stress','final'):
        rr=load(DATA/f'confirmation/{stage}_summary.json');hh=[r for r in rr if r['mode']=='hybrid']
        safety[stage]=dict(all_episodes=len(rr),hybrid_episodes=len(hh),hybrid_failures=sum(r['failed'] for r in hh),
            hybrid_collision_episodes=sum(r['collisions']>0 for r in hh),hybrid_ppo_ticks=sum(r['ppo_ticks'] for r in hh))
    native=load(DATA/'native/summary.json');nm={}
    for mode in ('lqr','hybrid'):
        rr=[r for r in native if r['case']['mode']==mode]
        nm[mode]={key:float(np.mean([r[key] for r in rr])) for key in ('rmse_m','heading_rmse_rad','steering_rate_rms','progress_m')}
        rates=[]
        for r in rr:
            raw=DATA/'native'/r['case']['name']/'ticks.jsonl'
            rows=[json.loads(line) for line in raw.read_text().splitlines()]
            rates.append(math.sqrt(np.mean([((x['measured_steering_after']-x['measured_steering_before'])/.05)**2 for x in rows])))
        nm[mode]['measured_tick_steering_rate_rms']=float(np.mean(rates))
    nb={(r['case']['route'],r['case']['speed']):r for r in native if r['case']['mode']=='lqr'}
    native_detail=[]
    for r in native:
        if r['case']['mode']!='hybrid':continue
        b=nb[(r['case']['route'],r['case']['speed'])]
        native_detail.append(dict(case=r['case']['name'],gain_percent=100*(1-r['rmse_m']/b['rmse_m']),
            heading_ratio=r['heading_rmse_rad']/b['heading_rmse_rad'],rate_ratio=r['steering_rate_rms']/b['steering_rate_rms'],
            progress_ratio=r['progress_m']/b['progress_m'],ppo_ticks=r['ppo_ticks'],mpc_ticks=r['mpc_ticks']))
    timing={}
    live=load(DATA/'live-functional/summary.json')
    for role in ('old','new'):
        rows=[]
        for record in live:
            if record['role']==role:
                rows.extend(json.loads(line) for line in (DATA/'live-functional'/record['directory']/'ticks.jsonl').read_text().splitlines())
        timing[role]=dict(stages['runtime']['roles'][role])
        for metric in ('response_ms','cycle_ms','scheduled_response_ms','scheduled_cycle_ms'):
            values=[r[metric] for r in rows]
            timing[role][metric]=dict(mean=float(np.mean(values)),p95=float(np.percentile(values,95)),maximum=max(values))
    tests=Path('/workspace/cloud-setup/publication-v9-unique-focused-tests.log')
    match=re.search(r'(\d+) passed',tests.read_text());assert match
    result=dict(verification_sha256=sha(DATA/'verification.json'),summary_source_sha256=sha(Path(__file__)),
        simulations=sum(stages[s]['episodes'] for s in ('calibration','baselines','confirmation')),
        simulation_ticks=sum(stages[s]['ticks'] for s in ('calibration','baselines','confirmation')),
        new_training_steps=stages['training']['steps'],training_collision_episodes=sum(r['failures'] for r in stages['training']['endpoints']),
        training_diagnostic_sha256=sha(DATA/'training-diagnostics/audit.json'),
        unique_focused_tests=int(match.group(1)),focused_test_log_sha256=sha(tests),python_safety=safety,
        development=comparison['development'],final=comparison['final'],runtime=timing,
        native=dict(metrics=nm,overall_mean_gain_percent=100*(1-nm['hybrid']['rmse_m']/nm['lqr']['rmse_m']),
            matched_cases=native_detail,verification=stages['native'],
            inference='Descriptive fixed single-vehicle transfer; no traffic/collision assessment or statistical generalization.'),
        candidate_promoted=False,requested_30_achieved=False,
        remaining=['Meaningful incremental learned benefit and the requested 30% whole-run gain.',
            'Python final progress failures and shared crossing training collisions.',
            'Full native traffic/V2V validation, target-hardware worst-case timing and closest published-method novelty evidence.'])
    (DATA/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print('Technical JSON summary saved; no thesis draft, figure or presentation table generated.')


if __name__=='__main__':main()
