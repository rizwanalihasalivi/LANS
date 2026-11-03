"""Read-only native sensor/message audit; never copies Python simulation metrics."""
import argparse
import json
import math
from pathlib import Path
from integrations.connected_v2v.demo import digest
from integrations.connected_v2v.messages import decode_beacon
from integrations.connected_v2v.node import V2VEndpoint
from integrations.connected_v2v.platoon import FollowingConfig, PlatoonController


def verify(output):
    output = Path(output)
    provenance = json.loads((output/'provenance.json').read_text())
    root = Path(__file__).resolve().parents[3]
    for name, expected in provenance['sources'].items():
        assert digest(root/name) == expected, ('Source changed', name)
    assert digest(output/'project/worlds/connected_convoy.wbt') == provenance['world_sha256']
    traces, summaries, hashes = {}, {}, {}
    for name, predecessor in [('leader', None), ('follower-1', 'leader'), ('follower-2', 'follower-1')]:
        rows = [json.loads(line) for line in (output/f'{name}.jsonl').read_text().splitlines()]
        summary = json.loads((output/f'{name}-summary.json').read_text())
        assert len(rows) == summary['samples'] >= 200, ('Incomplete native run', name)
        assert rows[-1]['time_s'] >= 12.-1e-8
        endpoint = V2VEndpoint(name, expected_peers=[predecessor] if predecessor else ())
        follower = PlatoonController(endpoint, predecessor, following=FollowingConfig(cruise_speed_m_s=8.))
        events = [json.loads(line) for line in (output/f'{name}-receipts.jsonl').read_text().splitlines()]
        last_t, last_steering, last_speed, event_index = 0., 0., 0., 0
        for index, row in enumerate(rows):
            assert row['sample'] == index and row['vehicle_id'] == name
            assert math.isclose(row['time_s']-last_t, .05, abs_tol=1e-8)
            assert all(math.isfinite(v) for v in row['state'])
            now = row['time_s']
            endpoint.observe_local(row['state'], now, now)
            while event_index < len(events) and events[event_index]['received_s'] <= now+1e-9:
                event = events[event_index]
                assert event['received_s'] == now
                payload = event['message'].encode('utf-8')
                beacon = decode_beacon(payload)
                assert beacon.vehicle_id != name
                assert endpoint.receive(payload, now) == event['accepted']
                event_index += 1
            assert endpoint.peers(now) == row['peers'], 'Native peer-history replay mismatch'
            scheduled = -2. if name == 'leader' and 7. <= now < 8. else None
            command, decision = follower.decide(now, leader_accel=scheduled)
            assert decision == row['decision'], 'Native cooperative-decision replay mismatch'
            assert math.isclose(command.steering, row['command']['steering'], abs_tol=1e-10)
            assert math.isclose(command.accel, row['command']['accel'], abs_tol=1e-10)
            target = max(0., min(8., last_speed+command.accel*.05))
            assert math.isclose(target, row['commanded_speed_m_s'], abs_tol=1e-10)
            assert row['state'][3] >= 0 and abs(row['command']['steering']) <= .5+1e-9
            assert abs(row['command']['steering']-last_steering) <= .6*.05+1e-9
            assert -6. <= row['command']['accel'] <= 2.5
            stale = [peer for peer, status in row['peers'].items() if status['status'] != 'fresh']
            if stale:
                assert row['command']['accel'] == -6. and row['decision']['risk'] == 'DANGER'
                assert set(stale) <= set(row['decision']['missing'])
            last_t, last_steering = row['time_s'], row['command']['steering']
            last_speed = row['commanded_speed_m_s']
        assert event_index == len(events) == summary['received'] and endpoint.accepted == summary['accepted'] > 20
        assert dict(endpoint.rejections) == summary['rejections']
        assert endpoint.peers(rows[-1]['time_s']) == summary['final_peers']
        assert len(endpoint.expected) == 2, ('Native multi-peer discovery did not execute', name)
        assert rows[-1]['state'][0] > rows[0]['state'][0]+1., ('Vehicle did not move', name)
        traces[name], summaries[name] = rows, summary
        for suffix in ['.jsonl', '-receipts.jsonl', '-summary.json']:
            hashes[name+suffix] = digest(output/(name+suffix))
    length = min(len(rows) for rows in traces.values())
    minimum = min(traces[front][i]['state'][0]-traces[back][i]['state'][0]-4.6
                  for front, back in [('leader', 'follower-1'), ('follower-1', 'follower-2')] for i in range(length))
    assert minimum > 0., 'Conservative longitudinal gap proxy violated'
    if provenance['case'] == 'peer_blackout':
        assert summaries['follower-1']['muted_broadcasts'] > 0
        assert any('follower-1' in row['decision']['missing'] and 5.4 <= row['time_s'] < 6.5
                   for row in traces['follower-2']), 'Blackout fallback was not exercised'
        assert summaries['follower-2']['final_peers']['follower-1']['status'] == 'fresh'
        assert summaries['follower-2']['final_decision']['source'] == 'cooperative_following'
    return dict(passed=True, case=provenance['case'], vehicles=3,
                native_samples=sum(len(rows) for rows in traces.values()),
                replayed_radio_messages=sum(s['received'] for s in summaries.values()),
                min_longitudinal_gap_proxy_m=minimum,
                fallback_samples={name:s['fallback_samples'] for name, s in summaries.items()},
                files=hashes, scope='native radio/driver integration only; no physical safety or real-time guarantee')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    print(json.dumps(verify(parser.parse_args().output), indent=2))
