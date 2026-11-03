"""Bounded connected-fleet development smoke; not a controller promotion study."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import numpy as np
from integrations.unified_lans.controller import Pipeline
from integrations.unified_lans.physics import Config, Route
from integrations.unified_lans.run import clean
from integrations.unified_lans.simulation import truth_metrics
from .network import Link, SimulatedChannel
from .node import V2VEndpoint

CASES = ('nominal', 'loss_jitter', 'peer_blackout', 'late_join')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(clean(data), indent=2, allow_nan=False) + '\n')


def run_case(case, seconds, seed, output):
    cfg, route = Config(), Route()
    count = round(seconds/cfg.dt)
    if case not in CASES or count < 50 or abs(seconds-count*cfg.dt) > 1e-9:
        raise ValueError('known case and >=2.5 seconds in complete control ticks required')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    names = ['vehicle-a', 'vehicle-b', 'vehicle-c']
    if case == 'late_join':
        names.append('vehicle-d')
    states = {name: np.array([30.*i, .05*(-1)**i, 0., 10. if i == 0 else 8., 0., 0.])
              for i, name in enumerate(names)}
    pipelines = {name: Pipeline(route, mode='lqr', cfg=cfg, target_speed=float(states[name][3]))
                 for name in names}
    nodes = {name: V2VEndpoint(name, inbox=pipelines[name].inbox,
                              expected_peers=set(names[:3])-{name}, max_packet_age_s=cfg.traffic_ttl)
             for name in names}
    links = {}
    default = Link()
    if case == 'loss_jitter':
        default = Link(delay_s=.05, jitter_s=.1, loss=.2, duplicate=.2)
    if case == 'peer_blackout':
        links = {('vehicle-b', other): Link(blackout=((1., 2.),)) for other in names if other != 'vehicle-b'}
    channel = SimulatedChannel(seed, default=default, links=links)
    telemetry, deliveries = [], []
    stale_fallbacks = 0
    for tick in range(count):
        now = tick*cfg.dt
        active = [name for name in names if name != 'vehicle-d' or now >= 1.]
        for name in active:
            nodes[name].observe_local(states[name], now, now)
        # 10 Hz broadcasts and 20 Hz control are separate, declared schedules.
        if tick % 2 == 0:
            for sender in active:
                payload = nodes[sender].publish(states[sender], now, now)
                for receiver in active:
                    if sender != receiver:
                        distance = float(np.linalg.norm(states[sender][:2]-states[receiver][:2]))
                        channel.transmit(sender, receiver, payload, now, distance_m=distance)
        deliveries.extend(channel.deliver(now, {name: nodes[name] for name in active}))
        after = {}
        for name in active:
            node, pipe = nodes[name], pipelines[name]
            node.sync_expected(pipe)
            peers = node.peers(now)
            before, previous = states[name].copy(), pipe.applied
            decision = pipe.decide(now)
            after[name] = pipe.apply(now, before)
            rate = (pipe.applied.steering-previous.steering)/cfg.dt
            assert abs(rate) <= cfg.steering_rate + 1e-9
            assert abs(pipe.applied.steering) <= cfg.steering_limit + 1e-9
            assert -cfg.max_brake <= pipe.applied.accel <= cfg.max_accel
            stale = {peer for peer, status in peers.items() if status['status'] != 'fresh'}
            if stale:
                assert stale <= set(decision['missing'])
                assert decision['risk'] == 'DANGER' and decision['source'] == 'lqr'
                assert decision['issued_accel'] == -cfg.max_brake
                stale_fallbacks += 1
            telemetry.append(dict(vehicle_id=name, tick=tick, time_s=now, peers=peers,
                                  state_before=before.tolist(), state_after=after[name].tolist(),
                                  applied_steering=pipe.applied.steering,
                                  applied_accel=pipe.applied.accel, steering_rate=rate,
                                  decision=decision))
        # Simultaneous update: iteration order cannot expose a peer's future state.
        states.update(after)
        for row in telemetry[-len(active):]:
            others = {name: states[name] for name in active if name != row['vehicle_id']}
            row['truth_metrics'] = truth_metrics(states[row['vehicle_id']], others, route, cfg)
    for filename, rows in [('ticks.jsonl', telemetry), ('deliveries.jsonl', deliveries)]:
        (output/filename).write_text(''.join(json.dumps(clean(r), allow_nan=False)+'\n' for r in rows))
    final_time = (count-1)*cfg.dt
    summary = dict(case=case, seed=seed, seconds=seconds, config=asdict(cfg), vehicles=names,
                   initially_expected=names[:3], delayed_join_s=1. if case == 'late_join' else None,
                   control_ticks=len(telemetry), delivery_events=len(deliveries),
                   collision_vehicle_ticks=sum(bool(r['truth_metrics']['collision']) for r in telemetry),
                   corridor_vehicle_ticks=sum(bool(r['truth_metrics']['corridor_exceeded']) for r in telemetry),
                   stale_fallback_vehicle_ticks=stale_fallbacks,
                   channel=dict(attempted=channel.attempted, scheduled=channel.scheduled,
                                delivered=channel.delivered, pending=channel.pending,
                                dropped=dict(channel.dropped)),
                   endpoints={name:dict(accepted=node.accepted, received=node.received,
                                        rejections=dict(node.rejections), peers=node.peers(final_time))
                              for name, node in nodes.items()},
                   files={name:digest(output/name) for name in ['ticks.jsonl', 'deliveries.jsonl']},
                   scope='logical-time connected-awareness development smoke, not performance promotion or radio validation')
    if case == 'peer_blackout':
        assert stale_fallbacks > 0, 'blackout did not exercise missing-peer fallback'
        assert all(node.peers(final_time)['vehicle-b']['status'] == 'fresh'
                   for name, node in nodes.items() if name != 'vehicle-b'), 'peer did not recover'
    if case == 'late_join':
        assert all('vehicle-d' in node.expected for name, node in nodes.items() if name != 'vehicle-d')
    write(output/'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--case', choices=CASES, default='nominal')
    parser.add_argument('--suite', action='store_true')
    parser.add_argument('--seconds', type=float, default=3.)
    parser.add_argument('--seed', type=int, default=20261103)
    args = parser.parse_args()
    cfg = Config()
    if not np.isfinite(args.seconds) or args.seconds < 2.5 or abs(args.seconds/cfg.dt-round(args.seconds/cfg.dt)) > 1e-8:
        parser.error('--seconds must be >=2.5 and a multiple of 0.05')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    files = [*Path(__file__).parent.glob('*.py'),
             *Path('integrations/unified_lans').glob('*.py'),
             Path('controllers/lqr_controller.py'), Path('models/bicycle_model.py')]
    write(output/'provenance.json', dict(python=platform.python_version(), seed=args.seed,
                                        sources={str(p):digest(p) for p in files},
                                        control_mode='unchanged LQR with existing V2V risk supervisor',
                                        traffic_clock='shared logical clock; clock synchronization not validated'))
    summaries = []
    for case in CASES if args.suite else [args.case]:
        summary = run_case(case, args.seconds, args.seed, output/case)
        summaries.append(summary)
        print(json.dumps(dict(case=case, vehicle_ticks=summary['control_ticks'],
                              delivery_events=summary['delivery_events'],
                              stale_fallbacks=summary['stale_fallback_vehicle_ticks'],
                              collisions=summary['collision_vehicle_ticks'],
                              corridor=summary['corridor_vehicle_ticks'])), flush=True)
    write(output/'summary.json', summaries)


if __name__ == '__main__':
    main()
