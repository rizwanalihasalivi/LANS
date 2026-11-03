"""Read-only replay of receiver history, supervisor decisions and bicycle motion."""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import numpy as np
from integrations.unified_lans.physics import Command, Config, advance, Route
from integrations.unified_lans.traffic import Supervisor
from .demo import digest, CASES as AWARENESS_CASES
from .node import V2VEndpoint
from .messages import decode_beacon
from .platoon import FollowingConfig, PlatoonController
from .platoon_demo import CASES as PLATOON_CASES


def records(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def verify_case(output):
    output = Path(output)
    summary = json.loads((output/'summary.json').read_text())
    for name in ['ticks.jsonl', 'deliveries.jsonl']:
        assert digest(output/name) == summary['files'][name], ('File checksum mismatch', name)
    rows, events = records(output/'ticks.jsonl'), records(output/'deliveries.jsonl')
    cfg = Config()
    assert summary['config'] == asdict(cfg), 'Control configuration changed'
    platoon = 'following' in summary
    if platoon:
        assert summary['following'] == asdict(FollowingConfig())
        assert summary['case'] in PLATOON_CASES
        names = ['leader', 'follower-1', 'follower-2']
        roster = {name:names[i-1:i] if i else [] for i, name in enumerate(names)}
    else:
        assert summary['case'] in AWARENESS_CASES
        names = ['vehicle-a', 'vehicle-b', 'vehicle-c']
        if summary['case'] == 'late_join':
            names.append('vehicle-d')
        assert summary['vehicles'] == names
        roster = {name:set(names[:3])-{name} for name in names}
    nodes = {name:V2VEndpoint(name, expected_peers=roster[name]) for name in names}
    controllers = ({name:PlatoonController(nodes[name], names[i-1] if i else None)
                    for i, name in enumerate(names)} if platoon else {})
    supervisors = {name:Supervisor(cfg, 'following') for name in names}
    previous_state, previous_command = {}, {name:Command() for name in names}
    row_index = event_index = 0
    fallback_count = collision_count = corridor_count = 0
    gaps, gap_errors = [], []
    for tick in range(round(summary['seconds']/cfg.dt)):
        now = tick*cfg.dt
        active = [name for name in names if name != 'vehicle-d' or now >= 1.]
        frame = rows[row_index:row_index+len(active)]
        assert [row['vehicle_id'] for row in frame] == active, 'Incomplete fleet frame'
        for row in frame:
            name = row['vehicle_id']
            assert row['tick'] == tick and row['time_s'] == now
            assert np.isfinite(row['state_before']).all() and np.isfinite(row['state_after']).all()
            if name in previous_state:
                np.testing.assert_allclose(row['state_before'], previous_state[name], rtol=0, atol=1e-10)
            nodes[name].observe_local(row['state_before'], now, now)
        while event_index < len(events) and events[event_index]['received_s'] <= now+1e-9:
            event = events[event_index]
            assert event['received_s'] == now and event['receiver'] in active and event['sender'] in active
            assert event['observed_s'] <= event['scheduled_s']+1e-9 <= now+2e-9
            assert math.isclose(event['age_s'], now-event['observed_s'], abs_tol=1e-10)
            payload = event['message'].encode('utf-8'); beacon = decode_beacon(payload)
            assert (beacon.vehicle_id, beacon.sequence, beacon.observed_s) == (event['sender'], event['sequence'], event['observed_s'])
            assert nodes[event['receiver']].receive(payload, now) == event['accepted'], 'Receiver replay mismatch'
            event_index += 1
        for i, row in enumerate(frame):
            name, decision = row['vehicle_id'], row['decision']
            node = nodes[name]
            assert node.peers(now) == row['peers'], 'Peer age/discovery replay mismatch'
            if platoon:
                scheduled = -3. if summary['case'] == 'leader_brake' and name == 'leader' and 2. <= now < 3. else None
                command, replay = controllers[name].decide(now, leader_accel=scheduled)
                np.testing.assert_allclose([row['command']['steering'], row['command']['accel']],
                                           [command.steering, command.accel], rtol=0, atol=1e-10)
                assert replay == decision, 'Cooperative-following replay mismatch'
                fallback_count += decision['source'] == 'fallback_brake'
                if i:
                    gap = frame[i-1]['state_after'][0]-row['state_after'][0]-2*cfg.vehicle_radius
                    assert math.isclose(gap, row['true_gap_m'], abs_tol=1e-10)
                    gaps.append(gap)
                    gap_errors.append(gap-FollowingConfig().standstill_gap_m-FollowingConfig().time_headway_s*row['state_after'][3])
                    collision_count += gap <= 0
            else:
                risk = supervisors[name].assess(np.array(row['state_before']), node.inbox, node.expected, now, now)
                assert (risk.state, list(risk.missing), risk.critical_id) == (decision['risk'], decision['missing'], decision['critical_id'])
                command = Command(row['applied_steering'], row['applied_accel'])
                assert command == Command(decision['issued_steering'], decision['issued_accel'])
                stale = {peer for peer, status in row['peers'].items() if status['status'] != 'fresh'}
                if stale:
                    assert stale <= set(decision['missing']) and command.accel == -cfg.max_brake
                    assert decision['source'] == 'lqr' and decision['risk'] == 'DANGER'
                    fallback_count += 1
                distance = min(np.linalg.norm(np.array(other['state_after'][:2])-row['state_after'][:2])
                               for other in frame if other is not row)-2*cfg.vehicle_radius
                collision = bool(distance <= 0)
                corridor = abs(row['state_after'][1]) > 1.75
                assert collision == row['truth_metrics']['collision'] and corridor == row['truth_metrics']['corridor_exceeded']
                collision_count += collision; corridor_count += corridor
            assert abs(command.steering) <= cfg.steering_limit+1e-9
            assert abs(command.steering-previous_command[name].steering) <= cfg.steering_rate*cfg.dt+1e-9
            assert -cfg.max_brake <= command.accel <= cfg.max_accel
            np.testing.assert_allclose(advance(row['state_before'], command, cfg.dt), row['state_after'],
                                       rtol=0, atol=1e-10, err_msg='Physics replay mismatch')
            previous_state[name], previous_command[name] = row['state_after'], command
        row_index += len(active)
    assert row_index == len(rows) and event_index == len(events), 'Trailing or missing records'
    assert len(rows) == summary['vehicle_ticks' if platoon else 'control_ticks']
    assert len(events) == summary['channel']['delivered']
    if platoon:
        assert collision_count == summary['collision_follower_ticks']
        assert fallback_count == summary['fallback_vehicle_ticks']
        assert math.isclose(min(gaps), summary['min_true_gap_m'], abs_tol=1e-10)
        assert math.isclose(float(np.sqrt(np.mean(np.square(gap_errors)))), summary['follower_spacing_error_rms_m'], abs_tol=1e-10)
    else:
        assert collision_count == summary['collision_vehicle_ticks'] and corridor_count == summary['corridor_vehicle_ticks']
        assert fallback_count == summary['stale_fallback_vehicle_ticks']
        for name, node in nodes.items():
            expected = summary['endpoints'][name]
            assert node.peers(now) == expected['peers']
            assert node.received == expected['received'] and node.accepted == expected['accepted']
            assert dict(node.rejections) == expected['rejections']
    return dict(passed=True, case=summary['case'], vehicle_ticks=len(rows), delivery_events=len(events),
                scope='receiver/control-contract and shared-dynamics replay, not independent physical validation')


def verify(output):
    output = Path(output)
    provenance = json.loads((output/'provenance.json').read_text())
    root = Path(__file__).resolve().parents[2]
    for name, expected in provenance['sources'].items():
        path = root/name
        assert path.resolve().is_relative_to(root.resolve()), 'Source path escapes repository'
        assert digest(path) == expected, ('Source changed', name)
    summary = json.loads((output/'summary.json').read_text())
    assert summary and len({row['case'] for row in summary}) == len(summary), 'Missing/duplicate cases'
    results = []
    for row in summary:
        assert row['case'] in set(AWARENESS_CASES) | set(PLATOON_CASES)
        assert json.loads((output/row['case']/'summary.json').read_text()) == row
        results.append(verify_case(output/row['case']))
    return dict(passed=True, cases=results, vehicle_ticks=sum(r['vehicle_ticks'] for r in results),
                delivery_events=sum(r['delivery_events'] for r in results))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    print(json.dumps(verify(parser.parse_args().output), indent=2))
