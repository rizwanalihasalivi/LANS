"""Evidence-based audit report, including failed endpoints and exact resume command."""
import boot12
import json
from checkpoint12 import atomic_json, digest


def main(run):
    load = lambda name: json.loads((run/name).read_text())
    decision, summary, diagnostic = load('decision.json'), load('summary.json'), load('diagnosis.json')
    base = summary['lqr']
    numerics = load('forecast-numerics.json')['checks']
    lines = ['# PPO performance audit and resumable experiment v12', '',
        'The20% target is a research objective, not a result that can be guaranteed by debugging. '
        'This audit covers the active training/normalization/action-credit, sensing, packet lifecycle, '
        'supervisor/recovery, compensation, physical reward/plant, export, runtime and selection chain. '
        'The repository-wide Python inventory supplies syntax/hash coverage; it is not a claim that every historical source line is semantically verified.', '',
        '## Confirmed defects and changes', '',
        '1. Response-delay compensation still used10ms semi-implicit Euler while the supervisor had moved to1ms RK4. '
        'Version12 uses the same nominal dynamics and held10ms LQR control with1ms RK4 in the input forecast and causal planner. '
        f'Across24 fixed independently integrated DOP853 cases, maximum state error changes from {max(r["old_max_abs_state_error"] for r in numerics):.8g} '
        f'to {max(r["fixed_max_abs_state_error"] for r in numerics):.8g}. This corrects numerical inconsistency; it does not identify the unknown nonlinear plant or prove tracking improvement.',
        '2. The previous runner refused partial training folders. The new runner saves atomic, hashed update-boundary checkpoints including '
        'actor/critic/Adam, full environment and worker queue, observer, reward-normalization statistics and accumulated returns, '
        'Python/NumPy/Torch RNGs and training counters. A restart restores the latest committed snapshot and repeats only uncommitted work. '
        'Tests require exact equality to uninterrupted training, including a time-limit auto-reset. Partial writes cannot replace the last good pointer; corrupt or changed-source checkpoints are refused.',
        '3. Evaluation now saves and verifies each completed episode independently. An incomplete episode is deterministically rerun; completed evidence is never silently replaced. '
        'Training checkpoints are saved and, with --publish, committed/pushed every10,000 new steps. In-flight work after that boundary is not claimed to be saved.', '',
        '## Why the previous PPO gain was small', '',
        f'- Only {diagnostic["counts"]["active"]:,}/{diagnostic["counts"]["ticks"]:,} recorded v11 control ticks had learned authority. '
        'Nominal cost rejection occurred on29277/32964ticks. The candidate must improve the declared balanced predicted cost before the supervisor applies it.',
        '- Residuals are restricted to five values between-0.08and+0.08rad, filtered at0.3s and multiplied by at most0.25. '
        'At40ms response age only one10ms control tick remains before50ms expiry. At100ms, learned authority is exactly zero by design. '
        'These are architectural constraints, not software exceptions to remove to obtain20%.',
        f'- The inherited v11 policy has mean entropy {diagnostic["mean_entropy_nats"]:.4f} nats versus a five-action maximum1.6094; '
        f'{100*diagnostic["fraction_max_probability_over_099"]:.2f}% of visited queries assign more than99% probability to one action. '
        'Low initial exploration is a plausible learning bottleneck. These associations do not establish a unique causal explanation.',
        '- The supervisor and compensation use a nominal linear bicycle while the software plant has nonlinear tires and stiffness mismatch. '
        'The model-based causal planner is a tested comparator, not a globally optimal ceiling. More expressive robust/adaptive prediction remains a research question.',
        '- Training rewards lateral error, heading, actual steering rate and effort. A lateral-only20% target can conflict with smoothness and heading constraints. '
        'A submitted action receives gradient credit even if delayed or subsequently rejected; the existing mask correctly removes busy-worker actions, '
        'but submitted-request credit can have low signal. Changing this estimator or the objective requires a separately validated experiment.', '',
        '## Frozen experiment and results', '',
        'Six final endpoints: two arms x three seeds x50,000 additional steps =300,000 NEW steps. '
        'continued preserves the v11 actor/critic/Adam/reward normalization and uses the corrected forecast. '
        'explore additionally divides initial action-head weights/bias by4and resets only its Adam slots. '
        'The latter is an exploration experiment, not a bug fix. Initial greedy actions and critic parameters remain identical; both arms use identical hyperparameters, '
        'matched per-pair RNG/noise, freshness, authority limits, reward and final-endpoint policy. No seed mixing, budget extension or best-checkpoint selection.',
        f'{decision["episodes"]} fresh matched development episodes, {decision["transitions"]:,} replayed transitions, '
        f'{decision["neural_queries"]:,} single-row neural decisions, {decision["exact_delay100_pairs"]} exact100ms/LQR trajectory pairs. '
        'Every normal comparator uses the corrected forecast and same information. legacy_prior is the numerical A/B using the unchanged v11 forecast and weights.', '',
        '| Controller | Tracking gain vs LQR | Heading change vs LQR | Steering-rate change vs LQR | Survived |',
        '|---|---:|---:|---:|---:|']
    for name, stats in summary.items():
        lines.append(f'| {name} | {stats["gain_vs_lqr_pct"]:+.4f}% | {100*(stats["heading_rmse_rad"]/base["heading_rmse_rad"]-1):+.3f}% | '
                     f'{100*(stats["rate_rms_rad_s"]/base["rate_rms_rad_s"]-1):+.3f}% | {stats["survived"]}/{stats["episodes"]} |')
    for arm, result in decision['arms'].items():
        lines += ['', f'**{arm}:20% requirement {"PASS" if result["twenty_percent_pass"] else "FAIL"}.**', '',
            'Matched gains: '+', '.join(f'{name} {gain:+.4f}%' for name, gain in result['gains_pct'].items())+'.',
            'Failed checks: '+('; '.join(result['reasons']) or 'none')+'.']
    numerical_gain = 100*(1-summary['prior']['rmse_m']/summary['legacy_prior']['rmse_m'])
    lines += ['', f'Unchanged v11 weights, corrected versus legacy forecast: {numerical_gain:+.5f}% tracking gain on the same grid. '
        'Numerical accuracy and empirical controller superiority are separate outcomes.', '',
        '## Evidence limits and next work', '',
        'No final controller is promoted by this audit. Reserved/unseen-path tests remain unopened. '
        'The replay uses the recorded inputs and code dynamics, with independent metric aggregation; it is not an independent physical simulator. '
        'New controller timing/native Webots/actual laptop and physical sensor–communication–actuator validation remain unperformed. '
        'A full matched robust published vehicle controller/MPC reproduction and remaining bibliography verification are still required. '
        'No20% all-baseline claim, deployment readiness, hard real-time guarantee or global stability proof follows from surviving software episodes.', '',
        'The next useful development task is to establish repeatable balanced headroom with a causal model-based controller '
        'and measure action-level predicted versus realized benefit under model mismatch. '
        'An additional learning method should be judged against that strong controller. '
        'Repeatedly extending PPO training until a selected result crosses20% is not an evidence-backed fix.', '',
        '## Resume', '', '```bash', 'cd /workspace/LANS',
        '/workspace/lans-venv/bin/python tools/reviewer_v12/run12.py --publish', '```', '',
        'The same command verifies frozen inputs, loads completed training checkpoints, skips verified completed stages, '
        'resumes episode-level evaluation, verifies results and republishes the report. '
        'Exit2 means the empirical20% target failed, not that the pipeline crashed. '
        'Check RESUME.md and status.json for the last completed stage. Cloud storage alone cannot protect unpushed work after the most recent checkpoint.']
    (run/'README.md').write_text('\n'.join(lines)+'\n')
    files = [f for f in run.rglob('*') if f.is_file() and '.partial-' not in str(f) and f.name not in
             ('evidence-hashes.json', 'README.md', 'RESUME.md', 'status.json') and f.suffix in ('.json', '.npz', '.csv', '.pkl', '.zip', '.log')]
    hashes = {str(f.relative_to(run)): digest(f) for f in files}
    seal = run/'evidence-hashes.json'
    if seal.exists():
        assert json.loads(seal.read_text())['sha256'] == hashes, 'Completed evidence changed'
    else:
        atomic_json(seal, dict(sha256=hashes))

