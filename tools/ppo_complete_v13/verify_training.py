"""Streaming V13 evidence audit; it never opens prospective case namespaces.

The default audit independently integrates the original Python RK4 plant and
shadow from recorded bounded commands, reconstructs delayed FIFOs, NPC truth,
finite-task scores and causal history features. ``--replay-controllers`` adds
the much slower complete current-query/guard/decision recomputation. Neither
mode claims to rerun stochastic PPO Adam trajectories or certify wall timing.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import math
import multiprocessing as mp
from pathlib import Path

import numpy as np

from integrations.unified_lans.physics import Command, Config, advance
from integrations.unified_lans.simulation import initial, move_npcs, truth_metrics
from tools.unified_campaign.study import StudyRoute
from .learning import ACTION_DIM, CONTRACT, DATA, Env, HORIZON, OBSERVATION_DIM, ROOT, curriculum
from .train import CONTROLLER_KWARGS, SEEDS, STEPS, actor_digest


def digest(path):
    """Bounded-memory SHA256, including multi-gigabyte raw traces."""
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    temporary.replace(path)


def equal(actual, expected, label='', atol=2e-10):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys(), (label, actual.keys(), expected.keys())
        for key, value in expected.items():
            equal(actual[key], value, f'{label}.{key}', atol)
    elif isinstance(expected, (list, tuple, np.ndarray)):
        np.testing.assert_allclose(actual, expected, rtol=0, atol=atol, err_msg=label)
    elif isinstance(expected, (bool, np.bool_)) or expected is None or isinstance(expected, str):
        assert actual == expected, (label, actual, expected)
    elif math.isinf(float(expected)):
        # Raw clean() encodes nonfinite diagnostic values as null.
        assert actual is None or actual == expected, (label, actual, expected)
    else:
        assert abs(float(actual)-float(expected)) <= atol, (label, actual, expected)


def tensor_equal(a, b):
    import torch
    if isinstance(a, torch.Tensor):
        assert isinstance(b, torch.Tensor) and torch.equal(a, b)
    elif isinstance(a, dict):
        assert a.keys() == b.keys()
        for key in a:
            tensor_equal(a[key], b[key])
    elif isinstance(a, (list, tuple)):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            tensor_equal(x, y)
    else:
        assert a == b


def source_protocol(folder):
    protocol = read(folder/'protocol.json')
    for name, expected in protocol['source_hashes'].items():
        assert digest(folder/'source'/name) == expected, ('Saved source', folder, name)
        assert digest(ROOT/name) == expected, ('Active replay dependency changed', name)
    return protocol


def initial_truth(case):
    """Independent initialization, including the declared pre-shift NPC heading."""
    route0, _, npcs = initial(case['scenario'], 0.)
    route = StudyRoute(route0.kind, case['mirror'], case['phase'], case['amplitude'])
    y, heading, _ = route.geometry(0.)
    state = np.array([0., y+case['lateral'], heading+case['heading'], case['speed'], 0., 0.])
    for npc in npcs.values():
        if case['scenario'] == 'crossing':
            npc[1] *= case['mirror']
            npc[2] *= case['mirror']
        else:
            npc[1] = route.geometry(npc[0])[0] if case['scenario'] in ('curved', 'merge') else 0.
            npc[2] = route.geometry(npc[0])[1] if case['scenario'] == 'curved' else 0.
            npc[3] = max(3., case['speed']-4.)
        npc[0] += case.get('npc_x_shift', 0.)
        npc[3] *= case.get('npc_speed_scale', 1.)
    return route, state, npcs


def bounded(command, previous):
    assert abs(command.steering) <= .5+1e-12
    assert abs(command.steering-previous.steering) <= .03+1e-12
    assert -6.-1e-12 <= command.accel <= 2.5+1e-12


def semantic_equal(recorded, regenerated, label=''):
    """Compare complete logical decisions, excluding measured compute durations."""
    for key, expected in regenerated.items():
        if key.endswith('_ms'):
            continue
        assert key in recorded, (label, 'Missing', key)
        if isinstance(expected, dict):
            semantic_equal(recorded[key], expected, f'{label}.{key}')
        else:
            equal(recorded[key], expected, f'{label}.{key}', atol=1e-7 if key.startswith('observation') else 2e-9)


def replay_trace(path, *, expected_steps, rng_seed=None, expected_cases=None,
                 complete_episodes=None, deterministic_actor=None, replay_controllers=False,
                 keep_returns=False, progress_label=''):
    """Verify every streamed row, including all failures and final partial rollouts."""
    rng = None if rng_seed is None else np.random.default_rng(rng_seed)
    cfg = Config(horizon=2.)
    episode = -1
    previous_done = True
    count = completed = failures = selected = raw_scored = 0
    reasons = Counter()
    raw_violations = Counter()
    failed_episodes = []
    observations, targets = [], []
    semantic_env = Env(controller_kwargs=CONTROLLER_KWARGS) if replay_controllers else None
    try:
        with Path(path).open() as stream:
            for line in stream:
                assert line.strip(), ('Blank raw row', path, count)
                row = json.loads(line)
                case = row['case']
                if row['episode_id'] != episode:
                    assert previous_done and row['episode_id'] == episode+1 and row['tick'] == 0, (path, count, 'Dropped/reset episode')
                    episode += 1
                    current_case = case
                    if rng is not None:
                        assert case == curriculum(rng), ('Case RNG sequence', path, episode)
                    if expected_cases is not None:
                        assert case == expected_cases[episode]
                    assert case['network'] == 'nominal' and case['delay'] in (0., .05, .1)
                    route, state, npcs = initial_truth(case)
                    shadow = state.copy()
                    pending, shadow_pending = [], []
                    issued = applied = shadow_issued = shadow_applied = Command()
                    previous_action = np.zeros(8)
                    sse = physical_sse = heading_sq = rate_sq = shadow_heading = shadow_rate = 0.
                    primary_total = 0.
                    tick = 0
                    prior_next = None
                    local_observations, local_rewards = [], []
                    if semantic_env is not None:
                        if expected_cases is not None:
                            semantic_obs, _ = semantic_env.reset(options={'case': case})
                        else:
                            semantic_obs, _ = semantic_env.reset(seed=rng_seed if episode == 0 else None)
                assert row['case'] == current_case and row['tick'] == tick and tick < HORIZON
                now = tick*.05
                equal(row['time_s'], now, 'time')
                equal(row['state_before'], state, 'plant before')
                equal(row['shadow_before'], shadow, 'shadow before')
                observation = np.asarray(row['observation'], np.float32)
                next_observation = np.asarray(row['observation_next'], np.float32)
                # Preserve the exact recorded coefficients. Training actions are
                # float32, while the separately opened computed teacher may
                # deliberately carry float64 coefficients.
                action = np.asarray(row['label'], float)
                assert observation.shape == next_observation.shape == (55,) and action.shape == (8,)
                assert np.isfinite(observation).all() and np.isfinite(next_observation).all() and np.isfinite(action).all()
                assert np.max(abs(observation)) <= 5. and np.max(abs(next_observation)) <= 5. and np.max(abs(action)) <= 1.
                if prior_next is not None:
                    np.testing.assert_array_equal(observation, prior_next)
                equal(observation[14:16], [applied.steering/.5, applied.accel/6], 'received applied controls', atol=1e-7)
                equal(observation[19], case['delay']/.15, 'causal delay', atol=1e-7)
                equal(observation[30:38], previous_action, 'last proposal', atol=1e-7)
                equal(observation[40:42], [issued.steering/.5, issued.accel/6], 'previous issued controls', atol=1e-7)
                equal(observation[42:51], np.clip(row['anchor_features'], -5, 5), 'current anchor features', atol=1e-7)
                equal(observation[51], 1-tick/HORIZON, 'remaining finite time', atol=1e-7)
                energies = [math.sqrt(physical_sse/HORIZON)/.25,
                    heading_sq/(HORIZON*.02**2), rate_sq/(HORIZON*.2**2)]
                equal(observation[52:55], np.clip(energies, -5, 5), 'causal received-history energies', atol=5e-7)
                proposal = row['proposal']
                assert proposal is not None and proposal['sequence'] == tick+1
                equal(proposal['coefficients'], action, 'actual proposal coefficients', atol=1e-7)
                for key in ('observed_s', 'submitted_s', 'wall_observed'):
                    equal(proposal[key], now, 'original logical source time')
                if deterministic_actor is not None:
                    prediction, _ = deterministic_actor.predict(observation, deterministic=True)
                    np.testing.assert_array_equal(action, prediction)
                if semantic_env is not None:
                    equal(observation, semantic_obs, 'fully recomputed current query', atol=1e-7)
                    semantic_obs, _, _, _, regenerated = semantic_env.step(action)
                    semantic_equal(row, regenerated)
                old_applied, old_shadow_applied = applied, shadow_applied
                command = Command(row['issued_steering'], row['issued_accel'])
                shadow_command = Command(row['shadow_decision']['issued_steering'], row['shadow_decision']['issued_accel'])
                bounded(command, issued)
                bounded(shadow_command, shadow_issued)
                issued, shadow_issued = command, shadow_command
                pending.append((now+case['delay'], command))
                shadow_pending.append((now+case['delay'], shadow_command))
                while pending and pending[0][0] <= now+1e-9:
                    _, applied = pending.pop(0)
                while shadow_pending and shadow_pending[0][0] <= now+1e-9:
                    _, shadow_applied = shadow_pending.pop(0)
                equal([row['applied_steering'], row['applied_accel']], [applied.steering, applied.accel], 'delayed ego FIFO')
                equal([row['shadow_steering'], row['shadow_accel']], [shadow_applied.steering, shadow_applied.accel], 'delayed shadow FIFO')
                state = advance(state, applied, .05, case['stiffness'])
                shadow = advance(shadow, shadow_applied, .05, case['stiffness'])
                equal(row['state_after'], state, 'plant RK4')
                equal(row['shadow_after'], shadow, 'shadow RK4')
                move_npcs(npcs, .05, route, case['scenario'])
                equal(row['npc_truth'], npcs, 'independent moving traffic')
                truth = truth_metrics(state, npcs, route, cfg)
                shadow_truth = truth_metrics(shadow, npcs, route, cfg)
                for key, value in truth.items():
                    equal(row[key], value, 'ego truth.'+key)
                equal(row['shadow_truth'], shadow_truth, 'shadow truth')
                rate = (applied.steering-old_applied.steering)/.05
                srate = (shadow_applied.steering-old_shadow_applied.steering)/.05
                equal(row['steering_rate'], rate, 'applied steering rate')
                equal(row['shadow_rate'], srate, 'shadow steering rate')
                failed = bool(truth['collision'] or truth['corridor_exceeded'])
                before_sse = sse
                physical_sse += truth['error']**2
                sse += truth['error']**2+(HORIZON-tick-1)*6.25*failed
                primary = 100*(math.sqrt((before_sse+1e-12)/HORIZON)-math.sqrt((sse+1e-12)/HORIZON))
                primary_total += primary
                heading_sq += truth['heading_error']**2
                rate_sq += rate*rate
                shadow_heading += shadow_truth['heading_error']**2
                shadow_rate += srate*srate
                done = failed or tick+1 == HORIZON
                parts = dict(rmse_reward=primary)
                if done:
                    heading_ratio = math.sqrt(heading_sq/max(shadow_heading, 1e-8))
                    rate_ratio = math.sqrt(rate_sq/max(shadow_rate, 1e-8))
                    progress_ratio = state[0]/max(shadow[0], 1e-6)
                    parts.update(heading_penalty=-20*max(0., heading_ratio-1.05),
                        rate_penalty=-20*max(0., rate_ratio-1.05),
                        progress_penalty=-100*max(0., .995-progress_ratio)-5*(progress_ratio<.99),
                        failure_penalty=-20.*failed)
                equal(row['score_error_sq'], sse, 'whole-run penalized SSE')
                equal(row['heading_energy'], heading_sq, 'heading energy')
                equal(row['rate_energy'], rate_sq, 'rate energy')
                equal(row['reward_parts'], parts, 'finite-task reward components')
                equal(row['reward'], sum(parts.values()), 'total constrained reward')
                assert row['terminated'] == done and row['truncated'] is False
                assert row['terminal_reason'] == ('failure' if failed else 'horizon' if done else '')
                equal(next_observation[51], 1-(tick+1)/HORIZON, 'real terminal/next remaining time', atol=1e-7)
                next_energies = [math.sqrt(physical_sse/HORIZON)/.25,
                    heading_sq/(HORIZON*.02**2), rate_sq/(HORIZON*.2**2)]
                equal(next_observation[52:55], np.clip(next_energies, -5, 5), 'next causal energies', atol=5e-7)
                equal(next_observation[30:38], action, 'next proposal history', atol=1e-7)
                picked = bool(row['sequence_plan_selected'])
                assert picked == (row['source'] == 'ppo_anchor')
                if picked:
                    assert row['sequence_reason'] == 'fresh_anchored_improvement'
                    assert row['projection_scale'] in (1., .5, .25, .125, .0625)
                    assert row['sequence_cost'] < row['anchor_reference_cost']-1e-8
                    values = np.asarray(row['applied_score_values'])
                    assert values.shape == (3, 4) and np.isfinite(values).all() and np.min(values[:, 1]) >= 0
                    equal(row['sequence_cost'], np.mean(values[:, 0]), 'admitted model mean cost')
                    assert abs(row['residual']) <= .08+1e-12
                selected += picked
                reasons[row['sequence_reason']] += 1
                if 'raw_score_values' in row:
                    raw_scored += 1
                    raw_values = np.asarray(row['raw_score_values'])
                    assert raw_values.shape == (3, 4) and np.isfinite(raw_values).all()
                    equal(row['raw_score_cost'], np.mean(raw_values[:, 0]), 'raw model mean cost')
                    for key, value in row['raw_score_violations'].items():
                        assert math.isfinite(value) and value >= 0
                        raw_violations[key] += value > 0
                if keep_returns:
                    local_observations.append(observation.copy())
                    local_rewards.append(row['reward'])
                if done:
                    completed += 1
                    failures += failed
                    if failed:
                        failed_episodes.append(dict(episode_id=episode, case=current_case,
                            observed_ticks=tick+1, collision=truth['collision'], corridor_exceeded=truth['corridor_exceeded'],
                            penalized_rmse_m=math.sqrt(sse/HORIZON)))
                    equal(primary_total, 100*(math.sqrt(1e-12/HORIZON)-math.sqrt((sse+1e-12)/HORIZON)), 'complete primary telescoping', atol=1e-8)
                    if keep_returns:
                        total = 0.
                        returns = []
                        for reward in reversed(local_rewards):
                            total += reward
                            returns.append(total)
                        observations.extend(local_observations)
                        targets.extend(reversed(returns))
                prior_next = next_observation
                previous_action = action.copy()
                previous_done = done
                tick += 1
                count += 1
                if progress_label and count % 8192 == 0:
                    print('V13 PHYSICAL TRAINING REPLAY', progress_label, count, flush=True)
        assert count == expected_steps, ('Missing/extra physical rows', path, count, expected_steps)
        assert completed+int(not previous_done) == episode+1 and len(failed_episodes) == failures
        if complete_episodes is not None:
            assert completed == episode+1 == complete_episodes and previous_done, ('Incomplete warmup/teacher episodes', path)
        report = dict(rows=count, episodes_started=episode+1, complete_episodes=completed,
            final_partial_episode=int(not previous_done), failures=failures, selected_ticks=selected,
            raw_scored_ticks=raw_scored, raw_violation_ticks=dict(raw_violations), failed_episodes=failed_episodes,
            sequence_reasons=dict(reasons), raw_sha256=digest(path), physical_shadow_fifo_npc_replayed=True,
            causal_history_features_replayed=True, full_controller_query_guard_replayed=replay_controllers,
            stochastic_ppo_gradients_rerun=False)
        assert sum(reasons.values()) == count
        return report, np.asarray(observations, np.float32), np.asarray(targets, np.float32)
    finally:
        if semantic_env is not None:
            semantic_env.close()


def rebuild_bc_and_warmup(seed, dataset, observations, returns, bc, folder):
    """Recreate only the declared supervised/value fitting, not stochastic PPO."""
    import torch
    from .learner import IndependentPPO, optimizer_steps
    torch.manual_seed(seed)
    env = Env(controller_kwargs=CONTROLLER_KWARGS)
    try:
        model = IndependentPPO('MlpPolicy', env, seed=seed, device='cpu',
            policy_kwargs=dict(net_arch=dict(pi=[128, 128], vf=[128, 128])))
        x, y, weights = (torch.tensor(dataset[key]) for key in ('observations', 'actions', 'weights'))
        supervised = torch.optim.Adam(model._actor_parameters, lr=3e-4)
        rng = np.random.default_rng(seed)
        for _ in range(32):
            permutation = rng.permutation(len(x))
            for start in range(0, len(x), 128):
                ids = permutation[start:start+128]
                means = model.policy.get_distribution(x[ids]).distribution.mean
                loss = (weights[ids]*(means-y[ids]).square().mean(dim=1)).mean()
                supervised.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model._actor_parameters, 1.)
                supervised.step()
        assert actor_digest(model) == actor_digest(bc), 'Initial BC actor or warmup actor changed'
        saved = torch.load(folder/'bc-supervised-optimizer.pt', map_location='cpu')
        tensor_equal(supervised.state_dict(), saved)
        initial_digest = actor_digest(model)
        x = torch.tensor(observations)
        target = torch.tensor(returns)
        rng = np.random.default_rng(seed+400000)
        for _ in range(4):
            permutation = rng.permutation(len(x))
            for start in range(0, len(x), 128):
                index = permutation[start:start+128]
                predicted = model.policy.predict_values(x[index]).flatten()
                loss = .5*torch.nn.functional.mse_loss(predicted, target[index])
                model.critic_optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model._critic_parameters, .5, error_if_nonfinite=True)
                model.critic_optimizer.step()
                model.critic_steps += 1
        assert initial_digest == actor_digest(model) == actor_digest(bc)
        tensor_equal(model.policy.state_dict(), bc.policy.state_dict())
        tensor_equal(model.critic_optimizer.state_dict(), bc.critic_optimizer.state_dict())
        assert model.critic_steps == bc.critic_steps and optimizer_steps(model.actor_optimizer) == 0
        return dict(initial_bc_supervised_updates=optimizer_steps(supervised),
            initial_bc_actor_and_adam_byte_reproduced=True, warmup_actor_unchanged=True,
            warmup_critic_and_adam_byte_reproduced=True)
    finally:
        env.close()


def rebuild_continued(seed, dataset, bc, continued, folder, budget):
    import torch
    from .learner import optimizer_steps
    # The loaded BC is private to this audit and no longer needed afterward.
    optimizer = torch.optim.Adam(bc._actor_parameters, lr=3e-4)
    x, y, weights = (torch.tensor(dataset[key]) for key in ('observations', 'actions', 'weights'))
    rng = np.random.default_rng(seed+200000)
    for _ in range(budget):
        index = rng.integers(len(x), size=128)
        means = bc.policy.get_distribution(x[index]).distribution.mean
        loss = (weights[index]*(means-y[index]).square().mean(dim=1)).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(bc._actor_parameters, 1.)
        optimizer.step()
    tensor_equal(bc.policy.state_dict(), continued.policy.state_dict())
    tensor_equal(bc.critic_optimizer.state_dict(), continued.critic_optimizer.state_dict())
    tensor_equal(optimizer.state_dict(), torch.load(folder/'supervised-optimizer.pt', map_location='cpu'))
    assert optimizer_steps(optimizer) == budget
    return dict(continued_bc_actual_updates=budget, continued_bc_actor_and_adam_byte_reproduced=True,
        continued_bc_critic_unchanged=True)


def audit_seed(seed, replay_controllers=False, reuse=False):
    import torch
    from .learner import IndependentPPO, optimizer_steps
    torch.set_num_threads(1)
    folder = DATA/f'policies/seed-{seed}'
    continued_folder = DATA/f'continued-bc/seed-{seed}'
    protocol = source_protocol(folder)
    continued_meta = read(continued_folder/'manifest.json')
    for name, expected in continued_meta['source_hashes'].items():
        assert digest(continued_folder/'source'/name) == digest(ROOT/name) == expected
    metadata = read(folder/'manifest.json')
    warmup = read(folder/'critic-warmup.json')
    inputs = {}
    for base in (folder, continued_folder, DATA/'dataset'):
        for path in sorted(base.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                inputs[str(path.relative_to(ROOT))] = digest(path)
    for name in protocol['source_hashes']:
        inputs[name] = digest(ROOT/name)
    inputs[str(Path(__file__).relative_to(ROOT))] = digest(__file__)
    cache = DATA/f'audits/training-seed-{seed}-{digest(__file__)[:12]}-controllers-{int(replay_controllers)}.json'
    if reuse and cache.exists():
        cached = read(cache)
        assert cached['passed'] and cached['input_hashes'] == inputs
        print('V13 SOURCE-PINNED TRAINING AUDIT REUSED', seed, flush=True)
        return cached['report']
    assert protocol['seed'] == metadata['seed'] == continued_meta['seed'] == seed
    assert protocol['contract'] == metadata['contract'] == continued_meta['contract'] == CONTRACT
    assert metadata['observation_dim'] == continued_meta['observation_dim'] == OBSERVATION_DIM
    assert metadata['action_dim'] == continued_meta['action_dim'] == ACTION_DIM
    assert protocol['controller_kwargs'] == metadata['controller_kwargs'] == continued_meta['controller_kwargs'] == CONTROLLER_KWARGS
    assert protocol['dataset_sha256'] == digest(DATA/'dataset/dataset.npz')
    assert protocol['ppo_steps'] == metadata['steps'] == STEPS and protocol['gamma'] == 1.
    assert digest(folder/'policy.zip') == metadata['policy_sha256']
    assert digest(folder/'bc-policy.zip') == metadata['bc_policy_sha256'] == continued_meta['source_bc_sha256']
    assert digest(folder/'training.jsonl') == metadata['trace_sha256']
    assert digest(folder/'critic-warmup.jsonl') == warmup['trace_sha256']
    assert digest(folder/'bc-supervised-optimizer.pt') == metadata['bc_optimizer_sha256']
    assert digest(continued_folder/'policy.zip') == continued_meta['policy_sha256']
    assert digest(continued_folder/'supervised-optimizer.pt') == continued_meta['supervised_optimizer_sha256']
    model = IndependentPPO.load(folder/'policy.zip', device='cpu')
    bc = IndependentPPO.load(folder/'bc-policy.zip', device='cpu')
    continued = IndependentPPO.load(continued_folder/'policy.zip', device='cpu')
    for agent in (model, bc, continued):
        agent.validate_optimizer_counters()
        assert agent.observation_space.shape == (55,) and agent.action_space.shape == (8,)
        assert np.all(agent.action_space.low == -1) and np.all(agent.action_space.high == 1)
        assert agent.gamma == 1. and agent.gae_lambda == .95
        assert agent.n_steps == 1024 and agent.batch_size == 128 and agent.n_epochs == 10
        assert agent.target_kl == .01 and agent.actor_learning_rate == 1e-5 and agent.critic_learning_rate == 1e-4
        assert agent.actor_max_grad_norm == agent.critic_max_grad_norm == .5
        assert optimizer_steps(agent.policy.optimizer) == 0
    assert model.num_timesteps == STEPS and bc.num_timesteps == continued.num_timesteps == 0
    assert bc.actor_steps == continued.actor_steps == 0
    assert actor_digest(bc) == warmup['actor_unchanged_sha256']
    assert bc.critic_steps == continued.critic_steps == warmup['critic_updates'] == metadata['critic_warmup_steps']
    assert model.actor_steps == metadata['actor_steps'] == continued_meta['supervised_optimizer_steps']
    assert continued_meta['steps'] == continued_meta['actor_ppo_steps'] == 0
    assert model.critic_steps == metadata['critic_steps'] == bc.critic_steps+5120
    assert metadata['critic_onpolicy_steps'] == 5120
    assert model._n_updates == metadata['sb3_epoch_counter'] == 640
    assert model.actor_kl_stops == metadata['actor_kl_stops']
    history = read(folder/'optimizer-history.json')
    assert history == model.train_history and len(history) == 64
    assert sum(row['actor_steps_this_rollout'] for row in history) == model.actor_steps
    assert sum(row['critic_steps_this_rollout'] for row in history) == 5120
    assert all(row['critic_steps_this_rollout'] == 80 for row in history)
    assert sum(bool(row['kl_stopped']) for row in history) == model.actor_kl_stops
    checkpoints = []
    for step in (16384, 32768, 49152, 65536):
        checkpoint = IndependentPPO.load(folder/f'checkpoint-{step}.zip', device='cpu')
        # SB3 calls _on_step before training the just-completed rollout. The
        # endpoint policy.zip separately includes that last optimizer pass.
        completed_rollouts = step//1024-1
        assert checkpoint.num_timesteps == step
        assert checkpoint._n_updates == completed_rollouts*10
        assert checkpoint.actor_steps == sum(row['actor_steps_this_rollout'] for row in history[:completed_rollouts])
        assert checkpoint.critic_steps == warmup['critic_updates']+completed_rollouts*80
        checkpoints.append(dict(environment_steps=step, actor_steps=checkpoint.actor_steps,
            critic_steps=checkpoint.critic_steps, policy_sha256=digest(folder/f'checkpoint-{step}.zip')))
    dataset = np.load(DATA/'dataset/dataset.npz')
    assert metadata['bc_supervised_updates'] == 32*math.ceil(len(dataset['observations'])/128)
    warm_report, observations, returns = replay_trace(folder/'critic-warmup.jsonl',
        expected_steps=warmup['environment_steps'], rng_seed=90000+seed, complete_episodes=32,
        deterministic_actor=bc, replay_controllers=replay_controllers, keep_returns=True,
        progress_label=f'{seed}-warmup')
    assert warm_report['failures'] == warmup['failures']
    assert warmup['seed_namespace'] == 90000+seed
    assert warmup['critic_updates'] == 4*math.ceil(warm_report['rows']/128)
    supervised = rebuild_bc_and_warmup(seed, dataset, observations, returns, bc, folder)
    train_report, _, _ = replay_trace(folder/'training.jsonl', expected_steps=STEPS,
        rng_seed=seed, replay_controllers=replay_controllers, progress_label=str(seed))
    supervised.update(rebuild_continued(seed, dataset, bc, continued, continued_folder, model.actor_steps))
    result = dict(seed=seed, steps=STEPS, actor_adam_steps=model.actor_steps,
        critic_adam_steps=model.critic_steps, warmup_critic_adam_steps=warmup['critic_updates'],
        onpolicy_critic_adam_steps=5120, reserved_stock_adam_steps=0,
        actor_kl_stops=model.actor_kl_stops, training=train_report, critic_warmup=warm_report,
        supervised_controls=supervised, checkpoints=checkpoints, policy_sha256=metadata['policy_sha256'],
        scope='All physical, shadow, FIFO, NPC, reward rows replayed; BC and warmup optimizers reproduced. '
            'Full controller/query/guard replay is an explicit separate flag. Stochastic PPO SGD is not reproduced.')
    for name, expected in inputs.items():
        assert digest(ROOT/name) == expected, ('Audit input changed while running', name)
    write(cache, dict(passed=True, input_hashes=inputs, report=result))
    return result


def audit_dataset():
    protocol = source_protocol(DATA/'dataset')
    metadata = read(DATA/'dataset/manifest.json')
    assert protocol['contract'] == CONTRACT and protocol['actor_controller_kwargs'] == CONTROLLER_KWARGS
    assert digest(DATA/'dataset/dataset.npz') == metadata['dataset_sha256']
    assert protocol['teacher_quality_factor'] == 1. and protocol['no_legacy_weight_reinterpretation']
    teacher = DATA/'teacher-development72'
    teacher_protocol = source_protocol(teacher)
    assert digest(teacher/'protocol.json') == protocol['teacher_protocol_sha256']
    assert teacher_protocol['quality'] == 'anchor' and teacher_protocol['objective'] == 'mixed'
    data = np.load(DATA/'dataset/dataset.npz')
    dataset_x, dataset_y, dataset_w = (data[key] for key in ('observations', 'actions', 'weights'))
    count = nonzero = 0
    inputs = protocol['input_hashes']
    records = read(teacher/'summary.json')
    assert len(records) == 144
    for record in records:
        if record['mode'] != 'teacher':
            continue
        path = teacher/f'{record["case"]["id"]:03d}-teacher.jsonl'
        expected = digest(path)
        assert expected == record['raw_sha256'] == inputs[str(path.relative_to(ROOT))]
        for line in path.open():
            row = json.loads(line)
            x, y = (np.asarray(row[key], np.float32) for key in ('observation', 'label'))
            np.testing.assert_array_equal(x, dataset_x[count])
            np.testing.assert_array_equal(y, dataset_y[count])
            weight = 10. if np.max(abs(y)) > 1e-8 else 1.
            assert dataset_w[count] == weight
            nonzero += weight > 1.
            count += 1
    assert count == len(dataset_x) == metadata['samples']
    assert nonzero == metadata['nonzero_labels']
    assert metadata['source_teacher_failures'] == sum(r['failed'] for r in records if r['mode'] == 'teacher')
    declaration = read(DATA/'policies/declaration.json')
    assert declaration['seeds'] == list(SEEDS) and declaration['steps_per_seed'] == STEPS
    assert declaration['protocol_sha256'] == digest(Path(__file__).parent/'TRAINING_PROTOCOL.md')
    assert declaration['source_sha256'] == digest(Path(__file__).parent/'train.py')
    assert declaration['fresh_evaluation_not_opened']
    return dict(samples=count, nonzero_labels=int(nonzero), dataset_sha256=metadata['dataset_sha256'],
        input_teacher_failures=metadata['source_teacher_failures'], all_teacher_frames_preserved=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--replay-controllers', action='store_true', help='Also recompute every complete causal query and original guard decision')
    parser.add_argument('--reuse', action='store_true', help='Reuse only matching exact source/input-pinned seed proofs')
    args = parser.parse_args()
    dataset = audit_dataset()
    summaries = read(DATA/'policies/summary.json')
    continued = read(DATA/'continued-bc/summary.json')
    assert sorted(row['seed'] for row in summaries) == sorted(row['seed'] for row in continued) == list(SEEDS)
    for row in summaries:
        assert row == read(DATA/f'policies/seed-{row["seed"]}/manifest.json')
    for row in continued:
        assert row == read(DATA/f'continued-bc/seed-{row["seed"]}/manifest.json')
    with ProcessPoolExecutor(max_workers=3, mp_context=mp.get_context('spawn')) as pool:
        results = [future.result() for future in as_completed([
            pool.submit(audit_seed, seed, args.replay_controllers, args.reuse) for seed in SEEDS])]
    results.sort(key=lambda result: result['seed'])
    audit_inputs = {str(path.relative_to(ROOT)): digest(path) for path in (
        DATA/'policies/declaration.json', DATA/'policies/summary.json', DATA/'continued-bc/summary.json',
        DATA/'dataset/protocol.json', DATA/'dataset/manifest.json', DATA/'dataset/dataset.npz',
        *(DATA/f'audits/training-seed-{seed}-{digest(__file__)[:12]}-controllers-{int(args.replay_controllers)}.json' for seed in SEEDS))}
    report = dict(passed=True, seeds=results, dataset=dataset, training_steps=sum(r['steps'] for r in results),
        all_failures_preserved=sum(r['training']['failures'] for r in results),
        full_controller_query_guard_replayed=args.replay_controllers,
        verifier_sha256=digest(__file__), input_hashes=audit_inputs, performance_promotion_claimed=False,
        limitation='Logical numerical replay does not establish wall-time deadlines, native Webots transfer or requested PPO improvement.')
    write(DATA/'training-verification.json', report)
    print('V13 ALL TRAINING PHYSICS/REWARDS/OPTIMIZERS VERIFIED', report['training_steps'], flush=True)


if __name__ == '__main__':
    main()
