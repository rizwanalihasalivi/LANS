"""Independent audit rejects altered physics, finite scores and causal records."""
import json

import numpy as np
import pytest

from .learning import Env
from .train import CONTROLLER_KWARGS
from .verify_training import replay_trace


def case(delay=0., failure=False):
    return dict(stage='audit-unit-fixture', scenario='following', speed=8., delay=delay,
        mirror=1, stiffness=.85, lateral=.25, heading=.01, phase=12., amplitude=1.1,
        network='nominal', network_seed=1001,
        npc_x_shift=-30. if failure else 0., npc_speed_scale=1.)


def trace(path, fixture, steps):
    env = Env(trace=path, controller_kwargs=CONTROLLER_KWARGS)
    try:
        env.reset(options={'case': fixture})
        for _ in range(steps):
            _, _, done, _, _ = env.step(np.linspace(-.1, .1, 8, dtype=np.float32))
            if done:
                break
    finally:
        env.close()


@pytest.mark.parametrize('delay', [0., .05, .1])
def test_delayed_partial_rollout_replays_current_queries_and_physics(tmp_path, delay):
    path = tmp_path/'partial.jsonl'
    fixture = case(delay)
    trace(path, fixture, 2)
    report, _, _ = replay_trace(path, expected_steps=2, expected_cases=[fixture], replay_controllers=True)
    assert report['final_partial_episode'] == 1 and report['complete_episodes'] == 0
    assert report['failures'] == 0 and report['full_controller_query_guard_replayed']


def test_failed_episode_retains_every_unrun_tick_penalty(tmp_path):
    path = tmp_path/'failed.jsonl'
    fixture = case(failure=True)
    trace(path, fixture, 1)
    report, observations, returns = replay_trace(path, expected_steps=1,
        expected_cases=[fixture], complete_episodes=1, keep_returns=True, replay_controllers=True)
    row = json.loads(path.read_text())
    assert report['failures'] == 1 and report['final_partial_episode'] == 0
    assert row['score_error_sq'] == row['error']**2+119*6.25
    assert observations.shape == (1, 55) and returns.shape == (1,)
    assert returns[0] == np.float32(row['reward'])
    assert report['failed_episodes'][0]['collision']


@pytest.mark.parametrize('corruption', ['plant', 'shadow', 'reward', 'penalty', 'history', 'terminal', 'missing_row'])
def test_audit_rejects_material_record_corruption(tmp_path, corruption):
    path = tmp_path/'failed.jsonl'
    fixture = case(failure=True)
    trace(path, fixture, 1)
    row = json.loads(path.read_text())
    if corruption == 'plant':
        row['state_after'][1] += .01
    elif corruption == 'shadow':
        row['shadow_after'][1] += .01
    elif corruption == 'reward':
        row['reward_parts']['rmse_reward'] += 1.
    elif corruption == 'penalty':
        row['score_error_sq'] -= 6.25
    elif corruption == 'history':
        row['observation_next'][52] += .1
    elif corruption == 'terminal':
        row['truncated'] = True
    path.write_text('' if corruption == 'missing_row' else json.dumps(row)+'\n')
    with pytest.raises(AssertionError):
        replay_trace(path, expected_steps=1, expected_cases=[fixture], complete_episodes=1)
