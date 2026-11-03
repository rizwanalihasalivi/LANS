"""Fresh independent range sensing can replace missing V2V knowledge.

The v1 law, actuator limits and supervisor are reused without modification.
This is a sensor-architecture ablation, not an attribution to a new learned law.
"""
from dataclasses import dataclass
import math
import numpy as np
from integrations.connected_v2v.messages import Beacon, timestamp, vehicle_id
from integrations.connected_v2v.node import V2VEndpoint
from integrations.connected_v2v.platoon import FollowingConfig, PlatoonController
from integrations.unified_lans.physics import Config
from integrations.unified_lans.traffic import Packet, extrapolate

METHODS = ('v2v_only', 'radar_acc', 'fusion')
RADAR_TTL = .2
MAX_RANGE = 120.


@dataclass(frozen=True)
class RangeObservation:
    target_id: str
    sequence: int
    observed_s: float
    ego_state: tuple
    gap_m: float
    relative_speed_m_s: float

    def __post_init__(self):
        vehicle_id(self.target_id)
        local = Beacon('local-sensor', self.sequence, self.observed_s, list(self.ego_state))
        object.__setattr__(self, 'observed_s', local.observed_s)
        object.__setattr__(self, 'ego_state', local.state)
        if (isinstance(self.gap_m, bool) or isinstance(self.relative_speed_m_s, bool)
                or not math.isfinite(self.gap_m) or not 0 <= self.gap_m <= MAX_RANGE
                or not math.isfinite(self.relative_speed_m_s)
                or self.relative_speed_m_s+self.ego_state[3] < -.25):
            raise ValueError('finite, physically admissible range/rate measurement required')

    def packet(self, cfg):
        # Reconstruct at observation time, NOT at receipt time. Straight-road
        # longitudinal sensing assumes target heading matches local heading.
        state = np.array(self.ego_state)
        state[:2] += (self.gap_m+2*cfg.vehicle_radius)*np.array([math.cos(state[2]), math.sin(state[2])])
        state[3] = max(0., state[3]+self.relative_speed_m_s)
        state[4:] = 0.
        return Packet(self.target_id, self.sequence, self.observed_s, tuple(state))


class FusionFollower:
    def __init__(self, endpoint, predecessor=None, *, method='fusion', cfg=None, following=None):
        if method not in METHODS:
            raise ValueError('unknown sensor ablation')
        self.endpoint, self.method = endpoint, method
        self.cfg, self.following = cfg or Config(), following or FollowingConfig()
        if endpoint.max_packet_age_s != self.cfg.traffic_ttl:
            raise ValueError('V2V and supervisor freshness limits must match')
        self.radar = {}
        self.radar_rejected = 0
        self._now = 0.
        self.predecessor = None
        self.base = None
        self.retarget(predecessor)

    def retarget(self, predecessor):
        """Explicit platoon membership command, never inferred from silence."""
        if predecessor is not None:
            vehicle_id(predecessor)
            if predecessor == self.endpoint.vehicle_id:
                raise ValueError('cannot follow self')
        previous = self.base.previous if self.base is not None else None
        self.predecessor = predecessor
        self.effective = V2VEndpoint(self.endpoint.vehicle_id, expected_peers=[predecessor] if predecessor else (),
                                     max_packet_age_s=self.cfg.traffic_ttl)
        self.base = PlatoonController(self.effective, predecessor, cfg=self.cfg, following=self.following)
        if previous is not None:
            self.base.previous = previous

    def observe_radar(self, observation, now):
        now = timestamp(now)
        if now < self._now-1e-9:
            raise ValueError('sensor clock moved backwards')
        self._now = max(self._now, now)
        if not isinstance(observation, RangeObservation):
            raise ValueError('RangeObservation required')
        previous = self.radar.get(observation.target_id)
        if previous is None and len(self.radar) >= self.endpoint.max_peers:
            self.radar_rejected += 1
            return False
        valid = (observation.target_id != self.endpoint.vehicle_id
                 and observation.observed_s <= now+1e-9
                 and now-observation.observed_s <= RADAR_TTL+1e-9)
        if previous is not None:
            valid &= observation.sequence > previous.sequence and observation.observed_s >= previous.observed_s
        if not valid:
            self.radar_rejected += 1
            return False
        self.radar[observation.target_id] = observation
        return True

    def decide(self, now, *, leader_accel=None):
        now = timestamp(now)
        if now < self._now-1e-9:
            raise ValueError('controller clock moved backwards')
        self._now = max(self._now, now)
        ego = self.endpoint.inbox.latest.get('ego')
        if ego is not None:
            self.effective.inbox.latest['ego'] = ego
        else:
            self.effective.inbox.latest.pop('ego', None)
        name = self.predecessor
        radio = self.endpoint.inbox.latest.get(name)
        radar = self.radar.get(name)
        radio_age = now-radio.observed_s if radio else None
        radar_age = now-radar.observed_s if radar else None
        fresh_radio = radio is not None and 0 <= radio_age <= self.cfg.traffic_ttl+1e-9
        fresh_radar = radar is not None and 0 <= radar_age <= RADAR_TTL+1e-9
        selected, sensing = None, 'none'
        if name is not None:
            if self.method != 'radar_acc' and fresh_radio:
                selected, sensing = radio, 'v2v'
            if self.method != 'v2v_only' and fresh_radar:
                local_packet = radar.packet(self.cfg)
                if self.method == 'fusion' and fresh_radio:
                    a = extrapolate(radio.state, radio_age)
                    b = extrapolate(local_packet.state, radar_age)
                    # Reject contradicting fresh sources; never hide a nearby
                    # obstacle by trusting a more convenient measurement.
                    if np.linalg.norm(a[:2]-b[:2]) > 2. or abs(a[3]-b[3]) > 2.:
                        selected, sensing = None, 'disagreement'
                    elif radar.observed_s > radio.observed_s+1e-9:
                        selected, sensing = local_packet, 'radar'
                else:
                    selected, sensing = local_packet, 'radar'
            if selected is None:
                self.effective.inbox.latest.pop(name, None)
            else:
                # Source replay checks occurred independently. The original
                # measurement stamp survives source switching unchanged.
                self.effective.inbox.latest[name] = selected
        command, decision = self.base.decide(now, leader_accel=leader_accel)
        if decision['source'] == 'hold_brake':
            sensing = 'none'
        decision.update(sensor_source=sensing, selected_observed_s=(selected.observed_s if sensing in ('v2v', 'radar') else None),
                        v2v_age_s=radio_age, radar_age_s=radar_age)
        return command, decision
