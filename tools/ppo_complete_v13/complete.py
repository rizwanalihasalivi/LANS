"""Frozen actual-runtime and representative native transfer campaigns.

No cases, policies, simulation or external process are opened at import. Execute
only after both registered Python cohorts and all training controls finish.
"""
from contextlib import contextmanager
from pathlib import Path
import argparse
import fcntl
import json
import math
import os
import shutil
import traceback

import numpy as np

from . import evaluate, native, runtime
from .headroom import write
from .learning import ROOT, DATA, CONTRACT, HORIZON
from .train import CONTROLLER_KWARGS, SEEDS

ROLES = (('lqr', 0), ('adaptive', 0), *(('ppo', seed) for seed in SEEDS))
RUNTIME_IDS = tuple(2*i for i in range(36))
NATIVE_IDS = tuple(s*36 + v*12 + ((s+v) % 3)*4 + m*2
                   for s in range(4) for v in range(3) for m in range(2))
BOOTSTRAP_SEEDS = dict(runtime=2134155, native=2134156)


def read(path):
    return json.loads(Path(path).read_text())


def fresh_write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def active_training():
    """Detect this experiment's active Python training leader without logging args."""
    found = []
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            arguments = (process/'cmdline').read_bytes().split(b'\0')
        except (OSError, PermissionError):
            continue
        if not arguments or not Path(os.fsdecode(arguments[0])).name.startswith('python'):
            continue
        marker = b'tools.ppo_complete_v13.train'
        if marker in arguments and any(a in (b'learn', b'continued') for a in arguments):
            found.append(int(process.name))
    return found


@contextmanager
def mission_lock():
    """Do not overlap two observed timing/transfer campaigns in this checkout."""
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA/'.completion-owner.lock').open('a+') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('another completion runtime/native campaign owns the host slot') from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def select_cases(cases, kind):
    ids = RUNTIME_IDS if kind == 'runtime' else NATIVE_IDS
    assert kind in BOOTSTRAP_SEEDS
    expected_count = 72 if kind == 'runtime' else 144
    by_id = {case['id']: case for case in cases}
    assert len(cases) == len(by_id) == expected_count
    selected = [dict(by_id[i]) for i in ids]
    if kind == 'runtime':
        assert all(c['mirror'] == -1 and c['replica'] == 0 for c in selected)
        assert {(c['scenario'], c['speed'], c['delay']) for c in selected} == set(evaluate.STRATA)
    else:
        for index, case in enumerate(selected):
            scenario, rest = divmod(index, 6)
            speed, mirror = divmod(rest, 2)
            assert case['scenario'] == ('following', 'merge', 'crossing', 'curved')[scenario]
            assert case['speed'] == (8., 12., 16.)[speed]
            assert case['delay'] == (0., .05, .1)[(scenario+speed) % 3]
            assert case['mirror'] == (-1, 1)[mirror] and case['replica'] == 0
    return selected


def frozen_inputs():
    assert not active_training(), 'formal observed timing cannot overlap V13 learning'
    policies = evaluate.frozen_policies()
    inputs = {}
    stages = {}
    for stage, expected in (('validation', 864), ('final', 1728)):
        folder = DATA/stage
        protocol = evaluate.verify_protocol(folder)
        assert protocol['policies'] == policies
        records, assessment = read(folder/'summary.json'), read(folder/'assessment.json')
        assert len(records) == expected and assessment['episodes'] == expected
        assert assessment == evaluate.assess(records, protocol['bootstrap_seed'])
        for filename in ('protocol.json', 'summary.json', 'assessment.json'):
            path = folder/filename
            inputs[str(path.relative_to(ROOT))] = runtime.sha(path)
        stages[stage] = dict(cases=protocol['cases'], assessment=assessment)
    return dict(policies=policies, input_hashes=inputs, python_stages=stages,
                training_leader_processes_observed=[])


def source_snapshot(out):
    files = [*Path(__file__).parent.glob('*.py'), *Path(__file__).parent.glob('*.md'),
             *Path(__file__).parent.joinpath('native_assets').glob('*.py'),
             *ROOT.joinpath('integrations/unified_lans').glob('*.py')]
    files += [ROOT/name for name in (
        'tools/unified_control_v9/learning.py', 'tools/unified_control_v9/native_adapter.py',
        'tools/ppo_benefit_v10/core.py', 'tools/unified_campaign/study.py',
        'models/bicycle_model.py', 'controllers/lqr_controller.py',
        'integrations/webots/worlds/publication_v9.wbt',
        'integrations/webots/research/calibration.json',
        'integrations/webots/runtime-sha256.txt', 'tools/cloud/run-webots.sh',
    )]
    for version in range(4, 9):
        files += list(ROOT.joinpath(f'tools/unified_control_v{version}').glob('*.py'))
    hashes = {}
    for path in sorted(set(files)):
        name = str(path.relative_to(ROOT))
        hashes[name] = runtime.sha(path)
        target = out/'source'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    return hashes


def check_freeze(protocol, out):
    assert not active_training(), 'V13 learning appeared during formal completion'
    for name, digest in protocol['source_hashes'].items():
        assert runtime.sha(ROOT/name) == runtime.sha(out/'source'/name) == digest, ('completion executable changed', name)
    for name, digest in protocol['input_hashes'].items():
        assert runtime.sha(ROOT/name) == digest, ('frozen Python input changed', name)
    for record in protocol['policies'].values():
        assert runtime.sha(ROOT/record['path']) == record['sha256']
        assert runtime.sha(ROOT/record['manifest_path']) == record['manifest_sha256']


def prepare(kind):
    assert kind in BOOTSTRAP_SEEDS
    inputs = frozen_inputs()
    output = DATA/'completion'/kind
    assert not output.exists(), ('refusing to overwrite measured campaign', output)
    python_stage = 'validation' if kind == 'runtime' else 'final'
    cases = select_cases(inputs['python_stages'][python_stage]['cases'], kind)
    python_gates = {stage: dict(
        numerical_qualification_passed=record['assessment']['numerical_qualification_passed'],
        inferential_at_least_10_passed=record['assessment']['inferential_at_least_10_passed'])
        for stage, record in inputs['python_stages'].items()}
    python_passed = all(r['numerical_qualification_passed'] and r['inferential_at_least_10_passed']
                        for r in python_gates.values())
    calibration = None
    if kind == 'native':
        from .verify_calibration import verify
        folder = DATA/'native-actuator-calibration-v3'
        calibration = verify(folder)
        assert calibration['verified'] and calibration['all_initial_speeds_settled']
        for filename in ('protocol.json', 'summary.json', 'verification.json'):
            path = folder/filename
            inputs['input_hashes'][str(path.relative_to(ROOT))] = runtime.sha(path)
    output.mkdir(parents=True, exist_ok=False)
    protocol = dict(
        kind=kind, contract=CONTRACT, cases=cases, roles=ROLES,
        expected_episodes=len(cases)*5, expected_owner_slots=len(cases)*5*120,
        expected_native_physics_steps=len(cases)*5*6000 if kind == 'native' else 0,
        source_hashes=source_snapshot(output), input_hashes=inputs['input_hashes'],
        policies=inputs['policies'], python_gates=python_gates,
        controller_kwargs=CONTROLLER_KWARGS, bootstrap_seed=BOOTSTRAP_SEEDS[kind], bootstrap_draws=5000,
        role='frozen_policy_transfer_after_python_gates' if python_passed else 'frozen_policy_transfer_diagnostic_after_python_gate_failure',
        scope='Observed host timing on36 validation fixtures' if kind == 'runtime' else 'Representative physical transfer on24 prespecified final fixtures; not all144 final cases',
        policy_free_actuator_calibration=calibration,
        policy_free_scene_calibration_per_case=kind == 'native',
        no_case_or_policy_selection=True, no_training_or_campaign_overlap=True,
        no_favorable_timing_reruns=True, all_failures_retained=True,
    )
    fresh_write(output/'protocol.json', protocol)
    return output, protocol


def _runtime_records(folder, cases, mode, seed):
    summary = read(folder/'summary.json')
    verification = runtime.verify_profile(folder)
    assert verification['passed'] and len(summary['records']) == len(cases)
    records = []
    # Use the verifier's separate elementary geometry on recorded Python poses;
    # this does not make any native-physics or Python re-execution claim.
    from .verify_native import pose_metrics
    for index, (case, claimed) in enumerate(zip(cases, summary['records'])):
        path = folder/f'case-{index:03d}.jsonl'
        assert claimed['case'] == case and claimed['mode'] == mode
        assert runtime.sha(path) == claimed['raw_sha256']
        rows = [json.loads(line) for line in path.open()]
        n = len(rows)
        assert 1 <= n <= HORIZON and n == claimed['ticks'] and claimed['expected_ticks'] == HORIZON
        geometry = dict(case, route_kind='sine' if case['scenario']=='curved' else ('lane_change' if case['scenario']=='merge' else 'straight'),
                        initial_npcs=rows[0]['npc_truth'])
        for tick, row in enumerate(rows):
            assert row['tick'] == tick and row['case'] == case
            metrics = pose_metrics(geometry, row['state_after'], row['npc_truth'])
            assert abs(metrics['error']-row['error']) < 1e-9
            assert abs(metrics['heading_error']-row['heading_error']) < 1e-9
            assert metrics['collision'] == row['collision'] and metrics['corridor'] == row['corridor_exceeded']
            if tick < n-1:
                assert not row['collision'] and not row['corridor_exceeded']
        failed = n < HORIZON or any(r['collision'] or r['corridor_exceeded'] for r in rows)
        if n < HORIZON:
            assert rows[-1]['collision'] or rows[-1]['corridor_exceeded']
        assert bool(claimed['failed']) == failed
        record = dict(
            case=case, mode=mode, seed=seed, ticks=n, expected_ticks=HORIZON,
            rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(HORIZON-n)*6.25)/HORIZON),
            heading_rms=math.sqrt(np.mean([r['heading_error']**2 for r in rows])),
            rate_rms=math.sqrt(np.mean([r['steering_rate']**2 for r in rows])),
            progress_m=float(rows[-1]['state_after'][0]), failed=failed,
            collisions=sum(bool(r['collision']) for r in rows),
            corridor_failures=sum(bool(r['corridor_exceeded']) for r in rows),
            owner_response_misses=sum(bool(r['owner_response_miss']) for r in rows),
            scheduled_response_misses=sum(bool(r['scheduled_owner_response_miss']) for r in rows),
            policy_worker_failures=sum(bool(r['policy_worker_failed']) for r in rows),
            policy_reply_count=sum(r['runtime_reply'] is not None for r in rows),
            selected_ticks=sum(bool(r['runtime_selected']) for r in rows),
            owner_max_ms=max(r['complete_decision_ms'] for r in rows),
            raw_path=str(path.relative_to(ROOT)), raw_sha256=runtime.sha(path),
            verification_path=str((folder/'verification.json').relative_to(ROOT)),
            verification_sha256=runtime.sha(folder/'verification.json'),
            raw_physics_steps=0, rate_basis='Applied Python vehicle control at50ms',
        )
        assert record['owner_response_misses'] == claimed['response_misses']
        assert record['scheduled_response_misses'] == claimed['scheduled_response_misses']
        records.append(record)
    return records


def _native_record(folder, case, mode, seed):
    from .verify_native import verify
    verification = verify(folder)
    assert verification['verified']
    assert verification['scene_calibration']['verified'], 'final transfer requires the common policy-free initial-scene calibration'
    summary = read(folder/'summary.json')
    assert all(summary['case'][key] == value for key, value in case.items())
    assert summary['case']['mode'] == mode
    fresh_write(folder/'independent-verification.json', verification)
    rows = [json.loads(line) for line in (folder/'ticks.jsonl').open()]
    record = dict(case=case, mode=mode, seed=seed, expected_ticks=HORIZON,
        **{key: verification[key] for key in (
            'ticks', 'rmse_m', 'heading_rms', 'rate_rms', 'commanded_rate_rms', 'progress_m',
            'failed', 'collisions', 'corridor_failures', 'owner_response_misses',
            'scheduled_response_misses', 'owner_max_ms', 'raw_physics_steps', 'initial_state_fidelity', 'scene_calibration')},
        policy_worker_failures=sum(bool(r['policy_worker_failed']) for r in rows),
        policy_reply_count=sum(r['runtime_reply'] is not None for r in rows),
        selected_ticks=verification['policy_selected_ticks'],
        raw_path=str((folder/'ticks.jsonl').relative_to(ROOT)),raw_sha256=verification['raw_sha256'],
        verification_path=str((folder/'independent-verification.json').relative_to(ROOT)),
        verification_sha256=runtime.sha(folder/'independent-verification.json'),
        world_sha256=read(folder/'protocol.json')['world_sha256'],
        rate_basis='Physically realized equivalent-bicycle steering derivative at1ms',
    )
    return record


def ratio(numerator, denominator):
    return numerator/denominator if denominator > 0 else (1. if numerator == 0 else None)


def assess_stage(records, protocol, errors=()):
    kind, cases = protocol['kind'], protocol['cases']
    lookup = {(r['case']['id'], r['mode'], r['seed']): r for r in records}
    expected = {(c['id'], mode, seed) for c in cases for mode, seed in ROLES}
    assert len(lookup) == len(records) and set(lookup) <= expected
    if errors or set(lookup) != expected:
        return dict(complete=False, episodes=len(records), expected_episodes=len(expected),
            execution_errors=len(errors), missing_roles=sorted(expected-set(lookup)),
            reasons=['incomplete_or_invalid_measured_campaign'],
            mean_target_qualified=False, inferential_target_qualified=False, overall_qualified=False)
    for case in cases:
        for mode, seed in ROLES:
            record = lookup[(case['id'], mode, seed)]
            assert record['case'] == case and record['expected_ticks'] == HORIZON
            assert 1 <= record['ticks'] <= HORIZON
            assert record['failed'] == (record['ticks'] < HORIZON or record['collisions'] > 0 or record['corridor_failures'] > 0)
            assert np.isfinite([record[k] for k in ('rmse_m','heading_rms','rate_rms','progress_m')]).all()
    metrics = {mode: {key: float(np.mean([r[key] for r in records if r['mode'] == mode]))
                     for key in ('rmse_m','heading_rms','rate_rms','progress_m')}
               for mode in ('lqr','adaptive','ppo')}
    groups = {}
    for case in cases:
        groups.setdefault((case['scenario'],case['speed'],case['delay']), []).append(case['id'])
    count = 36 if kind == 'runtime' else 12
    assert len(groups) == count
    draw = np.random.default_rng(protocol['bootstrap_seed']).integers(count, size=(5000,count))
    comparisons = {}
    for mode in ('lqr','adaptive'):
        pairs = np.asarray([
            [np.mean([lookup[(i,mode,0)]['rmse_m'] for i in ids]),
             np.mean([lookup[(i,'ppo',s)]['rmse_m'] for i in ids for s in SEEDS])]
            for _, ids in sorted(groups.items())])
        assert np.all(pairs[:,0] > 0)
        average = pairs.mean(axis=0);sample = pairs[draw].mean(axis=1)
        comparisons[mode] = dict(gain_percent=float(100*(1-average[1]/average[0])),
            ci95_percent=np.quantile(100*(1-sample[:,1]/sample[:,0]),[.025,.975]).tolist(),
            clusters=count, bootstrap_draws=5000, bootstrap_seed=protocol['bootstrap_seed'],
            conditional_on_fixed_policies_and_selected_cases=True)
    reasons = []
    actors = {}
    base = [lookup[(c['id'],'lqr',0)] for c in cases]
    for seed in SEEDS:
        rows = [lookup[(c['id'],'ppo',seed)] for c in cases]
        heading = float(np.mean([r['heading_rms'] for r in rows]))
        rate = float(np.mean([r['rate_rms'] for r in rows]))
        heading_base = float(np.mean([r['heading_rms'] for r in base]))
        rate_base = float(np.mean([r['rate_rms'] for r in base]))
        safety = not any(r['failed'] for r in rows)
        progress = all(b['progress_m'] > 0 and r['progress_m'] >= .99*b['progress_m'] for r,b in zip(rows,base))
        actors[str(seed)] = dict(
            mean_rmse_m=float(np.mean([r['rmse_m'] for r in rows])),
            failures=sum(bool(r['failed']) for r in rows),
            heading_ratio_to_lqr=ratio(heading,heading_base), rate_ratio_to_lqr=ratio(rate,rate_base),
            minimum_progress_ratio_to_lqr=min((r['progress_m']/b['progress_m'] if b['progress_m']>0 else 0.) for r,b in zip(rows,base)),
            selected_ticks=sum(r['selected_ticks'] for r in rows),
            policy_reply_count=sum(r['policy_reply_count'] for r in rows),
            safety_passed=safety,progress_passed=progress,
            heading_passed=heading<=1.1*heading_base,rate_passed=rate<=1.1*rate_base,
        )
        for key in ('safety','progress','heading','rate'):
            if not actors[str(seed)][key+'_passed']:
                reasons.append(f'actor_{seed}_{key}')
        if actors[str(seed)]['policy_reply_count'] == 0:
            reasons.append(f'actor_{seed}_no_recorded_policy_reply')
    slots = sum(r['ticks'] for r in records)
    owner_misses = sum(r['owner_response_misses'] for r in records)
    scheduled_misses = sum(r['scheduled_response_misses'] for r in records)
    worker_failures = sum(r['policy_worker_failures'] for r in records)
    physics = sum(r['raw_physics_steps'] for r in records)
    timing = slots == protocol['expected_owner_slots'] and owner_misses == scheduled_misses == worker_failures == 0
    native_samples = kind != 'native' or physics == protocol['expected_native_physics_steps']
    if not timing:reasons.append('actual_owner_or_scheduled_timing')
    if not native_samples:reasons.append('native_physical_sample_count')
    if any(r['failed'] for r in records if r['mode'] != 'ppo'):
        reasons.append('shared_reference_safety')
    initial_fidelity = kind != 'native' or all(r['initial_state_fidelity']['all_initial_speeds_within_01_m_s'] for r in records)
    if not initial_fidelity:reasons.append('native_initial_speed_fidelity')
    if kind == 'native':
        for case in cases:
            assert len({lookup[(case['id'],mode,seed)]['world_sha256'] for mode,seed in ROLES}) == 1, 'matched native physical worlds differ'
            assert len({lookup[(case['id'],mode,seed)]['scene_calibration']['scene_state_sha256'] for mode,seed in ROLES}) == 1, 'matched native scene calibration differs'
    mean_target = comparisons['adaptive']['gain_percent'] >= 10.
    lower_target = comparisons['adaptive']['ci95_percent'][0] >= 10.
    if not mean_target:reasons.append('requested_10_mean_gain')
    for mode in ('lqr','adaptive'):
        if comparisons[mode]['ci95_percent'][0] <= 0:
            reasons.append('confidence_'+mode)
    return dict(complete=True,episodes=len(records),cases=len(cases),metrics=metrics,
        comparisons=comparisons,actors=actors,reasons=reasons,
        expected_owner_slots=protocol['expected_owner_slots'],observed_owner_slots=slots,
        expected_native_physics_steps=protocol['expected_native_physics_steps'],observed_native_physics_steps=physics,
        owner_response_misses=owner_misses,scheduled_response_misses=scheduled_misses,policy_worker_failures=worker_failures,
        timing_passed=timing,native_physical_sample_count_passed=native_samples,initial_speed_fidelity_passed=initial_fidelity,
        mean_gain_at_least_10=mean_target,ci_lower_at_least_10=lower_target,
        mean_target_qualified=not reasons,inferential_target_qualified=not reasons and lower_target,
        failures={mode:sum(bool(r['failed']) for r in records if r['mode']==mode) for mode in ('lqr','adaptive','ppo')},
        scope=protocol['scope'],role=protocol['role'],overall_qualified=False)


def _journal(output, record):
    with (output/'journal.jsonl').open('a') as stream:
        stream.write(json.dumps(record,allow_nan=False)+'\n');stream.flush()


def run(kind):
    with mission_lock():
        output, protocol = prepare(kind)
        records, errors = [], []
        jobs = [(None,mode,seed) for mode,seed in ROLES] if kind=='runtime' else [
            (case,mode,seed) for case in protocol['cases'] for mode,seed in ROLES]
        for index,(case,mode,seed) in enumerate(jobs):
            name = f'{mode}-{seed}' if case is None else f'{case["id"]:03d}-{mode}-{seed}'
            folder = output/name
            try:
                check_freeze(protocol,output)
                policy = None if mode!='ppo' else (ROOT/protocol['policies'][f'ppo-{seed}']['path']).parent
                if kind=='runtime':
                    runtime.profile(protocol['cases'],folder,policy=policy,mode=mode,
                        controller_kwargs=CONTROLLER_KWARGS,steps=HORIZON,role=protocol['role'])
                    completed = _runtime_records(folder,protocol['cases'],mode,seed)
                else:
                    native.episode(folder,case,mode,policy,protocol['role'],
                        scene_calibration=output/'scene-calibrations'/f'case-{case["id"]:03d}')
                    completed = [_native_record(folder,case,mode,seed)]
                records.extend(completed)
                _journal(output,dict(unit=name,verified=True,records=completed))
                print('V13',kind,index+1,'/',len(jobs),'verified episodes',len(records),flush=True)
            except Exception as exc:
                error = dict(unit=name,error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc())
                errors.append(error);_journal(output,dict(verified=False,**error))
                print('V13',kind,'RETAINED EXECUTION ERROR',name,error['error_type'],error['error'],flush=True)
        check_freeze(protocol,output)
        records.sort(key=lambda r:(r['case']['id'],r['mode'],r['seed']))
        assessment = assess_stage(records,protocol,errors)
        summary = dict(protocol_sha256=runtime.sha(output/'protocol.json'),records=records,execution_errors=errors,
                       assessment=assessment,overall_qualified=False)
        fresh_write(output/'summary.json',summary)
        fresh_write(output/'assessment.json',assessment)
        if errors:
            raise RuntimeError(f'{len(errors)} retained {kind} execution errors; campaign incomplete')
        return assessment


def assess():
    inputs = frozen_inputs()
    stages = {}
    hashes = {}
    for kind in ('runtime','native'):
        folder = DATA/'completion'/kind
        protocol,summary = read(folder/'protocol.json'),read(folder/'summary.json')
        check_freeze(protocol,folder)
        assert summary['protocol_sha256'] == runtime.sha(folder/'protocol.json')
        assert protocol['policies'] == inputs['policies']
        for record in summary['records']:
            assert runtime.sha(ROOT/record['raw_path']) == record['raw_sha256']
            assert runtime.sha(ROOT/record['verification_path']) == record['verification_sha256']
        stage = assess_stage(summary['records'],protocol,summary['execution_errors'])
        assert stage == summary['assessment'] == read(folder/'assessment.json')
        stages[kind] = stage
        for filename in ('protocol.json','summary.json','assessment.json','journal.jsonl'):
            hashes[f'{kind}/{filename}'] = runtime.sha(folder/filename)
    python_mean = all(s['assessment']['numerical_qualification_passed'] for s in inputs['python_stages'].values())
    python_inferential = all(s['assessment']['inferential_at_least_10_passed'] for s in inputs['python_stages'].values())
    mean = python_mean and all(s['mean_target_qualified'] for s in stages.values())
    inferential = python_inferential and all(s['inferential_target_qualified'] for s in stages.values())
    result = dict(python_numerical_gates_passed=python_mean,python_inferential_gates_passed=python_inferential,
        measured_stages=stages,input_hashes=inputs['input_hashes'],campaign_hashes=hashes,
        overall_mean_target_qualified=mean,overall_inferential_at_least_10_qualified=inferential,
        overall_qualified=inferential,
        scope='Full registered Python cohorts plus observed runtime and24-case representative native transfer; not all144 cases in Webots or a WCET certificate.')
    fresh_write(DATA/'completion/qualification.json',result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('runtime','native','assess'))
    args = parser.parse_args()
    result = assess() if args.stage=='assess' else run(args.stage)
    print(json.dumps(result,indent=2,allow_nan=False),flush=True)


if __name__=='__main__':
    main()
