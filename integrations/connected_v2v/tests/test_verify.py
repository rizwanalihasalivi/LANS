import json
import pytest
from integrations.connected_v2v.demo import run_case, digest
from integrations.connected_v2v.platoon_demo import run_case as platoon_case
from integrations.connected_v2v.verify import verify_case


def test_receiver_physics_audit_rejects_rehashed_trajectory_tampering(tmp_path):
    output = tmp_path/'run'
    run_case('nominal', 2.5, 42, output)
    assert verify_case(output)['vehicle_ticks'] == 150
    path = output/'ticks.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]['state_after'][0] += .2
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    summary = json.loads((output/'summary.json').read_text())
    summary['files']['ticks.jsonl'] = digest(path)
    (output/'summary.json').write_text(json.dumps(summary))
    with pytest.raises(AssertionError, match='Physics replay mismatch'):
        verify_case(output)


def test_platoon_audit_replays_communication_and_exact_following_commands(tmp_path):
    output = tmp_path/'platoon'
    platoon_case('predecessor_blackout', 4., 42, output)
    assert verify_case(output)['vehicle_ticks'] == 240
