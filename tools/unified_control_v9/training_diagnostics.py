"""Training-only audit of delayed PPO authority and retained failure trajectories.

This reads every saved training transition, without selecting checkpoints,
opening evaluation data, changing a controller, or rerunning an experiment.
The trace records the combined admission result; it cannot identify individual
cost, heading, steering-rate and clearance subguards from that result alone.
"""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'results/publication-v9'
TTL = .15


def authority_category(decision):
    eligible = decision['eligible']
    if 'ppo' in eligible:
        if not eligible['ppo']:
            return 'combined_prediction_guard_rejected'
        return 'selected' if decision['source'] == 'ppo' else 'feasible_but_not_selected'
    if decision.get('ego_backup'):
        return 'ego_backup'
    if decision['risk'] == 'DANGER':
        return 'danger_supervisor_excluded'
    if decision['proposal_age'] is None:
        return 'no_response_yet'
    if decision['proposal_age'] >= TTL - 1e-9 or decision['proposal_wall_age'] >= TTL - 1e-9:
        return 'expired_at_issue'
    return 'not_evaluated_other'


def failed(truth):
    return bool(truth['collision'] or abs(truth['error']) > 1.75)


def brief(row):
    decision = row['decision']
    shadow = row['shadow_decision']
    return dict(tick=row['tick'], time_s=row['time_s'], source=decision['source'],
        reason=decision['reason'], risk=decision['risk'],
        lqr_eligible=decision['eligible'].get('lqr'),
        shadow_reason=shadow['reason'], shadow_risk=shadow['risk'],
        applied_steering=row['applied_steering'], applied_accel=row['applied_accel'],
        shadow_steering=row['shadow_steering'], shadow_accel=row['shadow_accel'],
        actual_truth=row['truth'], shadow_truth=row['shadow_truth'],
        state_after=row['state_after'], shadow_after=row['shadow_after'])


def audit_seed(seed):
    directory = DATA / 'policies' / f'seed-{seed}'
    manifest = json.loads((directory / 'manifest.json').read_text())
    protocol = json.loads((directory / 'protocol.json').read_text())
    assert protocol['service_s'] == .05 and protocol['new_steps'] == 16384
    rows = 0
    counts = Counter()
    categories = Counter()
    reasons = Counter()
    sources = Counter()
    by_delay = {}
    failures = []
    episodes = []
    current = None
    accepted = None
    trace_digest = hashlib.sha256()
    reward_sum = 0.
    selected_delays = Counter()
    unique_actions = set()
    def finish_episode():
        if current is None:
            return
        episodes.append({k: current[k] for k in ('episode', 'case', 'ticks', 'terminated',
            'truncated', 'actual_first_failure_tick', 'shadow_first_failure_tick',
            'first_state_divergence_tick', 'first_command_divergence_tick', 'ppo_selected',
            'reward_sum', 'max_actual_error_m', 'max_shadow_error_m')})
        if current['terminated']:
            failures.append(dict(**episodes[-1], initial_state=current['initial_state'],
                final_actual=current['last']['truth'], final_shadow=current['last']['shadow_truth'],
                final_state_distance_max=max(abs(a-b) for a,b in zip(current['last']['state_after'],current['last']['shadow_after'])),
                all_failure_history=current['history'],
                interpretation='Shared failure in both trajectories' if current['shadow_first_failure_tick'] is not None
                    else 'Hybrid fails while the matched LQR shadow remains inside the checked envelope up to this termination; no later counterfactual is recorded.'))
    with (directory / 'training.jsonl').open('rb') as stream:
        for raw in stream:
            trace_digest.update(raw)
            row = json.loads(raw)
            assert row['case']['stage'] == 'v9_training_only'
            if current is None or row['episode'] != current['episode']:
                finish_episode()
                assert row['tick'] == 0
                current = dict(episode=row['episode'], case=row['case'], ticks=0,
                    initial_state=row['state_before'], terminated=False, truncated=False,
                    actual_first_failure_tick=None, shadow_first_failure_tick=None,
                    first_state_divergence_tick=None, first_command_divergence_tick=None,
                    ppo_selected=0, reward_sum=0., max_actual_error_m=0., max_shadow_error_m=0., history=[])
                accepted = None
            assert row['tick'] == current['ticks'] and row['case'] == current['case']
            decision = row['decision']; info = row['info']
            category = authority_category(decision)
            delay_key = format(row['case']['delay'], '.2f')
            group = by_delay.setdefault(delay_key, dict(ticks=0, submitted=0, accepted_after_step=0,
                ppo_candidates_evaluated=0, categories=Counter(), sources=Counter()))
            rows += 1; group['ticks'] += 1
            categories[category] += 1; group['categories'][category] += 1
            reasons[decision['reason']] += 1; sources[decision['source']] += 1
            group['sources'][decision['source']] += 1
            reward_sum += row['reward']; unique_actions.add(row['action'])
            counts['nonzero_reward_ticks'] += abs(row['reward']) > 1e-12
            counts['zero_reward_ticks'] += abs(row['reward']) <= 1e-12
            counts['busy_feature_zero_ticks'] += row['observation'][-1] == 0
            counts['submitted'] += bool(info['submitted']); group['submitted'] += bool(info['submitted'])
            counts['accepted_after_step'] += info['accepted'] is True
            group['accepted_after_step'] += info['accepted'] is True
            counts['rejected_after_step'] += info['accepted'] is False
            counts['no_acceptance_on_terminal_step'] += info['accepted'] is None
            if 'ppo' in decision['eligible']:
                counts['ppo_candidates_evaluated'] += 1; group['ppo_candidates_evaluated'] += 1
                assert accepted is not None, ('Unrecorded PPO response', seed, row['episode'], row['tick'])
                expected_age = row['time_s'] + row['case']['delay'] - accepted['observed_s']
                assert abs(decision['proposal_age'] - expected_age) < 1e-10
                assert expected_age < TTL - 1e-9
                assert accepted['submission_tick'] < row['tick'], 'Current sampled action must not bypass its declared service delay'
                if category == 'combined_prediction_guard_rejected':
                    counts['rejected_despite_lower_mean_cost'] += decision['costs']['ppo'] < decision['costs']['lqr'] - 1e-9
                    counts['rejected_with_no_lower_mean_cost'] += decision['costs']['ppo'] >= decision['costs']['lqr'] - 1e-9
                elif category == 'feasible_but_not_selected':
                    counts['feasible_cost_ties_with_lqr'] += abs(decision['costs']['ppo']-decision['costs']['lqr']) <= 1e-8
                if decision['source'] == 'ppo':
                    assert abs(decision['residual'] - accepted['residual']) < 1e-12
                    selected_delays[format(row['time_s']-accepted['submitted_s'], '.2f')] += 1
                    current['ppo_selected'] += 1
            if accepted is not None and decision['proposal_age'] is not None:
                assert abs(decision['proposal_age']-(row['time_s']+row['case']['delay']-accepted['observed_s'])) < 1e-10
            if info['accepted'] is True:
                assert info['submitted'] and info['submission_sequence'] == info['response_sequence']
                accepted = dict(sequence=info['response_sequence'], submission_tick=row['tick'],
                    observed_s=row['time_s'], submitted_s=row['time_s'], residual=max(-1.,min(1.,row['action']))*.08)
            actual_failure = failed(row['truth']); shadow_failure = failed(row['shadow_truth'])
            assert row['terminated'] == actual_failure
            if actual_failure and current['actual_first_failure_tick'] is None:current['actual_first_failure_tick'] = row['tick']
            if shadow_failure and current['shadow_first_failure_tick'] is None:current['shadow_first_failure_tick'] = row['tick']
            state_gap = max(abs(a-b) for a,b in zip(row['state_after'],row['shadow_after']))
            command_gap = max(abs(row['applied_steering']-row['shadow_steering']),abs(row['applied_accel']-row['shadow_accel']))
            if state_gap > 1e-10 and current['first_state_divergence_tick'] is None:current['first_state_divergence_tick'] = row['tick']
            if command_gap > 1e-12 and current['first_command_divergence_tick'] is None:current['first_command_divergence_tick'] = row['tick']
            current['ticks'] += 1; current['terminated'] = row['terminated']; current['truncated'] = row['truncated']
            current['reward_sum'] += row['reward']
            current['max_actual_error_m'] = max(current['max_actual_error_m'],abs(row['truth']['error']))
            current['max_shadow_error_m'] = max(current['max_shadow_error_m'],abs(row['shadow_truth']['error']))
            current['history'].append(brief(row)); current['last'] = row
    finish_episode()
    assert rows == 16384 and trace_digest.hexdigest() == manifest['training_trace_sha256']
    assert sum(categories.values()) == rows
    return dict(seed=seed,steps=rows,training_trace_sha256=trace_digest.hexdigest(),
        protocol_sha256=hashlib.sha256((directory/'protocol.json').read_bytes()).hexdigest(),
        counts=dict(counts),authority_categories=dict(categories),selected_sources=dict(sources),
        reasons=dict(reasons),by_command_delay=by_delay,reward_sum=reward_sum,
        unique_sampled_actions=len(unique_actions),selected_proposal_service_delay_s=dict(selected_delays),
        failures=failures,episodes=episodes,
        failures_shared_with_shadow=sum(f['shadow_first_failure_tick'] is not None for f in failures),
        failures_with_shadow_still_inside_envelope=sum(f['shadow_first_failure_tick'] is None for f in failures))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DATA/'training-diagnostics/audit.json')
    args=parser.parse_args()
    reports=[audit_seed(seed) for seed in (42,43,44)]
    categories=Counter();counts=Counter()
    for report in reports:categories.update(report['authority_categories']);counts.update(report['counts'])
    steps=sum(report['steps'] for report in reports)
    result=dict(diagnostic_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scope='All frozen v9 training transitions only; no prospective or final evaluation data read.',
        steps=steps,counts=dict(counts),authority_categories=dict(categories),
        ppo_selection_percent=100*categories['selected']/steps,
        failure_episodes=sum(len(r['failures']) for r in reports),
        failures_shared_with_shadow=sum(r['failures_shared_with_shadow'] for r in reports),
        failures_with_shadow_still_inside_envelope=sum(r['failures_with_shadow_still_inside_envelope'] for r in reports),
        endpoints=reports,
        findings=[
            'A sampled action enters a one-request 50 ms service queue. The current reward can reflect a previously submitted action; this is delayed credit, not immediate control authority.',
            'At 100 ms command delay, 50 ms service consumes the entire 150 ms proposal TTL. Acceptance permits equality; decision admission requires strict freshness and excludes the boundary proposal.',
            'The 17-feature feedforward actor omits the pending residual and controller estimator history, so delayed control is partially observed.',
            'Recorded eligible=false is a combined admission result. It cannot alone separate robust mixed-cost dominance, heading, steering-rate and physical-clearance subguards.',
            'Lower mean predicted PPO cost can still fail a per-model cost or secondary-quality/clearance check; recorded aggregate cost is not sufficient to blame a specific subguard.',
            'The optimizer must choose among admitted analytical, grid, planned and PPO candidates. Feasible does not imply selected, especially when bounded commands have equal cost.',
            'This audit does not estimate a global achievable improvement bound or justify weakening safety or baseline controllers.'],
        next_research_options=[
            'Use a newly declared development-only study with a pending-action/history-aware observation or recurrent policy; retain the old frozen study.',
            'Train a proposal distribution on feasible residual authority or a learned planning/model objective, and log each admission subguard separately.',
            'Address the service-delay/TTL boundary by reducing measured service or declaring a compatible control architecture, never by relabeling old observations as fresh.',
            'Treat any newly inspected failure fixture as a regression case; use a new untouched cohort for claims about a repaired controller.'])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    assert not args.output.exists(),'Preserve prior diagnostic evidence'
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('steps','counts','authority_categories','ppo_selection_percent','failure_episodes','failures_shared_with_shadow','failures_with_shadow_still_inside_envelope')},indent=2))


if __name__=='__main__':main()
