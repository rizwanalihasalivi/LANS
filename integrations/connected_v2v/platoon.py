"""Straight-road, time-headway cooperative following using received V2V state.

No acceleration feedforward, consensus protocol or string-stability claim is made.
The unchanged LANS supervisor can only reduce the follower's acceleration.
"""
from dataclasses import dataclass
import math
import numpy as np
from integrations.unified_lans.physics import Command, Config, Route, baseline, constrain
from integrations.unified_lans.traffic import Supervisor, extrapolate
from .messages import timestamp, vehicle_id


@dataclass(frozen=True)
class FollowingConfig:
    standstill_gap_m: float = 6.
    time_headway_s: float = 1.2
    position_gain: float = .35
    velocity_gain: float = .9
    cruise_speed_m_s: float = 12.

    def __post_init__(self):
        if any(isinstance(v, bool) or not math.isfinite(v) or v <= 0 for v in self.__dict__.values()):
            raise ValueError('positive finite following settings required')


class PlatoonController:
    def __init__(self, endpoint, predecessor=None, *, cfg=None, following=None):
        self.endpoint = endpoint
        self.predecessor = vehicle_id(predecessor) if predecessor is not None else None
        if self.predecessor == endpoint.vehicle_id:
            raise ValueError('a vehicle cannot follow itself')
        if self.predecessor is not None and self.predecessor not in endpoint.expected:
            raise ValueError('declare the predecessor in expected_peers before control starts')
        self.cfg = cfg or Config()
        if endpoint.max_packet_age_s != self.cfg.traffic_ttl:
            raise ValueError('endpoint and supervisor freshness thresholds must agree')
        self.following = following or FollowingConfig()
        self.supervisor = Supervisor(self.cfg, 'following')
        self.previous = Command()

    def decide(self, now, *, leader_accel=None):
        now = timestamp(now)
        if leader_accel is not None and (self.predecessor is not None or not math.isfinite(leader_accel)):
            raise ValueError('only a leader may receive a finite scheduled acceleration')
        peers = self.endpoint.peers(now)
        packet = self.endpoint.inbox.latest.get('ego')
        if packet is None or now-packet.observed_s > self.cfg.ego_ttl+1e-9:
            command = constrain(Command(self.previous.steering, -self.cfg.max_brake), self.previous, self.cfg)
            self.previous = command
            return command, dict(source='hold_brake', reason='ego_missing_or_stale',
                                 risk='DANGER', missing=sorted(peer for peer, status in peers.items() if status['status'] != 'fresh'),
                                 gap_m=None, desired_gap_m=None, predecessor_age_s=None)
        # Local sensing is ideal and current in these demos. A delayed local
        # observation is not replaced with simulator truth.
        ego = np.array(packet.state)
        risk = self.supervisor.assess(ego, self.endpoint.inbox, self.endpoint.expected, now, now)
        settings = self.following
        accel = .8*(settings.cruise_speed_m_s-ego[3])
        gap = desired = age = None
        source, reason = 'cruise', ''
        if self.predecessor is None:
            if leader_accel is not None:
                accel = leader_accel
                source = 'leader_schedule'
        elif peers[self.predecessor]['status'] != 'fresh':
            accel = -self.cfg.max_brake
            source, reason = 'fallback_brake', 'predecessor_missing_or_stale'
        else:
            predecessor = self.endpoint.inbox.latest[self.predecessor]
            age = now-predecessor.observed_s
            other = extrapolate(predecessor.state, age)
            tangent = np.array([math.cos(ego[2]), math.sin(ego[2])])
            gap = float((other[:2]-ego[:2])@tangent-2*self.cfg.vehicle_radius)
            desired = settings.standstill_gap_m+settings.time_headway_s*ego[3]
            relative_speed = other[3]*math.cos(other[2]-ego[2])-ego[3]
            accel = settings.position_gain*(gap-desired)+settings.velocity_gain*relative_speed
            # A leader behind the follower or in the opposite direction is not
            # a valid predecessor; it must not induce acceleration.
            if gap <= 0 or math.cos(other[2]-ego[2]) <= 0:
                accel = -self.cfg.max_brake
                source, reason = 'fallback_brake', 'predecessor_geometry_invalid'
            else:
                source = 'cooperative_following'
        accel = self.supervisor.acceleration(accel, risk)
        if risk.missing:
            source, reason = 'fallback_brake', 'traffic_missing_or_stale'
        command = constrain(Command(baseline(ego, Route()), accel), self.previous, self.cfg)
        self.previous = command
        return command, dict(source=source, reason=reason, risk=risk.state, missing=list(risk.missing),
                             gap_m=gap, desired_gap_m=desired, predecessor_age_s=age,
                             critical_id=risk.critical_id)
