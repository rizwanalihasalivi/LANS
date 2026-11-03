import json
import pytest
from .study import digest, replay, run_episode


def test_closed_loop_replay_is_deterministic_without_membership_events(tmp_path):
    a, b = tmp_path/'a', tmp_path/'b'
    run_episode(a, 'nonconnected', 101, seconds=1.)
    run_episode(b, 'nonconnected', 101, seconds=1.)
    assert digest(a/'ticks.jsonl') == digest(b/'ticks.jsonl')
    assert replay(a)['ticks'] == 20
    assert 'membership' not in (a/'ticks.jsonl').read_text()


@pytest.mark.parametrize('field', ['after', 'decision', 'summary'])
def test_replay_rejects_rehashed_corruption(tmp_path, field):
    run_episode(tmp_path/'run', 'connected', 101, seconds=.5)
    root = tmp_path/'run'
    rows = [json.loads(s) for s in (root/'ticks.jsonl').read_text().splitlines()]
    summary = json.loads((root/'summary.json').read_text())
    if field == 'after':
        rows[0]['after'][0] += .1
    elif field == 'decision':
        rows[0]['decision']['selected_target'] = 'fabricated'
    else:
        summary['progress_m'] += 1.
    (root/'ticks.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    summary['raw_sha256'] = digest(root/'ticks.jsonl')
    (root/'summary.json').write_text(json.dumps(summary))
    with pytest.raises(AssertionError):
        replay(root)


@pytest.mark.parametrize('case,seed', [('nonconnected', 101), ('loss_jitter', 203)])
def test_adjacent_stopping_guard_regression_through_complete_cut_in_and_out(tmp_path, case, seed):
    result = run_episode(tmp_path/case, case, seed)
    assert result['passed'] and result['collisions'] == 0
