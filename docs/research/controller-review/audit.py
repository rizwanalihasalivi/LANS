"""Read-only controller audit; writes new evidence only to a new output directory.

Run from any directory with the repository's Python 3.10 research dependencies:
  python docs/research/controller-review/audit.py --output /workspace/lans-review/fresh
No training, source modification, or reserved revision3 test-noise use.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
from statistics import mean

import numpy as np
import torch
from stable_baselines3 import PPO

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = ROOT / 'integrations/webots/research'
RESULTS = RESEARCH.parent / 'results'
sys.path.insert(0, str(ROOT))


def read_csv(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(1)
    evidence = {'reviewed_head': subprocess.check_output(
        ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()}

    # Legacy reproduction: no PPO/checkpoint is needed to expose the plant bug.
    from envs.path_tracking_env import PathTrackingEnv
    from envs.residual_path_env import ResidualPathEnv
    from controllers.lans_controller import LANSController
    env = PathTrackingEnv(mode='eval')
    env.reset(seed=42)
    max_state = 0.
    for _ in range(700):
        _, _, terminated, truncated, _ = env.step(np.array([0.], dtype=np.float32))
        max_state = max(max_state, float(np.max(np.abs(env.state))))
        if terminated or truncated:
            break
    evidence['legacy_zero_action'] = dict(max_abs_state=max_state,
        reference_peak_m=float(np.max(env.y_ref)), simulated_x_m=env.x_position)
    assert max_state == 0 and np.max(env.y_ref) > 3

    env = ResidualPathEnv()
    env.target_speed = 15.
    env.reset(seed=42)
    env.state = np.array([.1, 0., .01, 0.])
    before = env.state.copy()
    baseline = float(-env.K @ before)
    # Fresh reset makes both latency weights exactly one.
    expected_actual = env.A_d @ before + env.B_d * (2 * baseline)
    expected_single = env.A_d @ before + env.B_d * baseline
    _, _, _, _, info = env.step(np.array([0.], dtype=np.float32))
    assert np.allclose(env.state, expected_actual, atol=1e-8)
    assert not np.allclose(env.state, expected_single)
    evidence['legacy_double_lqr'] = dict(single_lqr_rad=baseline,
        effective_plant_command_rad=2*baseline, reported_total_rad=float(info['total_steer']),
        single_lqr_state_error=float(np.max(np.abs(env.state-expected_single))),
        target_speed=env.target_speed, actual_dynamics_speed=env.vx,
        child_distance_m=env.car_x, parent_distance_m=env.x_position)
    controller = LANSController(vx=15., load_ppo_model=False)
    evidence['legacy_controller_speed'] = dict(requested=controller.vx,
        observation=float(controller.obs_builder.get_full_input()[4]))
    assert evidence['legacy_controller_speed']['observation'] == 25.

    # Stable-Baselines3 retains its initialized schedule if only this attribute changes.
    model = PPO('MlpPolicy', PathTrackingEnv(), n_steps=8, batch_size=8,
                learning_rate=3e-4, device='cpu', verbose=0)
    model.learning_rate = 1e-4
    evidence['legacy_lr_assignment'] = dict(attribute=model.learning_rate,
        effective_schedule=model.lr_schedule(1.))
    assert model.lr_schedule(1.) == 3e-4

    # Recompute published cell-level numbers and verify 600k source/model provenance.
    aggregate = []
    for name, filename, metric in [
        ('revision2-test', 'episodes.csv', 'penalized_rmse'),
        ('revision2-native-test', 'episodes.csv', 'penalized_rmse_m'),
        ('revision3-600k', 'development.csv', 'penalized_rmse')]:
        path = RESULTS / name / filename
        rows = read_csv(path)
        evidence[name] = dict(rows=len(rows), sha256=sha(path))
        assert len(rows) == {'revision2-test': 900, 'revision2-native-test': 270,
                             'revision3-600k': 288}[name]
        keys = [(r['seed'], r['speed'], r.get('path', 'dlc220'), r['scenario'], r['method']) for r in rows]
        assert len(keys) == len(set(keys))
        for region in sorted({r['scenario'] for r in rows}):
            baseline_rows = [r for r in rows if r['scenario'] == region and r['method'] == 'lqr']
            baseline = mean(float(r[metric]) for r in baseline_rows)
            for method in sorted({r['method'] for r in rows}):
                selected = [r for r in rows if r['scenario'] == region and r['method'] == method]
                score = mean(float(r[metric]) for r in selected)
                aggregate.append(dict(stage=name, region=region, method=method,
                    episodes=len(selected), survived=sum(r['survived'] == 'True' for r in selected),
                    mean_rmse_m=score, improvement_vs_lqr_pct=100*(baseline-score)/baseline,
                    active_pct=100*mean(float(r['active_fraction']) for r in selected),
                    mean_weight=mean(float(r['mean_weight']) for r in selected)))
    with (out/'aggregates.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=aggregate[0], lineterminator="\n"); writer.writeheader(); writer.writerows(aggregate)
    complete = json.loads((RESULTS/'revision3-600k/complete.json').read_text())
    assert sha(RESULTS/'revision3-600k/development.csv') == complete['development_sha256']
    for name, digest in complete['source_sha256'].items():
        assert sha(RESEARCH/name) == sha(RESULTS/'revision3-600k/source'/name) == digest
    old = read_csv(RESULTS/'revision3-extended/development.csv')
    key = lambda r: (r['seed'], r['speed'], r['path'], r['scenario'], r['method'])
    lookup = {key(r): r for r in old}
    reproduced = 0
    for r in read_csv(RESULTS/'revision3-600k/development.csv'):
        if r['method'] != 'baseline600':
            for field in ['rmse', 'penalized_rmse', 'survived', 'steps', 'scheduled_steps', 'noise_seed']:
                assert r[field] == lookup[key(r)][field]
            reproduced += 1
    assert reproduced == 216
    evidence['reference_cells_reproduced'] = reproduced
    for seed in (101, 202):
        folder = RESULTS/f'revision3-600k/baseline-{seed}'
        meta = json.loads((folder/'complete.json').read_text())
        assert sha(folder/'policy.zip') == meta['policy_sha256'] == complete['policy_sha256'][f'baseline-{seed}']
        model = PPO.load(folder/'policy.zip', device='cpu')
        assert model.num_timesteps == 600000 and model.seed == seed
        counters = sorted({int(v['step'].item()) for v in model.policy.optimizer.state_dict()['state'].values()})
        assert counters == [30000]
        evidence[f'model_{seed}'] = dict(steps=model.num_timesteps, optimizer_steps=counters,
                                        policy_sha256=meta['policy_sha256'])

    # Small controlled diagnostic on EXISTING DEVELOPMENT cells only. All five
    # candidates and both regions are reported; no parameter/policy selection.
    sys.path[:0] = [str(RESEARCH/'revision3'), str(RESEARCH/'revision2'), str(RESEARCH)]
    spec = importlib.util.spec_from_file_location('review_runner', RESEARCH/'revision2/run.py')
    runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
    from mapping import RangeMappedPolicy
    runner.configure_lqr()
    model = PPO.load(RESULTS/'revision3-600k/baseline-101/policy.zip', device='cpu')
    mapped = RangeMappedPolicy(model)
    class Constant:
        def __init__(self, value): self.value = value
        def predict(self, *args, **kwargs): return np.array([self.value]), None
    candidates = [('lqr', None, 'lqr'), ('600k_gated', mapped, 'gated_residual'),
                  ('600k_direct', mapped, 'residual'),
                  ('constant_plus_008_gated', Constant(.16), 'gated_residual'),
                  ('constant_minus_008_gated', Constant(-.16), 'gated_residual')]
    diagnostics = []
    config = json.loads((RESULTS/'revision2-development/freeze.json').read_text())['selected_config']
    for region in ('nominal', 'tire_mismatch'):
        for label, policy, method in candidates:
            row = runner.episode(policy, method, 101, 25, 'dlc220', region, config, 4100000, None)
            row['diagnostic'] = label
            diagnostics.append(row)
            print(region, label, row['penalized_rmse'], flush=True)
    with (out/'diagnostics.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=diagnostics[0], lineterminator="\n"); writer.writeheader(); writer.writerows(diagnostics)
    evidence['diagnostics_scope'] = '10 runs: seed101, 25m/s, DLC220, nominal/tire_mismatch, existing development noise4100000. Not a policy selection or reserved test.'
    evidence['reward_lateral_only'] = {str(e): math.exp(-(e/.5)**2)+.05 for e in (.06,.03,0.)}
    (out/'evidence.json').write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
