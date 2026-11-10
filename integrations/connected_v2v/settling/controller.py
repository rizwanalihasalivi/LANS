"""Positive-departure selector with a measured lateral-entry stopping guard.

LaneSelector retains the frozen observation/target logic with an explicitly
replaced guard and Frenet steering. MRO makes RobustFollower's positive-exit
super-call execute LaneSelector.decide; no global monkeypatch or truth input.
"""
import math
import numpy as np
from integrations.connected_v2v.autonomy.controller import AutonomousFollower
from integrations.connected_v2v.robustness.controller import RobustFollower
from integrations.connected_v2v.recovery.controller import RADAR_TTL,RangeObservation
from integrations.unified_lans.traffic import Packet,extrapolate
from integrations.unified_lans.physics import Command,constrain
from integrations.unified_lans.traffic import velocity
from .geometry import route_steering


def lane_guard(nearby,ego_s,ego_speed,recovering=False):
    objects=[];blocked=False
    for s,d,speed,lateral in nearby:
        end=d+.6*lateral
        minimum=0. if d*end<=0 else min(abs(d),abs(end))
        lower=minimum-.5*3.*.6**2-.15
        # Initial approach retains the conservative guard. Established following
        # requires an observed cut-in plus distinct fresh unblocked confirmations.
        # Positive exit independently enables catch-up; no schedule/actor label.
        relevant=lower<=2.4 if recovering else abs(d)<=4.5
        gap=s-ego_s-4.6
        threshold=2.+.4*max(0.,ego_speed)+max(0.,ego_speed**2-max(0.,speed)**2)/12.
        danger=relevant and s>ego_s and gap<=threshold
        blocked|=danger
        objects.append(dict(s=float(s),d=float(d),speed=float(speed),lateral=float(lateral),
            lateral_clearance_lower_m=float(lower),relevant=bool(relevant),brake=bool(danger)))
    return bool(blocked),objects


class LaneSelector(AutonomousFollower):
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
                nearby.append(projected)
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
                    nearby.append((s, d, track.speed, track.lateral))
                    if self._radar_in_lane(track, s, d, ego_s):
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
            ego_s, ego_speed = 0., 0.
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
        lane_aware = self.recovering or self.following_confirmations >= 3
        guard, guard_objects = lane_guard(nearby,ego_s,ego_speed,lane_aware)
        blocked |= guard
        if guard and reason == 'unchanged':
            reason = 'occupied_stopping_guard'
        steering = route_steering(ego.state, self.road) if ego is not None and now-ego.observed_s <= .2+1e-9 else self.previous.steering
        command = constrain(Command(steering, -6. if blocked else command.accel), self.previous, self.follower.cfg)
        self.previous = self.follower.base.previous = command
        info.update(selected_target=self.selected, selection_event=reason,
                    selection_brake=bool(blocked), scan_age_s=now-self.scan.observed_s if self.scan else None,
                    nearby_stopping_guard=bool(guard), candidates=sorted(candidates),
                    guard_objects=guard_objects, lateral_guard_horizon_s=.6,
                    lateral_guard_mode='lane_aware' if lane_aware else 'conservative',
                    target_gap_m=selected['gap'] if selected else None)
        return command, info


class SettlingFollower(RobustFollower,LaneSelector):
    def __init__(self,endpoint,**kwargs):
        super().__init__(endpoint,**kwargs)
        self.unknown_since=None
        self.recovering=False
        self.settle_ticks=0
        self.settle_since=None
        self.last_settle_observation=None
        self.cooperative_anchors={}
        self.entry_observations={}
        self.following_confirmations=0
        self.following_target=None
        self.following_stamp=None
        self.cutin_observed=False

    def _prune_tracks(self,observed_s,now):
        super()._prune_tracks(observed_s,now)
        self.entry_observations={name:value for name,value in self.entry_observations.items() if name in self.tracks}
        live={t.alias for t in self.tracks.values()}|{self.selected}
        self.cooperative_anchors={name:value for name,value in self.cooperative_anchors.items() if name in live}

    @staticmethod
    def _in_lane(s,d,lateral,ego_s):
        # Predicted entry is a braking concern, not proof of target membership.
        return 0<s-ego_s<=300. and abs(d)<=1.9

    def _radar_in_lane(self,track,s,d,ego_s):
        inside=self._in_lane(s,d,track.lateral,ego_s) and abs(track.d)<=1.9
        old=self.entry_observations.get(track.name)
        if old is None or old[0]!=track.sequence:
            count=(old[2]+1 if old is not None and track.observed_s-old[1]<=.3+1e-9 else 1) if inside else 0
            self.entry_observations[track.name]=(track.sequence,track.observed_s,count)
        count=self.entry_observations[track.name][2]
        established=track.alias==self.selected or track.name==self.selected
        return inside and (established or abs(track.d)<=1.3 or count>=2)

    def _peer_evidence(self,target,now):
        if target is None:return []
        evidence=super()._peer_evidence(target,now)
        anchor=self.cooperative_anchors.get(target)
        if anchor is not None and 0<=now-anchor[4]<=.5+1e-9:
            for observer,scan in self.peer_scans.items():
                if not 0<=now-scan.observed_s<=.2+1e-9:continue
                age=scan.observed_s-anchor[4]
                if not 0<=age<=.5+1e-9:continue
                matches=[]
                for detection in scan.detections:
                    angle=scan.ego_state[2]+detection.azimuth_rad
                    ray=np.array([math.cos(angle),math.sin(angle)])
                    s,d,heading=self.road.project(np.array(scan.ego_state[:2])+detection.distance_m*ray)
                    projection=math.cos(heading-angle)
                    speed=(detection.range_rate_m_s+float(velocity(scan.ego_state)@ray))/max(.01,projection)
                    if projection<.7 or speed<-.25:continue
                    distance=math.hypot(s-anchor[0]-anchor[2]*age,d-anchor[1]-anchor[3]*age)
                    if distance<=2.+1.5*age*age:
                        rate=(d-anchor[1])/age if age>1e-9 else anchor[3]
                        lateral=.25*max(-5.,min(5.,rate))+.75*anchor[3]
                        matches.append((s,d,max(0.,speed),lateral,scan.observed_s,('peer:'+observer,scan.sequence)))
                if len(matches)==1 and not any(z[-1]==matches[0][-1] for z in evidence):evidence.extend(matches)
        if evidence:
            newest=max(evidence,key=lambda z:z[4])
            if anchor is None or newest[4]>anchor[4]:self.cooperative_anchors[target]=newest
        # This memory is association-only. It never enters candidates, the
        # nominal following packet, or the original local/radio freshness path.
        return evidence

    def decide(self,now):
        used_recovery=self.recovering
        command,info=super().decide(now)
        if info['selection_event']=='positive_exit_release':
            self.recovering=True;self.settle_ticks=0;self.settle_since=None
        elif info['selection_event']=='cut_in':
            self.recovering=False;self.settle_ticks=0;self.settle_since=None
        fresh=info['sensor_source'] in ('radar','v2v') and info['selected_observed_s'] is not None
        if info['selection_event']=='cut_in':
            self.cutin_observed=True
        if self.selected != self.following_target:
            self.following_target=self.selected
            self.following_confirmations=0
            self.following_stamp=None
        if (self.cutin_observed and fresh and not info['selection_brake']
                and (self.following_stamp is None or info['selected_observed_s'] > self.following_stamp)):
            self.following_confirmations=min(3,self.following_confirmations+1)
            self.following_stamp=info['selected_observed_s']
        ego=self.endpoint.inbox.latest.get('ego')
        packet=self.follower.effective.inbox.latest.get(self.selected)
        settled=False
        if fresh and not info['selection_brake'] and ego is not None and packet is not None and info['target_gap_m'] is not None:
            speed=self.road.canonical(ego.state)[2]
            settled=abs(info['target_gap_m']-6.-1.2*speed)<=2. and abs(packet.state[3]-speed)<=.5
        # A repeated call is not another control interval, and a missing interval
        # cannot supply stability evidence. Require two elapsed seconds.
        previous=self.last_settle_observation
        if not settled:
            self.settle_ticks=0;self.settle_since=None
        elif previous is None or now-previous>self.follower.cfg.dt+1e-9 or self.settle_since is None:
            self.settle_ticks=1;self.settle_since=now
        elif now>previous+1e-9:
            self.settle_ticks+=1
        self.last_settle_observation=now
        settled_duration=0. if self.settle_since is None else now-self.settle_since
        if settled_duration>=2.-1e-9:self.recovering=False
        if fresh:self.unknown_since=None
        elif self.unknown_since is None:self.unknown_since=now
        unavailable=0. if self.unknown_since is None else now-self.unknown_since
        info.update(connectivity_mode=('observed' if fresh else 'knowledge_unavailable'),
            knowledge_unavailable_s=unavailable,radio_range_m=150.,
            formation_mode='recovering' if self.recovering else 'following',settled_ticks=self.settle_ticks,
            settled_duration_s=settled_duration,
            formation_mode_used='recovering' if used_recovery else 'following',
            selected_radio_id=next((name for name,alias in self.aliases.items() if alias==self.selected),None),
            cooperative_anchor_observed_s=self.cooperative_anchors.get(self.selected,(None,)*5)[4],
            anonymous_entry_confirmation_frames=2,
            confirmed_following_frames=self.following_confirmations,
            recovery_condition='fresh radar or original-age radio path required; no inference from silence')
        return command,info
