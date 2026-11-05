"""No scripted predecessor IDs, scan truth labels, or silence-based departures.

Radar returns are vehicle-centre range/bearing/range-rate measurements. The
adapter must calibrate native returns to that convention. Velocity reconstruction
assumes traffic follows the known route tangent; unresolved association brakes.
"""
from dataclasses import dataclass
import math
import numpy as np
from integrations.connected_v2v.messages import Beacon, timestamp
from integrations.connected_v2v.node import V2VEndpoint
from integrations.connected_v2v.formation.controller import FormationFollower, following_for
from integrations.connected_v2v.recovery.controller import RADAR_TTL, RangeObservation
from integrations.unified_lans.physics import Command, baseline, constrain
from integrations.unified_lans.traffic import Packet, extrapolate, velocity
from .road import Road


@dataclass(frozen=True)
class Detection:
    distance_m: float
    azimuth_rad: float
    range_rate_m_s: float

    def __post_init__(self):
        if (any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                for v in (self.distance_m, self.azimuth_rad, self.range_rate_m_s))
                or not 0 < self.distance_m <= 120. or abs(self.azimuth_rad) > .35
                or abs(self.range_rate_m_s) > 80.):
            raise ValueError('bounded finite radar return required')


@dataclass(frozen=True)
class Scan:
    sequence: int
    observed_s: float
    ego_state: tuple
    detections: tuple
    complete: bool = True

    def __post_init__(self):
        local = Beacon('scan', self.sequence, self.observed_s, self.ego_state)
        if type(self.complete) is not bool or len(self.detections) > 32 or any(
                not isinstance(d, Detection) for d in self.detections):
            raise ValueError('bounded scan and explicit health flag required')
        object.__setattr__(self, 'observed_s', local.observed_s)
        object.__setattr__(self, 'ego_state', local.state)
        object.__setattr__(self, 'detections', tuple(self.detections))


@dataclass
class Track:
    name: str
    observed_s: float
    s: float
    d: float
    speed: float
    lateral: float
    sequence: int
    alias: str


class AutonomousFollower:
    """Bounded development selector around the unchanged v3 following law.

    This controls a follower on a known route. None is NOT permission to cruise:
    a healthy, complete, empty scan must be confirmed on three distinct frames.
    A farther target also needs positive departure evidence on three frames.
    A newly observed closer obstacle takes effect immediately.
    """
    TRACK_MEMORY_S = .5

    def __init__(self, endpoint, *, road=None, speed=12.):
        self.endpoint, self.road = endpoint, road or Road()
        # This inbox uses private peer-/track- aliases, not wire identities.
        # A legitimate wire ID such as "peer-1" must not look like following self.
        self.local = V2VEndpoint('selector-local', max_peers=endpoint.max_peers)
        self.follower = FormationFollower(self.local, following=following_for('damped', speed))
        self.scan = None
        self.tracks = {}
        self._track_serial = 0
        self.active = []
        self.aliases = {}
        self.selected = None
        self.rejected_scans = 0
        self.scan_fault = False
        self.pending = None
        self.pending_frames = 0
        self.pending_stamp = None
        self.previous = Command()
        self.now = 0.

    def _time(self, now):
        now = timestamp(now)
        if now < self.now-1e-9:
            raise ValueError('selector clock moved backwards')
        self.now = max(self.now, now)
        return now

    def _prune_tracks(self, observed_s, now):
        """Retire expired association memory without releasing a missing target.

        Radio replay state belongs to the endpoint and is never removed here.
        Scan replay state is global, so retired anonymous aliases cannot admit
        an old scan. Fresh measurements alone may allocate a new, unique alias.
        """
        self.tracks = {name: track for name, track in self.tracks.items()
                       if observed_s-track.observed_s <= self.TRACK_MEMORY_S+1e-9
                       or self.selected in (name, track.alias)}
        live = {track.alias for track in self.tracks.values()} | {self.selected, 'ego'}
        self.local.inbox.latest = {name: packet for name, packet in self.local.inbox.latest.items()
                                   if name in live or name in self.aliases.values()}
        # Only this selector feeds this cache, after global scan replay checks.
        # Expired, unselected packets cannot be used for following on a retarget.
        self.follower.radar = {name: obs for name, obs in self.follower.radar.items()
                              if name == self.selected or now-obs.observed_s <= RADAR_TTL+1e-9}

    def _new_track_name(self):
        self._track_serial += 1
        while f'track-{self._track_serial}' in self.tracks:
            self._track_serial += 1
        return f'track-{self._track_serial}'

    def observe_scan(self, scan, now):
        now = self._time(now)
        if not isinstance(scan, Scan):
            raise ValueError('Scan required')
        if (scan.observed_s > now+1e-9 or now-scan.observed_s > RADAR_TTL+1e-9
                or self.scan is not None and (scan.sequence <= self.scan.sequence
                                             or scan.observed_s < self.scan.observed_s)):
            self.rejected_scans += 1
            return False
        self._prune_tracks(scan.observed_s, now)
        proposed = []
        fault = False
        for detection in scan.detections:
            angle = scan.ego_state[2]+detection.azimuth_rad
            ray = np.array([math.cos(angle), math.sin(angle)])
            position = np.array(scan.ego_state[:2])+detection.distance_m*ray
            s, d, heading = self.road.project(position)
            projection = math.cos(heading-angle)
            speed = (detection.range_rate_m_s+float(velocity(scan.ego_state)@ray))/max(.01, projection)
            if projection < .7 or speed < -.25:
                fault = True
                continue
            proposed.append((s, d, max(0., speed)))
        if any(math.hypot(a[0]-b[0], a[1]-b[1]) < 1.
               for i, a in enumerate(proposed) for b in proposed[i+1:]):
            fault = True
        # Global one-to-one gates: never greedily attach two returns to one track.
        links = []
        for s, d, speed in proposed:
            matches = []
            for name, old in self.tracks.items():
                age = scan.observed_s-old.observed_s
                if 0 <= age <= .5 and math.hypot(s-old.s-old.speed*age,
                                               d-old.d-old.lateral*age) <= 2.:
                    matches.append(name)
            links.append(matches)
        active = []
        for i, (s, d, speed) in enumerate(proposed):
            matches = links[i]
            if len(matches) > 1 or matches and sum(matches[0] in m for m in links) > 1:
                fault = True
                continue
            old = self.tracks[matches[0]] if matches else None
            if old is None and len(self.tracks) >= self.endpoint.max_peers:
                fault = True
                continue
            name = old.name if old else self._new_track_name()
            dt = scan.observed_s-old.observed_s if old else 0.
            lateral = (d-old.d)/dt if dt > 1e-9 else 0.
            track = Track(name, scan.observed_s, s, d, speed, lateral,
                          scan.sequence, old.alias if old else name)
            self.tracks[name] = track
            active.append(track)
        self.scan, self.active, self.scan_fault = scan, active, fault
        return True

    @staticmethod
    def _in_lane(s, d, lateral, ego_s):
        return 0 < s-ego_s <= 120. and min(abs(d), abs(d+.5*lateral)) <= 1.9

    def decide(self, now):
        now = self._time(now)
        ego = self.endpoint.inbox.latest.get('ego')
        scan_fresh = self.scan is not None and 0 <= now-self.scan.observed_s <= RADAR_TTL+1e-9
        fault = scan_fresh and self.scan_fault
        candidates = {}
        nearby = []
        current_seen_outside = False
        if ego is not None and 0 <= now-ego.observed_s <= self.follower.cfg.ego_ttl+1e-9:
            ego_s, _, ego_speed, _ = self.road.canonical(ego.state)
            canonical_ego = (ego_s, 0., 0., max(0., ego_speed), 0., 0.)
            self.local.observe_local(canonical_ego, ego.observed_s, now)
            radios = {}
            for name in sorted(self.endpoint.expected):
                packet = self.endpoint.inbox.latest.get(name)
                if packet is None or not 0 <= now-packet.observed_s <= self.follower.cfg.traffic_ttl+1e-9:
                    continue
                if name not in self.aliases:
                    self.aliases[name] = f'peer-{len(self.aliases)+1}'
                alias = self.aliases[name]
                s, d, speed, lateral = self.road.canonical(packet.state)
                # Preserve the source timestamp. Candidate geometry alone is projected to now.
                canonical = Packet(alias, packet.sequence, packet.observed_s,
                                   (s, 0., 0., max(0., speed), 0., 0.))
                projected = self.road.canonical(extrapolate(packet.state, now-packet.observed_s))
                radios[alias] = (packet, canonical, projected)
                nearby.append(projected[:3])
                if self._in_lane(*[projected[j] for j in (0, 1, 3)], ego_s):
                    candidates[alias] = dict(radio=canonical, radar=None, gap=projected[0]-ego_s-4.6)
                elif alias == self.selected:
                    current_seen_outside = True
            if scan_fresh:
                associations = []
                for track in self.active:
                    near = []
                    for alias, (raw, _, _) in radios.items():
                        projected = self.road.canonical(extrapolate(raw.state, track.observed_s-raw.observed_s))
                        if abs(track.observed_s-raw.observed_s) <= .2+1e-9 and math.hypot(
                                track.s-projected[0], track.d-projected[1]) <= 2.:
                            near.append(alias)
                            if abs(track.speed-projected[2]) > 2.:
                                fault = True
                    associations.append(near)
                for track, near in zip(self.active, associations):
                    if len(near) > 1 or near and sum(near[0] in m for m in associations) > 1:
                        fault = True
                        continue
                    if near:
                        if track.alias.startswith('peer-') and track.alias != near[0]:
                            fault = True
                        track.alias = near[0]
                    age = now-track.observed_s
                    s, d = track.s+track.speed*age, track.d+track.lateral*age
                    nearby.append((s, d, track.speed))
                    if self._in_lane(s, d, track.lateral, ego_s):
                        entry = candidates.setdefault(track.alias, dict(radio=None, radar=None, gap=math.inf))
                        # RangeObservation's reconstruction is in route coordinates.
                        scan_s, _, scan_speed, _ = self.road.canonical(self.scan.ego_state)
                        gap = max(0., track.s-scan_s-4.6)
                        if gap > 120.:
                            fault = True
                            continue
                        entry['radar'] = RangeObservation(track.alias, track.sequence, track.observed_s,
                            (scan_s, 0., 0., max(0., scan_speed), 0., 0.), gap, track.speed-max(0., scan_speed))
                        entry['gap'] = min(entry['gap'], s-ego_s-4.6)
                    elif track.alias == self.selected:
                        current_seen_outside = True
        else:
            ego_s = 0.
        nearest = min(candidates, key=lambda key:(candidates[key]['gap'], key)) if candidates else None
        old = self.selected
        reason = 'unchanged'
        blocked = False
        complete = scan_fresh and self.scan.complete and not fault
        if nearest != old or nearest is None:
            # No positive absence evidence is inferred from an expired packet/scan.
            closer = nearest is not None and (old is None or old in candidates and
                      candidates[nearest]['gap'] < candidates[old]['gap']-.05)
            if closer:
                self.selected = nearest
                reason = 'acquired' if old is None else 'cut_in'
                self.pending, self.pending_frames = None, 0
            else:
                positive_departure = complete or current_seen_outside and nearest is not None
                stamp = (self.scan.sequence if complete else
                         tuple((k, v[0].sequence) for k, v in sorted(radios.items())) if current_seen_outside else None)
                proposal = (nearest, old)
                if not positive_departure:
                    self.pending, self.pending_frames = None, 0
                elif proposal != self.pending:
                    self.pending, self.pending_frames, self.pending_stamp = proposal, 1, stamp
                elif stamp != self.pending_stamp:
                    self.pending_frames += 1
                    self.pending_stamp = stamp
                if self.pending_frames >= 3:
                    self.selected = nearest
                    reason = 'clear_confirmed' if nearest is None else 'cut_out'
                else:
                    blocked, reason = True, 'departure_unconfirmed'
        else:
            self.pending, self.pending_frames = None, 0
        # A selected target must have fresh knowledge on every tick. A clear lane
        # needs a current healthy complete scan; None alone never grants cruise.
        selected = candidates.get(self.selected)
        blocked |= fault or (selected is None and (self.selected is not None or not complete))
        if fault:
            reason = 'association_ambiguous'
        elif blocked and reason == 'unchanged':
            reason = 'knowledge_missing'
        if self.selected != self.follower.predecessor:
            self.follower.retarget(self.selected)
        if selected is not None:
            if selected['radio'] is not None:
                self.local.inbox.latest[self.selected] = selected['radio']
            else:
                self.local.inbox.latest.pop(self.selected, None)
            if selected['radar'] is not None:
                obs = selected['radar']
                previous = self.follower.radar.get(self.selected)
                if previous is None or obs.sequence > previous.sequence:
                    self.follower.observe_radar(obs, now)
        command, info = self.follower.decide(now)
        # Catch-up must not consume braking distance beside a slower vehicle
        # whose future lane choice is unknown. This cap uses ALL fresh nearby
        # observations, including adjacent lanes, not only the selected target.
        # .4 s reaction allowance + differential stopping distance at 6 m/s².
        guard = False
        if ego is not None and 0 <= now-ego.observed_s <= self.follower.cfg.ego_ttl+1e-9:
            guard = any(abs(d) <= 4.5 and 0 < s-ego_s and s-ego_s-4.6 <=
                        2.+.4*max(0., ego_speed)+max(0., ego_speed**2-speed**2)/12.
                        for s, d, speed in nearby)
        blocked |= guard
        if guard and reason == 'unchanged':
            reason = 'nearby_stopping_guard'
        steering = baseline(ego.state, self.road) if ego is not None and now-ego.observed_s <= .2+1e-9 else self.previous.steering
        command = constrain(Command(steering, -6. if blocked else command.accel), self.previous, self.follower.cfg)
        self.previous = self.follower.base.previous = command
        info.update(selected_target=self.selected, selection_event=reason,
                    selection_brake=bool(blocked), scan_age_s=now-self.scan.observed_s if self.scan else None,
                    nearby_stopping_guard=bool(guard), candidates=sorted(candidates),
                    target_gap_m=selected['gap'] if selected else None)
        return command, info
