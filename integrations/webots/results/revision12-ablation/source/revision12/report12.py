"""Strict raw-data verification and predeclared revision12 spending decision.

This reporter never reads reserved data, trains, or chooses new thresholds.
"""
import argparse
import csv
import hashlib
import itertools
import json
import math
import re
from pathlib import Path, PurePosixPath
from statistics import mean, stdev

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / 'protocol.json').read_text())
COLUMNS = {'repetition','seed','noise_id','speed','path','scenario','method',
           'survived','steps','scheduled_steps','rmse','penalized_rmse',
           'active_fraction','mean_weight','max_rate','max_command','max_actuator',
           'trajectory_sha256','wall_p99_s','submissions','max_packet_age_s'}
INT_FIELDS = ('repetition','seed','noise_id','speed','steps','scheduled_steps','submissions')
FLOAT_FIELDS = ('rmse','penalized_rmse','active_fraction','mean_weight','max_rate',
                'max_command','max_actuator','wall_p99_s','max_packet_age_s')
REQUIRED_SOURCES = {
    'revision12/protocol.json', 'revision12/run12.py', 'revision12/gate12.py',
    'revision12/report12.py', 'revision12/test_gate12.py', 'revision12/test_report12.py',
    'revision8/bootstrap.py', 'revision8/student.py', 'revision8/teacher.py',
    'revision8/protocol.json', 'revision7/kernels.py', 'revision7/bootstrap.py',
    'revision5/execution.py', 'revision5/bootstrap.py', 'revision2/gating.py',
    'revision2/plant.py', 'revision6/protocol.json', 'core.py', 'comparison.py',
    'comparison-protocol.json', 'protocol.json',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def cell(row):
    return (row['repetition'],row['speed'],row['path'],row['scenario'])


def validate_metadata(complete, protocol=PROTOCOL):
    require(complete.get('protocol') == protocol, 'completion protocol mismatch')
    require(complete.get('submission_semantics') == 'every-available-worker-v1', 'submission semantics mismatch')
    require(complete.get('split') == 'development', 'completion split must be development')
    require(type(complete.get('training_steps')) is int and complete['training_steps'] == 0, 'screen must record zero training steps')
    require(complete.get('reserved_split_opened') is False, 'reserved split must remain unopened')
    require(re.fullmatch(r'[0-9a-f]{7,40}',str(complete.get('source_commit',''))) is not None, 'source commit missing or invalid')
    students = complete.get('students', {})
    require(isinstance(students,dict) and set(students) == set(map(str,protocol['student_seeds'])), 'student metadata incomplete')
    for values in students.values():
        require(isinstance(values,dict) and set(values) == {'student.pt','normalization.npz','complete.json'}, 'student artifact metadata incomplete')
        require(all(re.fullmatch(r'[0-9a-f]{64}',str(v)) for v in values.values()), 'invalid student artifact digest')
    sources = complete.get('sources', {})
    require(isinstance(sources,dict) and REQUIRED_SOURCES.issubset(sources), 'source manifest incomplete')
    for name,digest in sources.items():
        require(isinstance(name,str), 'invalid source path')
        path=PurePosixPath(name)
        require(not path.is_absolute() and bool(path.parts) and '..' not in path.parts and str(path)==name and '\\' not in name, 'unsafe source path')
        require(re.fullmatch(r'[0-9a-f]{64}',str(digest)) is not None, 'invalid source digest')


def verify_archive(run, complete):
    validate_metadata(complete)
    archive=(run/'source').resolve()
    for name,digest in complete['sources'].items():
        source=(archive/name).resolve()
        require(source.is_relative_to(archive) and source.is_file(), 'missing or unsafe archived source: '+name)
        require(hashlib.sha256(source.read_bytes()).hexdigest()==digest, 'archived source digest mismatch: '+name)
    archived_protocol=json.loads((archive/'revision12/protocol.json').read_text())
    require(archived_protocol==complete['protocol'], 'archived protocol mismatch')


def validate(raw_rows, complete, protocol=PROTOCOL):
    validate_metadata(complete, protocol)
    rows=[]
    for raw in raw_rows:
        require(set(raw) == COLUMNS, 'episode schema mismatch')
        row=dict(raw)
        for field in INT_FIELDS:
            try:
                number=float(raw[field]);integer=int(number)
            except (ValueError,TypeError,OverflowError) as exc:
                raise ValueError('invalid integer '+field) from exc
            require(math.isfinite(number) and integer==number, 'noninteger '+field)
            row[field]=integer
        for field in FLOAT_FIELDS:
            try:row[field]=float(raw[field])
            except (ValueError,TypeError) as exc:raise ValueError('invalid number '+field) from exc
            require(math.isfinite(row[field]) and row[field]>=0, 'nonfinite/negative '+field)
        require(str(raw['survived']).lower() in ('true','false'), 'invalid survival flag')
        row['survived']=str(raw['survived']).lower()=='true'
        require(re.fullmatch(r'[0-9a-f]{64}',str(row['trajectory_sha256'])) is not None, 'invalid trajectory digest')
        rows.append(row)
    expected=set(itertools.product(protocol['repetitions'],protocol['speeds'],protocol['paths'],protocol['scenarios'],protocol['methods']))
    keys=[cell(r)+(r['method'],) for r in rows]
    require(len(keys)==len(set(keys))==len(expected)==protocol['development_episodes']==complete.get('episodes'), 'incomplete or duplicate development grid')
    require(set(keys)==expected, 'unexpected development cells')
    lookup=dict(zip(keys,rows))
    for row in rows:
        rep=row['repetition'];v=row['speed'];n=row['steps'];total=row['scheduled_steps']
        require(row['seed']==protocol['student_seeds'][rep], 'student seed mismatch')
        expected_noise=protocol['development_noise_base']+rep*10000+v*100+protocol['paths'].index(row['path'])*10+protocol['scenarios'].index(row['scenario'])
        require(row['noise_id']==expected_noise, 'development noise identity mismatch')
        require(total==math.ceil((220/v+2)/.01) and 0<n<=total, 'episode horizon mismatch')
        require(not row['survived'] or n==total, 'survival requires complete episode')
        penalty=math.sqrt((n*row['rmse']**2+(total-n)*6.25)/total)
        require(math.isclose(row['penalized_rmse'],penalty,rel_tol=1e-10,abs_tol=1e-10), 'failure penalty mismatch')
        require(row['max_rate']<=.3500001 and row['max_command']<=.5000001 and row['max_actuator']<=.5000001, 'physical bound violation')
        require(row['active_fraction']<=1 and row['mean_weight']<=.5*row['active_fraction']+1e-12, 'gate activity/weight bound violation')
        require(abs(row['active_fraction']*n-round(row['active_fraction']*n))<=1e-7, 'activity fraction inconsistent with ticks')
        require(0<=row['submissions']<=n, 'submission count out of bounds')
        if row['method']=='lqr':
            require(row['submissions']==0 and row['active_fraction']==0 and row['mean_weight']==0 and row['max_packet_age_s']==0, 'LQR must not submit learned requests')
        if row['scenario']=='latency100':
            baseline=lookup[cell(row)+('lqr',)]
            require(row['trajectory_sha256']==baseline['trajectory_sha256'] and row['rmse']==baseline['rmse'] and row['penalized_rmse']==baseline['penalized_rmse'] and row['survived']==baseline['survived'] and row['steps']==baseline['steps'] and row['active_fraction']==0 and row['mean_weight']==0, 'severe-delay exact fallback mismatch')
    return sorted(rows,key=lambda r:(r['repetition'],r['speed'],protocol['paths'].index(r['path']),protocol['scenarios'].index(r['scenario']),protocol['methods'].index(r['method'])))


def reduction(value, reference):
    # Zero baseline error cannot support a positive improvement claim.
    if reference==0:return 0. if value==0 else -math.inf
    return 100*(1-value/reference)


def finite_or_none(value):
    # JSON cannot represent undefined relative reductions against zero error.
    return value if math.isfinite(value) else None


def assess(rows, complete, protocol=PROTOCOL):
    rows=validate(rows,complete,protocol)
    lookup={cell(r)+(r['method'],):r for r in rows}
    def subset(method,region=None,rep=None):
        return [r for r in rows if r['method']==method and (region is None or r['scenario']==region) and (rep is None or r['repetition']==rep)]
    def score(method,region=None,rep=None):return mean(r['penalized_rmse'] for r in subset(method,region,rep))
    def survival(method,reference):return all(not lookup[cell(r)+(reference,)]['survived'] or r['survived'] for r in subset(method))
    def gain(method,reference,region=None,rep=None):return reduction(score(method,region,rep),score(reference,region,rep))
    summary={m:dict(mean_penalized_rmse=score(m),survived=sum(r['survived'] for r in subset(m)),episodes=len(subset(m)),
                   paired_seed_mean_sd=stdev(score(m,rep=i) for i in protocol['repetitions']),reduction_vs_lqr_percent=finite_or_none(gain(m,'lqr'))) for m in protocol['methods']}
    rules=protocol['gate_progress'];stress=rules['stress_regions'];assessments={}
    for variant in ('preview','lateral'):
        method=variant+'_student';reference='legacy_student'
        qualifying_stress=[r for r in stress if gain(method,reference,r)>=1.]
        checks={
            'overall_gain_vs_legacy_student':gain(method,reference)>=rules['overall_gain_vs_legacy_student_percent'],
            'all_three_seed_means_better':all(score(method,rep=i)<score(reference,rep=i) for i in protocol['repetitions']),
            'minimum_stress_regions_with_one_percent_gain':len(qualifying_stress)>=rules['minimum_stress_regions_with_one_percent_gain'],
            'active_regions_preserved':all(score(method,r)<=score(reference,r)*(1+rules['maximum_active_region_regression_vs_legacy_student_percent']/100) for r in protocol['scenarios'] if r!='latency100'),
            'nominal_not_worse_than_lqr':score(method,'nominal')<=score('lqr','nominal'),
            'cellwise_survival_lqr':survival(method,'lqr'),
            'cellwise_survival_legacy_student':survival(method,reference),
            'exact_severe_fallback':True}
        learning={}
        for proposer in ('fixed_m004','fixed_p004'):
            control=variant+'_'+proposer
            learning['one_percent_gain_vs_'+proposer]=gain(method,control)>=1.
            learning['cellwise_survival_vs_'+proposer]=survival(method,control)
        five_regions=[r for r in stress if gain(method,'lqr',r)>=5. and all(score(method,r,i)<score('lqr',r,i) for i in protocol['repetitions'])]
        preservation=all(checks[k] for k in ('active_regions_preserved','nominal_not_worse_than_lqr','cellwise_survival_lqr','cellwise_survival_legacy_student','exact_severe_fallback'))
        assessments[variant]=dict(gate_progress_checks=checks,gate_progress_pass=all(checks.values()),
            learning_benefit_checks=learning,learning_benefit_pass=all(learning.values()),
            eligible=all(checks.values()) and all(learning.values()),mean_penalized_rmse=score(method),
            reduction_vs_legacy_student_percent=finite_or_none(gain(method,reference)),qualifying_one_percent_stress_regions=qualifying_stress,
            five_percent_qualifying_stress_regions=five_regions,five_percent_regional_target=len(five_regions)>=2 and preservation,
            overall_five_percent_reduction=gain(method,'lqr')>=5.,overall_reduction_vs_lqr_percent=finite_or_none(gain(method,'lqr')))
    eligible=[v for v in ('preview','lateral') if assessments[v]['eligible']]
    selected=None;selection_reason='No variant passes both gate progress and learned-benefit screens.'
    if len(eligible)==1:
        selected=eligible[0];selection_reason='Only eligible variant.'
    elif len(eligible)==2:
        a,b=(assessments[v]['mean_penalized_rmse'] for v in ('preview','lateral'))
        if abs(a-b)<=.01*min(a,b):selected='preview';selection_reason='Within 1% of lower mean; predefined preview preference.'
        else:selected=min(eligible,key=lambda v:assessments[v]['mean_penalized_rmse']);selection_reason='Lower mean among eligible variants beyond the tie band.'
    result=dict(protocol=protocol,source_commit=complete['source_commit'],summary=summary,assessments=assessments,
                eligible_variants=eligible,selected_gate=selected,selection_reason=selection_reason,
                next_action='independent_development_teacher_confirmation' if selected else 'stop_retraining_path',
                additional_rl_steps_run=0,training_authorized_now=False,reserved_opened=False,
                interpretation='Development spending screen only; no automatic full training, deployment or statistical superiority.')
    return rows,result


def write_report(run):
    complete=json.loads((run/'complete.json').read_text())
    verify_archive(run,complete)
    with (run/'episodes.csv').open(newline='') as handle:raw=list(csv.DictReader(handle))
    rows,result=assess(raw,complete)
    def score(method,region=None,rep=None):return mean(r['penalized_rmse'] for r in rows if r['method']==method and (region is None or r['scenario']==region) and (rep is None or r['repetition']==rep))
    lines=['# Revision12 predictor / objective development ablation','',
           f"Source freeze: `{result['source_commit']}` (from completion record). All {len(rows)} paired development episodes and archived source digests are validated. The completion record declares zero training steps and an unopened reserved split; this reporter reads only this development run and launches no training.",'',
           '## Overall raw results','','| Method | Survival /108 | Mean penalized RMSE (m) | Paired seed-mean SD | Reduction vs LQR |','|---|---:|---:|---:|---:|']
    for method,value in result['summary'].items():
        gain=value['reduction_vs_lqr_percent'];percent='undefined (zero reference)' if gain is None else f'{gain:+.3f}%'
        lines.append(f"| {method} | {value['survived']} | {value['mean_penalized_rmse']:.8f} | {value['paired_seed_mean_sd']:.8f} | {percent} |")
    lines+=['','## Regional raw mean RMSE','','| Region | '+' | '.join(PROTOCOL['methods'])+' |','|---|'+'---:|'*len(PROTOCOL['methods'])]
    for region in PROTOCOL['scenarios']:lines.append('| '+region+' | '+' | '.join(f'{score(m,region):.8f}' for m in PROTOCOL['methods'])+' |')
    lines+=['','## Paired seed raw mean RMSE','','| Student seed / noise pair | '+' | '.join(PROTOCOL['methods'])+' |','|---|'+'---:|'*len(PROTOCOL['methods'])]
    for rep,seed in zip(PROTOCOL['repetitions'],PROTOCOL['student_seeds']):lines.append(f'| {seed} / {rep} | '+' | '.join(f'{score(m,rep=rep):.8f}' for m in PROTOCOL['methods'])+' |')
    lines+=['','## Frozen screens','','| Variant | Gate progress | Learning benefit vs both constants | Eligible | Regional 5% target | Overall 5% reduction |','|---|---|---|---|---|---|']
    for variant,value in result['assessments'].items():
        lines.append(f"| {variant} | {value['gate_progress_pass']} | {value['learning_benefit_pass']} | {value['eligible']} | {value['five_percent_regional_target']} | {value['overall_five_percent_reduction']} |")
    for variant,value in result['assessments'].items():
        lines+=['',f"{variant} failed gate checks: "+(', '.join(k for k,v in value['gate_progress_checks'].items() if not v) or 'none')+'.',
                f"{variant} failed learned-benefit checks: "+(', '.join(k for k,v in value['learning_benefit_checks'].items() if not v) or 'none')+'.',
                f"{variant} qualifying 5% stress regions (each lower in all three pairs): "+(', '.join(value['five_percent_qualifying_stress_regions']) or 'none')+'.','']
    lines+=['',f"Selected gate: **{result['selected_gate'] or 'none'}**. {result['selection_reason']}",'',
            'Independent teacher confirmation is the next permitted stage; retraining and reserved evaluation remain unopened.' if result['selected_gate'] else 'No variant qualifies. Stop the retraining path at this development screen; additional RL steps 0 and reserved split unopened.',
            '', '## Limits','',
            'The original student weights and train-only standardizer remain frozen. Changing a gate changes the 20-feature history distribution even when feature names and actor weights are identical; this comparison isolates gate changes, not a newly trained deployment-matched policy.',
            'Three optimization/noise pairs and known geometry/condition families are descriptive evidence, not independent-domain generalization or statistical proof. Mean episode penalized RMSE fills failed unexecuted tails with 2.5 m; failed cases remain in denominators. Severe 100 ms equality is fallback, not an AI win.',
            'The regional 5% target and overall 5% reduction are reported separately from gate-progress/learning-benefit eligibility. Undefined reductions against a zero reference are stored as null and cannot pass a gain threshold. A lower predictor cost or changed gate alone does not establish learning-specific benefit, real-vehicle safety, stability, native timing or superiority to published controllers.']
    (run/'report.md').write_text('\n'.join(lines)+'\n')
    (run/'selection.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    verification=dict(verified=True,episodes=len(rows),unique_paired_grid=True,physical_bounds=True,failure_penalties=True,
                      severe_trajectory_and_score_exact=True,archived_source_digests=True,archived_protocol_matches=True,submission_semantics=complete['submission_semantics'],
                      source_commit=complete['source_commit'],additional_rl_steps_run=0,reserved_opened=False)
    (run/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True)
    args=parser.parse_args();result=write_report(args.run)
    print(json.dumps({k:result[k] for k in ('selected_gate','next_action','additional_rl_steps_run','reserved_opened')},indent=2))
