"""Conditional private-Webots confirmation of a frozen nonlearned balanced gate.

No learned worker is present. Constant proposals use the same simulation-time
availability contract as the surrogate; these runs do not measure IPC deadlines.
"""
import argparse
import concurrent.futures
import csv
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import shutil
from statistics import mean
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPO = ROOT.parents[1]
RESEARCH = ROOT / 'research'
sys.path.insert(0, str(RESEARCH))
from native_process import run_native
P = json.loads((HERE / 'protocol.json').read_text())

NATIVE_PROTOCOL = {
    'purpose': 'Conditional physical-simulator confirmation of a selected nonlearned balanced gate',
    'repetitions': [0, 1], 'speeds': [20, 25], 'signs': [1, -1],
    'regions': ['nominal', 'contact_mismatch', 'latency100'],
    'methods': ['lqr', 'selected'], 'cases': 48,
    'noise_base': 1430000000,
    'noise_formula': 'base+repetition*10000+speed*100+region_index; mirror first three noise channels, not the fixed proposal',
    'physics_step_s': .001, 'control_period_s': .01, 'warmup_s': 10.,
    'path': 'DLC220 and its left/right reflection; no new road shape in native confirmation',
    'duration': '220/speed+2 seconds after physical acceleration warmup',
    'parallel_jobs': 2, 'case_timeout_s': 360,
    'contact_mismatch': 'Calibrated native force-dependent slip divided by0.65; not measured Fiala stiffness',
    'availability': 'Known constant generated on every available worker tick; simulated0/100ms service delay, no real inference process',
    'initial_condition': 'Physical settling, no teleport; approximatelyzero lateral offset instead of surrogate mirrored±0.15m',
    'input': 'Common noisy estimate and measured-speed LQR, current map curvature, mean front-wheel angle proxy; no hidden contact changes enter gate',
    'acceptance': 'All48 cases and24 matched pairs retained. Require all paired survivors, verified command/commanded-actuator bounds, exact severe-delay control/physical fallback, overall lateral reduction>=1%, nominal lateral RMSE<=LQR, overall heading RMSE<=1.05LQR, actual mean-front-wheel rate RMS and TV<=1.15LQR. Equal weight per episode; no native selection or retuning. Passing permits only the frozen teacher-headroom diagnostic, not training directly.',
    'confirmation_budgets': {'min_overall_lateral_reduction_percent': 1.,
        'max_nominal_lateral_ratio_lqr': 1., 'max_overall_heading_ratio_lqr': 1.05,
        'max_overall_measured_wheel_rate_ratio_lqr': 1.15,
        'max_overall_measured_wheel_tv_ratio_lqr': 1.15},
    'metric_contract': 'Smoothness acceptance uses measured_wheel_rate_rms_rad_s and measured_wheel_total_variation_rad from actual mean-front-wheel sensor increments including the first delta from the post-warmup measured angle. The separate actuator_rate_rms_rad_s/actuator_total_variation_rad describe the commanded first-order actuator model and do not replace the measured metrics. The commanded model enforces angle/rate bounds; actual wheel maxima are reported, without treating servo numerical overshoot as exactly identical to the command.',
    'limits': 'Calibrated native contact is not Fiala; explicitEuler1ms actuator differs from surrogateRK4; no real-time/safety/stability claim',
}

SOURCES = [
    'research/revision13/native13.py', 'research/revision13/native_controller13.py',
    'research/revision13/test_native13.py', 'research/revision13/protocol.json', 'research/revision13/gate13.py',
    'research/revision13/dynamics13.py', 'research/revision12/gate12.py',
    'research/revision8/bootstrap.py', 'research/revision7/kernels.py',
    'research/revision2/gating.py', 'research/revision2/plant.py',
    'research/core.py', 'research/protocol.json', 'research/comparison.py',
    'research/comparison-protocol.json', 'research/calibration.json',
    'research/native_process.py', 'worlds/research_validation.wbt', 'run-gated-webots.sh',
]
GATE_NAMES = {2: 'balanced_light', 3: 'balanced_medium', 4: 'balanced_strong'}
PHYSICAL_FIELDS = (
    't_command_s', 't_state_s', 'command_rad', 'actuator_rad',
    'measured_center_angle_rad', 'speed_truth_m_s', 'x_cg_m', 'y_cg_m',
    'heading_rad', 'vy_truth_m_s', 'yaw_rate_rad_s', 'error_m',
    'heading_error_rad', 'estimated_error_m', 'estimated_vy_m_s', 'lqr_command_rad',
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def candidate_name(candidate):
    require(isinstance(candidate, dict) and set(candidate) == {'variant', 'residual_rad'},
            'selected candidate must contain only variant and residual_rad')
    require(type(candidate['variant']) is int and candidate['variant'] in GATE_NAMES,
            'native candidate must be one of the three balanced gates')
    require(candidate['residual_rad'] in (-.04, .04), 'native candidate must be a frozen nonlearned constant')
    return GATE_NAMES[candidate['variant']] + ('_fixed_m004' if candidate['residual_rad'] < 0 else '_fixed_p004')


def validate_stage_proofs(data, proofs):
    """Check stage identity and actual eligibility, not authorization booleans alone."""
    selected = data['selected']
    name = candidate_name(selected)
    for label, phase in (('development_selection', 'development'), ('reserved_verification', 'reserved')):
        proof = proofs[label]
        require(proof.get('native_candidate') == selected, label+' candidate mismatch')
        require(proof.get('selected_candidate') == name, label+' selected method mismatch')
        require(proof.get('phase') == phase, label+' phase mismatch')
        require(proof.get('protocol') == P, label+' protocol mismatch')
    development = proofs['development_selection']
    require(development.get('assessments', {}).get(name, {}).get('eligible') is True,
            'development selected candidate is not eligible')
    reserved = proofs['reserved_verification']
    require(reserved.get('verified') is True, 'reserved proof is not verified')
    require(reserved.get('confirmed') is True, 'reserved confirmation did not pass')
    require(reserved.get('selection_sha256') == data['development_selection_sha256'],
            'reserved proof does not confirm this development selection')


def validate_selection(path, *, verify_checkout=True):
    """Fail closed before generating worlds when either prior stage did not pass."""
    path = Path(path).resolve()
    data = json.loads(path.read_text())
    for key in ('native_authorized', 'development_pass', 'reserved_confirmation_pass'):
        require(data.get(key) is True, 'native stage requires explicit passing '+key)
    selected = data.get('selected')
    candidate_name(selected)
    commit = data.get('source_commit', '')
    require(re.fullmatch(r'[0-9a-f]{40}', commit) is not None, 'full executable freeze commit required')
    proofs = {}
    for label in ('development_selection', 'reserved_verification'):
        proof_path = Path(data.get(label+'_path', ''))
        if not proof_path.is_absolute():
            proof_path = path.parent / proof_path
        proof_path = proof_path.resolve()
        require(proof_path.is_file(), 'missing '+label+' proof')
        require(sha(proof_path) == data.get(label+'_sha256'), 'changed '+label+' proof')
        proof = json.loads(proof_path.read_text())
        proofs[label] = (proof_path, proof)
    validate_stage_proofs(data, {label: content for label, (_, content) in proofs.items()})
    hashes = data.get('source_sha256', {})
    required = ('revision13/gate13.py', 'revision13/dynamics13.py')
    require(all(re.fullmatch(r'[0-9a-f]{64}', str(hashes.get(name, ''))) for name in required),
            'frozen gate and observation source hashes required')
    if verify_checkout:
        for name in required:
            source = RESEARCH / name
            require(sha(source) == hashes[name], 'selected source changed: '+name)
            archived = subprocess.check_output(['git', 'show', commit+':'+str(source.relative_to(REPO))], cwd=REPO)
            require(hashlib.sha256(archived).hexdigest() == hashes[name], 'source differs from selected executable freeze: '+name)
        for name in ('core.py','protocol.json','comparison.py','comparison-protocol.json',
                     'revision7/kernels.py','revision12/gate12.py','revision2/gating.py'):
            source=RESEARCH/name
            archived=subprocess.check_output(['git','show',commit+':'+str(source.relative_to(REPO))],cwd=REPO)
            require(hashlib.sha256(archived).hexdigest()==sha(source), 'shared control source changed after selection: '+name)
    return data, proofs


def cases(selected):
    candidate_name(selected)
    for rep, speed, sign, region, method in itertools.product(
            NATIVE_PROTOCOL['repetitions'], NATIVE_PROTOCOL['speeds'], NATIVE_PROTOCOL['signs'],
            NATIVE_PROTOCOL['regions'], NATIVE_PROTOCOL['methods']):
        case = dict(repetition=rep, speed=speed, path='dlc220', path_sign=sign,
                    scenario=region, mode=method, variant=selected['variant'],
                    residual_rad=selected['residual_rad'], noise=1., sensor_delay_steps=0,
                    mu=.9, contact_scale=.65 if region == 'contact_mismatch' else 1.,
                    service_ticks=10 if region == 'latency100' else 0,
                    seed=NATIVE_PROTOCOL['noise_base']+rep*10000+speed*100+NATIVE_PROTOCOL['regions'].index(region),
                    duration=220/speed+2)
        name=f'{region}-rep{rep}-v{speed}-sign{"p" if sign>0 else "m"}-{method}'
        yield name, case


def make_world(case, destination):
    """Generate only a new private project; never edit the shared/private install."""
    destination = Path(destination).resolve()
    project = ROOT / '.runtime/revision13-native-cases' / hashlib.sha256(str(destination).encode()).hexdigest()[:20]
    (project / 'worlds').mkdir(parents=True, exist_ok=False)
    controller = project / 'controllers/revision13_validation'
    controller.mkdir(parents=True)
    shutil.copyfile(HERE / 'native_controller13.py', controller / 'revision13_validation.py')
    calibration = json.loads((RESEARCH / 'calibration.json').read_text())
    case = dict(case, output=str(destination))
    for axle in ('front', 'rear'):
        case[axle+'_slip'] = 4*case['speed']/80000*calibration[axle+'_slip_multiplier']/case['contact_scale']
    world = (ROOT / 'worlds/research_validation.wbt').read_text()
    world = world.replace('../.runtime/protos', str(ROOT / '.runtime/protos'))
    world = world.replace('controller "research_validation"', 'controller "revision13_validation"')
    world = world.replace('coulombFriction [ 0.9 ]', f'coulombFriction [ {case["mu"]} ]')
    for axle in ('front', 'rear'):
        world = world.replace(f'forceDependentSlip [ 0 0 ] # {axle.upper()}_SLIP',
                              f'forceDependentSlip [ {case[axle+"_slip"]} 0 ]')
    world_path = project / 'worlds/test.wbt'
    world_path.write_text(world)
    (destination / 'generated-world.wbt').write_text(world)
    (destination / 'case.json').write_text(json.dumps(case, indent=2)+'\n')
    return world_path, case


def summarize_records(records, case, failure=None):
    require(bool(records), 'empty native trace')
    total = round(case['duration']/.01)
    count = len(records)
    require(0 < count <= total, 'invalid native trace length')
    rms = lambda key: math.sqrt(mean(row[key]**2 for row in records))
    return dict(
        case=case, steps=count, scheduled_steps=total, survived=failure is None,
        failure=failure, rmse_m=rms('error_m'), heading_rmse_rad=rms('heading_error_rad'),
        penalized_rmse_m=math.sqrt((sum(row['error_m']**2 for row in records)+(total-count)*6.25)/total),
        command_rms_rad=rms('command_rad'), actuator_rate_rms_rad_s=rms('actuator_rate_rad_s'),
        actuator_total_variation_rad=sum(abs(row['actuator_increment_rad']) for row in records),
        measured_wheel_rate_rms_rad_s=rms('measured_wheel_rate_rad_s'),
        measured_wheel_total_variation_rad=sum(abs(row['measured_wheel_increment_rad']) for row in records),
        active_fraction=mean(row['weight']>0 for row in records), mean_weight=mean(row['weight'] for row in records),
        max_abs_error_m=max(abs(row['error_m']) for row in records),
        max_abs_heading_error_rad=max(abs(row['heading_error_rad']) for row in records),
        max_command_rad=max(abs(row['command_rad']) for row in records),
        max_actuator_rad=max(abs(row['actuator_rad']) for row in records),
        max_actuator_rate_rad_s=max(abs(row['actuator_rate_rad_s']) for row in records),
        max_measured_wheel_rate_rad_s=max(abs(row['measured_wheel_rate_rad_s']) for row in records),
        max_packet_age_s=max(row['packet_age_s'] for row in records), final=records[-1])


def assess_native(rows, severe, *, bounds_verified):
    """Frozen confirmation budgets; a verified campaign can still fail promotion."""
    keys = ('repetition', 'speed', 'sign', 'scenario', 'method')
    expected = set(itertools.product(NATIVE_PROTOCOL['repetitions'], NATIVE_PROTOCOL['speeds'],
                                    NATIVE_PROTOCOL['signs'], NATIVE_PROTOCOL['regions'], NATIVE_PROTOCOL['methods']))
    identities = [tuple(row[key] for key in keys) for row in rows]
    require(len(identities) == len(expected) and set(identities) == expected,
            'native confirmation requires the complete unique paired grid')
    severe_keys = ('repetition', 'speed', 'sign')
    severe_expected = set(itertools.product(NATIVE_PROTOCOL['repetitions'], NATIVE_PROTOCOL['speeds'], NATIVE_PROTOCOL['signs']))
    severe_identities = [tuple(row[key] for key in severe_keys) for row in severe]
    require(len(severe_identities) == len(severe_expected) and set(severe_identities) == severe_expected,
            'native confirmation requires every severe-delay pair')
    metrics = ('penalized_rmse_m', 'heading_rmse_rad', 'measured_wheel_rate_rms_rad_s',
               'measured_wheel_total_variation_rad')
    require(all(math.isfinite(row[key]) and row[key] >= 0 for row in rows for key in metrics),
            'native confirmation metric must be finite and nonnegative')
    aggregate = {}
    for method in NATIVE_PROTOCOL['methods']:
        subset = [row for row in rows if row['method'] == method]
        aggregate[method] = {key: mean(row[key] for row in subset) for key in metrics}
        aggregate[method]['nominal_rmse_m'] = mean(row['penalized_rmse_m'] for row in subset if row['scenario'] == 'nominal')
    base, candidate = aggregate['lqr'], aggregate['selected']
    budgets = NATIVE_PROTOCOL['confirmation_budgets']
    reduction = 100*(1-candidate['penalized_rmse_m']/base['penalized_rmse_m']) if base['penalized_rmse_m'] else None
    checks = dict(
        complete_unique_paired_grid=True,
        all_paired_survivors=all(row['survived'] is True for row in rows),
        commanded_actuator_bounds_verified=bounds_verified is True,
        overall_lateral_reduction_at_least_1_percent=base['penalized_rmse_m'] > 0 and candidate['penalized_rmse_m'] <= base['penalized_rmse_m']*(1-budgets['min_overall_lateral_reduction_percent']/100),
        nominal_lateral_preserved=candidate['nominal_rmse_m'] <= base['nominal_rmse_m']*budgets['max_nominal_lateral_ratio_lqr'],
        overall_heading_budget=candidate['heading_rmse_rad'] <= base['heading_rmse_rad']*budgets['max_overall_heading_ratio_lqr'],
        actual_mean_wheel_rate_budget=candidate['measured_wheel_rate_rms_rad_s'] <= base['measured_wheel_rate_rms_rad_s']*budgets['max_overall_measured_wheel_rate_ratio_lqr'],
        actual_mean_wheel_tv_budget=candidate['measured_wheel_total_variation_rad'] <= base['measured_wheel_total_variation_rad']*budgets['max_overall_measured_wheel_tv_ratio_lqr'],
        severe_delay_exact_fallback=all(row['exact'] is True and row['same_length'] is True for row in severe))
    confirmed = all(checks.values())
    return dict(confirmed=confirmed, native_confirmation_checks=checks,
                native_confirmation_aggregates=aggregate, overall_lateral_reduction_percent=reduction,
                next_action='teacher_headroom_check' if confirmed else 'stop_after_native_confirmation',
                automatic_training_authorized=False)


def run_case(item, output, source_hashes):
    name, case = item
    destination = output / name
    destination.mkdir()
    world, case = make_world(case, destination)
    python = Path(os.environ.get('LANS_PYTHON', str(ROOT / '.runtime/research-venv/bin/python')))
    require(python.is_file(), 'private controller interpreter missing')
    env = os.environ.copy()
    env.update(LANS_INTEGRATION_ROOT=str(ROOT), LANS_CASE_CONFIG=str(destination / 'case.json'),
               PATH=str(python.parent)+':'+env['PATH'], OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
               NUMBA_CACHE_DIR=str(ROOT / '.runtime/numba'), MPLCONFIGDIR=str(ROOT / '.runtime/mpl'))
    started = time.time()
    with (destination / 'console.log').open('w') as log:
        run_native(['bash', str(ROOT / 'run-gated-webots.sh'), '--stdout', '--stderr', '--batch',
                    '--mode=fast', '--no-rendering', str(world)], env=env, stdout=log,
                   timeout=NATIVE_PROTOCOL['case_timeout_s'])
    metrics = json.loads((destination / 'metrics.json').read_text())
    require(metrics['case'] == case, 'native case/metrics mismatch')
    provenance = dict(started_unix_s=started, elapsed_wall_s=time.time()-started, python=str(python),
                      source_sha256=source_hashes,
                      artifacts={p.name: sha(p) for p in [destination/'case.json', destination/'metrics.json',
                                 destination/'vehicle.json', destination/'initial-state.json',
                                 destination/'telemetry.csv', destination/'generated-world.wbt']})
    (destination / 'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    print(name, metrics['survived'], metrics['penalized_rmse_m'], flush=True)
    return name, metrics


def verify_run(output):
    output = Path(output).resolve()
    start = json.loads((output / 'start.json').read_text())
    complete = json.loads((output / 'complete.json').read_text())
    require(start['protocol'] == NATIVE_PROTOCOL, 'native protocol mismatch')
    require(complete['source_sha256'] == start['source_sha256'], 'native source manifest mismatch')
    for name, digest in start['source_sha256'].items():
        require(sha(output/'source'/name) == digest, 'native archived source changed: '+name)
    for name,digest in start['eligibility_sha256'].items():
        require(sha(output/'eligibility'/name)==digest, 'native archived eligibility evidence changed: '+name)
    authorization=json.loads((output/'eligibility/native-authorization.json').read_text())
    require(authorization==start['selection'], 'native authorization differs from start record')
    archived_proofs = {}
    for label in ('development_selection','reserved_verification'):
        evidence=output/'eligibility'/f'{label}.json'
        require(sha(evidence)==authorization[label+'_sha256'], 'native eligibility proof hash mismatch')
        archived_proofs[label]=json.loads(evidence.read_text())
    validate_stage_proofs(authorization, archived_proofs)
    require(sha(output/'summary.json') == complete['summary_sha256'], 'native summary digest mismatch')
    summary = json.loads((output/'summary.json').read_text())
    expected = dict(cases(start['selection']['selected']))
    require(set(summary) == set(expected) and len(summary) == complete['cases'] == 48, 'native grid incomplete')
    traces = {}
    rows = []
    for name, metrics in summary.items():
        folder = output/name
        proof = json.loads((folder/'provenance.json').read_text())
        case = json.loads((folder/'case.json').read_text())
        require(all(case[key] == value for key, value in expected[name].items()), 'native grid case mismatch')
        require(case == metrics['case'], 'native case summary mismatch')
        require(proof['source_sha256'] == start['source_sha256'], 'native case source mismatch')
        for filename, digest in proof['artifacts'].items():
            require(sha(folder/filename) == digest, 'native artifact changed: '+filename)
        with (folder/'telemetry.csv').open() as handle:
            records = [{key: float(value) for key, value in raw.items()} for raw in csv.DictReader(handle)]
        require(bool(records), 'empty native telemetry')
        for i, row in enumerate(records):
            require(all(math.isfinite(v) for v in row.values()), 'nonfinite native telemetry')
            require(row['step'] == i+1 and abs(row['t_test_s']-i*.01)<1e-8, 'native step clock mismatch')
            require(abs(row['t_state_s']-row['t_command_s']-.01)<1e-8, 'native transition clock mismatch')
            require(abs(row['t_command_s']-records[0]['t_command_s']-i*.01)<1e-8, 'native elapsed clock mismatch')
            require(abs(row['command_rad'])<=.50000001 and abs(row['actuator_rad'])<=.50000001
                    and abs(row['actuator_rate_rad_s'])<=.35000001, 'native physical bound violation')
            require(abs(row['actuator_increment_rad']/.01-row['actuator_rate_rad_s'])<1e-12, 'native actuator increment mismatch')
            require(abs(row['measured_wheel_increment_rad']/.01-row['measured_wheel_rate_rad_s'])<1e-12, 'native wheel increment mismatch')
            require(0<=row['weight']<=.5, 'native fusion bound violation')
            if row['packet_available']:
                require(abs(row['t_test_s']-row['packet_observed_s']-row['packet_age_s'])<1e-8, 'native packet age mismatch')
            if row['weight']>0:
                require(row['packet_available']==1 and 0<=row['packet_age_s']<.05 and row['reason']==6,
                        'native stale/unearned authority')
            else:
                require(row['command_rad']==row['lqr_command_rad'], 'native fallback command mismatch')
        recomputed = summarize_records(records, case, metrics['failure'])
        failed_rows=[i for i,row in enumerate(records) if abs(row['error_m'])>2.5 or abs(row['heading_error_rad'])>.6]
        require((not failed_rows and metrics['failure'] is None)
                or (failed_rows==[len(records)-1] and metrics['failure']=='tracking_envelope'),
                'native failure flag differs from raw tracking envelope')
        require(recomputed['steps']==metrics['steps'] and recomputed['survived']==metrics['survived'], 'native count/survival mismatch')
        for key, value in recomputed.items():
            if isinstance(value, float):
                require(math.isclose(value, metrics[key], rel_tol=1e-11, abs_tol=1e-12), 'native raw metric mismatch: '+key)
        require(not metrics['survived'] or metrics['steps']==metrics['scheduled_steps'], 'native survivor incomplete')
        vehicle=json.loads((folder/'vehicle.json').read_text())
        require(abs(vehicle['mass_kg']-1650)<1e-8 and abs(vehicle['nominal_cg_x_m']-1.4)<1e-8
                and abs(vehicle['nominal_yaw_inertia']-4224)<1e-7, 'native vehicle audit mismatch')
        traces[name]=records
        rows.append(dict(name=name, repetition=case['repetition'], speed=case['speed'], sign=case['path_sign'],
                         scenario=case['scenario'], method=case['mode'],
                         **{k:metrics[k] for k in ('survived','steps','penalized_rmse_m','heading_rmse_rad',
                           'command_rms_rad','actuator_rate_rms_rad_s','actuator_total_variation_rad',
                           'measured_wheel_rate_rms_rad_s','measured_wheel_total_variation_rad','active_fraction')}))
    severe=[]
    for rep,speed,sign in itertools.product(NATIVE_PROTOCOL['repetitions'],NATIVE_PROTOCOL['speeds'],NATIVE_PROTOCOL['signs']):
        prefix=f'latency100-rep{rep}-v{speed}-sign{"p" if sign>0 else "m"}'
        baseline=traces[prefix+'-lqr'];selected=traces[prefix+'-selected']
        require(all(r['weight']==0 and r['command_rad']==r['lqr_command_rad'] for r in selected), 'native severe authority violation')
        differences={key:max(abs(a[key]-b[key]) for a,b in zip(baseline,selected)) for key in PHYSICAL_FIELDS}
        severe.append(dict(repetition=rep,speed=speed,sign=sign,same_length=len(baseline)==len(selected),
                           exact=len(baseline)==len(selected) and all(v==0 for v in differences.values()),
                           max_abs_differences=differences))
    with (output/'episodes.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    proof=dict(verified=True,cases=len(rows),survived=sum(r['survived'] for r in rows),severe_delay=severe,
               severe_exact=sum(r['exact'] for r in severe),no_native_retuning=True,
               no_learned_worker=True,hard_realtime_claim=False,
               **assess_native(rows, severe, bounds_verified=True))
    paired={}
    for region,sign in itertools.product(NATIVE_PROTOCOL['regions'],NATIVE_PROTOCOL['signs']):
        base=[r for r in rows if r['scenario']==region and r['sign']==sign and r['method']=='lqr']
        candidate=[r for r in rows if r['scenario']==region and r['sign']==sign and r['method']=='selected']
        score0=mean(r['penalized_rmse_m'] for r in base);score1=mean(r['penalized_rmse_m'] for r in candidate)
        paired[f'{region}/sign{sign}']=dict(lqr_mean_rmse_m=score0,selected_mean_rmse_m=score1,
            reduction_percent=100*(1-score1/score0) if score0 else None,
            survival_difference=sum(r['survived'] for r in candidate)-sum(r['survived'] for r in base),
            paired_cells=len(base))
    proof['paired_by_region_and_sign']=paired
    (output/'verification.json').write_text(json.dumps(proof,indent=2)+'\n')
    lines=['# Revision13 conditional native confirmation','',f'All {len(rows)} native cases are retained; {proof["survived"]}/{len(rows)} survive.',
           '', f'Frozen native confirmation passed: **{proof["confirmed"]}**. Next permitted step: `{proof["next_action"]}`. This does not authorize training directly.',
           '', '| Region | Method | Survival /8 | Lateral RMSE m | Heading RMSE rad | Command RMS rad | Actual mean-wheel rate RMS rad/s | Actual mean-wheel TV rad |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    for region,method in itertools.product(NATIVE_PROTOCOL['regions'],NATIVE_PROTOCOL['methods']):
        subset=[r for r in rows if r['scenario']==region and r['method']==method]
        lines.append(f'| {region} | {method} | {sum(r["survived"] for r in subset)} | '+
                     ' | '.join(f'{mean(r[key] for r in subset):.8f}' for key in ('penalized_rmse_m','heading_rmse_rad','command_rms_rad','measured_wheel_rate_rms_rad_s','measured_wheel_total_variation_rad'))+' |')
    lines += ['', 'Smoothness budgets use the actual mean front-wheel sensor increments, including the first delta from the post-warmup measured angle. The separate commanded actuator model rate/TV are retained in `episodes.csv` and every trace; its enforced angle/rate limits do not substitute for measured smoothness.',
              '', '| Frozen native check | Passed |', '|---|---|']
    lines += [f'| {key} | {value} |' for key, value in proof['native_confirmation_checks'].items()]
    lines += ['', '| Region / path sign | Paired cells | Reduction vs LQR | Survival difference |',
              '|---|---:|---:|---:|']
    for label,value in paired.items():
        relative=f'{value["reduction_percent"]:+.3f}%' if value['reduction_percent'] is not None else 'undefined'
        lines.append(f'| {label} | {value["paired_cells"]} | {relative} | {value["survival_difference"]:+d} |')
    lines += ['',f'Severe-delay paired physical/control equality: {proof["severe_exact"]}/8; all per-field differences are retained.',
              '', 'This evaluates only a frozen nonlearned proposal and gate on calibrated native DLC reflections. Contact softening is not measured Fiala stiffness; initial offsets and actuator integration differ from the surrogate. Known-constant service delay is simulated, not real inference/IPC timing. Passing every frozen check permits only the preregistered teacher-headroom diagnostic, whose separate criteria must pass before pilots. No native result changes selection, directly authorizes training, proves real-vehicle safety or establishes hard real-time performance.']
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    return proof


def run(selection_path, output):
    selection, proofs = validate_selection(selection_path)
    relative_sources=[str((ROOT/name).relative_to(REPO)) for name in SOURCES]
    subprocess.run(['git','ls-files','--error-unmatch','--',*relative_sources],cwd=REPO,stdout=subprocess.DEVNULL,check=True)
    subprocess.run(['git','diff','--exit-code','HEAD','--',*relative_sources],cwd=REPO,check=True)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    hashes={name:sha(ROOT/name) for name in SOURCES}
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    for name in SOURCES:
        target=output/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    (output/'eligibility').mkdir()
    shutil.copyfile(selection_path,output/'eligibility/native-authorization.json')
    for label,(path,_) in proofs.items():shutil.copyfile(path,output/'eligibility'/f'{label}.json')
    start=dict(protocol=NATIVE_PROTOCOL,source_commit=commit,source_sha256=hashes,selection=selection,
               eligibility_sha256={p.name:sha(p) for p in (output/'eligibility').iterdir()},
               private_runtime_proto_sha256={name:sha(ROOT/'.runtime/protos'/name) for name in ('Car.proto','VehicleWheel.proto')})
    (output/'start.json').write_text(json.dumps(start,indent=2)+'\n')
    with concurrent.futures.ThreadPoolExecutor(max_workers=NATIVE_PROTOCOL['parallel_jobs']) as pool:
        results=dict(pool.map(lambda item:run_case(item,output,hashes),cases(selection['selected'])))
    require(len(results)==NATIVE_PROTOCOL['cases'], 'native run grid incomplete')
    require(hashes=={name:sha(ROOT/name) for name in SOURCES},'native sources changed during campaign')
    require(start['private_runtime_proto_sha256']=={name:sha(ROOT/'.runtime/protos'/name) for name in ('Car.proto','VehicleWheel.proto')},
            'private vehicle PROTO changed during native campaign')
    (output/'summary.json').write_text(json.dumps(results,indent=2,sort_keys=True)+'\n')
    (output/'complete.json').write_text(json.dumps(dict(cases=len(results),source_sha256=hashes,
        summary_sha256=sha(output/'summary.json')),indent=2)+'\n')
    return verify_run(output)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    launch=sub.add_parser('run');launch.add_argument('--selection',type=Path,required=True);launch.add_argument('--output',type=Path,required=True)
    audit=sub.add_parser('verify');audit.add_argument('--run',type=Path,required=True)
    args=parser.parse_args()
    result=run(args.selection,args.output) if args.command=='run' else verify_run(args.run)
    print(json.dumps({k:result[k] for k in ('verified','cases','survived','severe_exact','confirmed','next_action')},indent=2))
