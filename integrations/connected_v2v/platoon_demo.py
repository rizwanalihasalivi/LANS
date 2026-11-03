"""Three vehicles, lead braking and V2V faults on a straight simulated road."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import numpy as np
from integrations.unified_lans.physics import Config, advance
from integrations.unified_lans.run import clean
from .demo import digest, write
from .network import Link, SimulatedChannel
from .node import V2VEndpoint
from .platoon import FollowingConfig, PlatoonController

CASES = ('nominal', 'leader_brake', 'predecessor_blackout', 'loss_jitter')


def run_case(case, seconds, seed, output):
    cfg, settings = Config(), FollowingConfig()
    if case not in CASES or not np.isfinite(seconds) or seconds < 4. or abs(seconds/cfg.dt-round(seconds/cfg.dt)) > 1e-8:
        raise ValueError('known case, >=4 seconds and complete 50 ms ticks required')
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    names = ['leader', 'follower-1', 'follower-2']
    spacing = 2*cfg.vehicle_radius+settings.standstill_gap_m+settings.time_headway_s*settings.cruise_speed_m_s
    states = {name:np.array([-i*spacing, 0., 0., settings.cruise_speed_m_s, 0., 0.]) for i, name in enumerate(names)}
    nodes = {name:V2VEndpoint(name, expected_peers=names[i-1:i] if i else ()) for i, name in enumerate(names)}
    controllers = {name:PlatoonController(nodes[name], names[i-1] if i else None) for i, name in enumerate(names)}
    default = Link(delay_s=.05)
    links = {}
    if case == 'loss_jitter':
        default = Link(delay_s=.05, jitter_s=.08, loss=.2, duplicate=.1)
    if case == 'predecessor_blackout':
        links[('leader', 'follower-1')] = Link(delay_s=.05, blackout=((1., 2.5),))
    channel = SimulatedChannel(seed, default=default, links=links)
    rows, deliveries = [], []
    for tick in range(round(seconds/cfg.dt)):
        now = tick*cfg.dt
        for name in names:
            nodes[name].observe_local(states[name], now, now)
        if tick % 2 == 0:
            for i, sender in enumerate(names[:-1]):
                message = nodes[sender].publish(states[sender], now, now)
                channel.transmit(sender, names[i+1], message, now,
                                 distance_m=float(np.linalg.norm(states[sender][:2]-states[names[i+1]][:2])))
        deliveries.extend(channel.deliver(now, nodes))
        after = {}
        for name in names:
            acceleration = -3. if case == 'leader_brake' and 2. <= now < 3. else None
            command, decision = controllers[name].decide(now, leader_accel=acceleration if name == 'leader' else None)
            after[name] = advance(states[name], command, cfg.dt)
            rows.append(dict(vehicle_id=name, tick=tick, time_s=now, state_before=states[name].tolist(),
                             state_after=after[name].tolist(), command=asdict(command), decision=decision,
                             peers=nodes[name].peers(now)))
        states.update(after)
        for i, row in enumerate(rows[-3:]):
            row['true_gap_m'] = float(states[names[i-1]][0]-states[names[i]][0]-2*cfg.vehicle_radius) if i else None
    for filename, records in [('ticks.jsonl', rows), ('deliveries.jsonl', deliveries)]:
        (output/filename).write_text(''.join(json.dumps(clean(r), allow_nan=False)+'\n' for r in records))
    summary = dict(case=case, seconds=seconds, seed=seed, config=asdict(cfg), following=asdict(settings),
                   vehicle_ticks=len(rows), min_true_gap_m=min(r['true_gap_m'] for r in rows if r['true_gap_m'] is not None),
                   collision_follower_ticks=sum(r['true_gap_m'] is not None and r['true_gap_m'] <= 0 for r in rows),
                   fallback_vehicle_ticks=sum(r['decision']['source'] == 'fallback_brake' for r in rows),
                   follower_spacing_error_rms_m=float(np.sqrt(np.mean([
                       (r['true_gap_m']-settings.standstill_gap_m-settings.time_headway_s*r['state_after'][3])**2
                       for r in rows if r['true_gap_m'] is not None]))),
                   channel=dict(attempted=channel.attempted, delivered=channel.delivered, pending=channel.pending,
                                dropped=dict(channel.dropped)),
                   files={name:digest(output/name) for name in ['ticks.jsonl', 'deliveries.jsonl']},
                   scope='straight-road cooperative-following development smoke; no string-stability or superiority claim')
    if case == 'predecessor_blackout':
        first = [r for r in rows if r['vehicle_id'] == 'follower-1']
        assert any(r['decision']['source'] == 'fallback_brake' and 1.4 <= r['time_s'] < 2.5 for r in first)
        assert first[-1]['decision']['source'] == 'cooperative_following'
    write(output/'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--suite', action='store_true')
    parser.add_argument('--case', choices=CASES, default='nominal')
    parser.add_argument('--seconds', type=float, default=8.)
    parser.add_argument('--seed', type=int, default=20261103)
    args = parser.parse_args()
    if not np.isfinite(args.seconds) or args.seconds < 4 or abs(args.seconds/.05-round(args.seconds/.05)) > 1e-8:
        parser.error('use >=4 seconds in complete 50 ms ticks')
    output = Path(args.output); output.mkdir(parents=True, exist_ok=False)
    files = [*Path(__file__).parent.glob('*.py'), *Path('integrations/unified_lans').glob('*.py'),
             Path('controllers/lqr_controller.py'), Path('models/bicycle_model.py')]
    write(output/'provenance.json', dict(sources={str(p):digest(p) for p in files},
                                        simulation='shared-clock bicycle, ideal local sensing, predecessor-only unicast',
                                        seed=args.seed))
    summaries = []
    for case in CASES if args.suite else [args.case]:
        summary = run_case(case, args.seconds, args.seed, output/case)
        summaries.append(summary)
        print(json.dumps(summary, allow_nan=False), flush=True)
    write(output/'summary.json', summaries)


if __name__ == '__main__':
    main()
