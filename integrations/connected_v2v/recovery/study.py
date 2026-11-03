"""Matched development trials. Truth is confined to sensor generation/scoring."""
from dataclasses import asdict
import heapq
import json
from pathlib import Path
import numpy as np
from integrations.connected_v2v.demo import write, digest
from integrations.connected_v2v.network import Link, SimulatedChannel
from integrations.connected_v2v.node import V2VEndpoint
from integrations.connected_v2v.platoon import FollowingConfig
from integrations.unified_lans.physics import Config, advance
from integrations.unified_lans.run import clean
from .controller import FusionFollower, RangeObservation

SCENARIOS = ('nominal', 'leader_brake', 'v2v_blackout', 'radar_blackout',
             'dual_blackout', 'loss_jitter', 'ego_blackout', 'cut_in')
NAMES = ('leader', 'follower-1', 'follower-2')


def run_episode(output, scenario, method, speed, seed, *, seconds=20., shift=0., perturb=True):
    if scenario not in SCENARIOS or seconds < 4. or abs(seconds/.05-round(seconds/.05)) > 1e-8:
        raise ValueError('known scenario, >=4 s and complete control ticks required')
    cfg, following = Config(), FollowingConfig(cruise_speed_m_s=float(speed))
    rng = np.random.default_rng(seed)
    sensor_rng = {name:np.random.default_rng(seed+100+i) for i, name in enumerate(NAMES)}
    distance = 2*cfg.vehicle_radius+following.standstill_gap_m+following.time_headway_s*speed
    states = {name:np.array([-i*distance+(float(rng.uniform(-.2,.2)) if perturb and i else 0.),
                            0., 0., speed, 0., 0.]) for i, name in enumerate(NAMES)}
    nodes = {name:V2VEndpoint(name) for name in [*NAMES, 'cut-in']}
    followers = {name:FusionFollower(nodes[name], NAMES[i-1] if i else None,
                                     method=method, following=following) for i, name in enumerate(NAMES)}
    default = Link(delay_s=.05)
    if scenario == 'loss_jitter':
        default = Link(delay_s=.05, jitter_s=.12, loss=.3, duplicate=.2)
    links = {}
    if scenario in ('v2v_blackout', 'dual_blackout'):
        links[('leader', 'follower-1')] = Link(delay_s=.05, blackout=((1.+shift, 2.5+shift),))
    channel = SimulatedChannel(seed, default=default, links=links)
    radar_queue, radar_seq, serial = [], {name:0 for name in NAMES}, 0
    path = Path(output); path.mkdir(parents=True, exist_ok=False)
    initial = {name:state.tolist() for name, state in states.items()}
    write(path/'case.json', dict(scenario=scenario, method=method, speed=speed, seed=seed,
                                seconds=seconds, shift=shift, perturb=perturb,
                                initial=initial, following=asdict(following), config=asdict(cfg)))
    rows = []
    for tick in range(round(seconds/cfg.dt)):
        now = tick*cfg.dt
        membership = {}
        if scenario == 'cut_in' and tick == round((3.+shift)/cfg.dt):
            states['cut-in'] = np.array([(states['leader'][0]+states['follower-1'][0])/2,
                                        3.5, 0., max(2., speed-2.), 0., 0.])
        if scenario == 'cut_in' and tick in [round((3.5+shift)/cfg.dt), round((12.5+shift)/cfg.dt)]:
            target = 'cut-in' if tick == round((3.5+shift)/cfg.dt) else 'leader'
            followers['follower-1'].retarget(target)
            membership['follower-1'] = target
        local = {}
        for name in NAMES:
            lost = scenario == 'ego_blackout' and name == 'follower-1' and 1.+shift <= now < 1.6+shift
            if not lost:
                local[name] = dict(observed_s=now, state=states[name].tolist())
                nodes[name].observe_local(states[name], now, now)
        if tick % 2 == 0:
            # A sender without current local sensing cannot publish simulator truth.
            for sender in [name for name in states if name == 'cut-in' or name in local]:
                payload = nodes[sender].publish(states[sender], now, now)
                for receiver in ['follower-1', 'follower-2']:
                    permitted = (sender == 'leader' and receiver == 'follower-1'
                                 or sender == 'cut-in' and receiver == 'follower-1'
                                 or sender == 'follower-1' and receiver == 'follower-2')
                    if permitted:
                        channel.transmit(sender, receiver, payload, now,
                                         distance_m=float(np.linalg.norm(states[sender][:2]-states[receiver][:2])))
            for name in ['follower-1', 'follower-2']:
                blocked = scenario in ('radar_blackout', 'dual_blackout') and name == 'follower-1' and 1.+shift <= now < 2.5+shift
                if blocked or name not in local:
                    continue
                target = followers[name].predecessor
                a, b = states[name], states[target]
                gap = float(b[0]-a[0]-2*cfg.vehicle_radius)
                if not 0 <= gap <= 120. or abs(b[1]-a[1]) > 2.:
                    continue
                random = sensor_rng[name]
                measured_gap = max(0., min(120., gap+float(random.uniform(-.1,.1))))
                relative = float(b[3]-a[3]+random.uniform(-.05,.05))
                obs = RangeObservation(target, radar_seq[name], now, tuple(a), measured_gap, relative)
                radar_seq[name] += 1; serial += 1
                heapq.heappush(radar_queue, (now+.05, serial, name, obs))
        radio_events = channel.deliver(now, nodes)
        radar_events = []
        while radar_queue and radar_queue[0][0] <= now+1e-9:
            _, _, name, obs = heapq.heappop(radar_queue)
            accepted = followers[name].observe_radar(obs, now)
            radar_events.append(dict(receiver=name, observation=asdict(obs), accepted=accepted))
        before = {name:state.tolist() for name, state in states.items()}
        controls, after = {}, {}
        for name in NAMES:
            scheduled = -3. if scenario == 'leader_brake' and 2.+shift <= now < 3.+shift else None
            command, decision = followers[name].decide(now, leader_accel=scheduled if name == 'leader' else None)
            after[name] = advance(states[name], command, cfg.dt)
            controls[name] = dict(command=asdict(command), decision=decision)
        if 'cut-in' in states:
            other = states['cut-in'].copy()
            other[0] += other[3]*cfg.dt
            t = now+cfg.dt-shift
            other[1] = 3.5*max(0.,1-(t-3.)) if t < 4. else (0. if t < 12. else min(7.,3.5*(t-12.)))
            after['cut-in'] = other
        states.update(after)
        rows.append(dict(tick=tick, time_s=now, membership=membership, local=local,
                         radio=radio_events, radar=radar_events, before=before,
                         after={name:state.tolist() for name, state in states.items()}, controls=controls))
    raw = path/'ticks.jsonl'
    raw.write_text(''.join(json.dumps(clean(row), allow_nan=False)+'\n' for row in rows))
    from .verify import summarize, replay
    summary = summarize(rows, following)
    summary.update(scenario=scenario, method=method, speed=speed, seed=seed,
                   raw_sha256=digest(raw), case_sha256=digest(path/'case.json'))
    write(path/'summary.json', summary)
    audit = replay(path)
    write(path/'audit.json', audit)
    return summary
