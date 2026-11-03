"""Fallible-perception following: absence is not departure evidence."""
from dataclasses import replace
import math
import numpy as np
from integrations.connected_v2v.autonomy.controller import AutonomousFollower, Scan, Track
from integrations.connected_v2v.recovery.controller import RADAR_TTL
from integrations.unified_lans.physics import Command
from integrations.unified_lans.traffic import velocity,extrapolate
from .perception import decode_peer_scan


class RobustFollower(AutonomousFollower):
    def __init__(self, endpoint, **kwargs):
        super().__init__(endpoint, **kwargs)
        self.exit_target = None
        self.exit_frames = 0
        self.exit_stamp = None
        self.peer_scans={}
        self.peer_scan_rejections=0

    def observe_peer_scan(self,payload,now):
        now=self._time(now)
        try:observer,scan=decode_peer_scan(payload)
        except (ValueError,TypeError,OverflowError):
            self.peer_scan_rejections+=1;return False
        previous=self.peer_scans.get(observer)
        peer=self.endpoint.inbox.latest.get(observer)
        valid=(observer!=self.endpoint.vehicle_id and 0<=now-scan.observed_s<=.2+1e-9 and
               peer is not None and 0<=now-peer.observed_s<=.4+1e-9 and
               (previous is not None or len(self.peer_scans)<self.endpoint.max_peers))
        if previous is not None:valid &= scan.sequence>previous.sequence and scan.observed_s>=previous.observed_s
        if valid:
            pose=extrapolate(peer.state,scan.observed_s-peer.observed_s)
            valid=np.linalg.norm(pose[:2]-scan.ego_state[:2])<=2. and np.linalg.norm(velocity(pose)-velocity(scan.ego_state))<=2.
        if not valid:
            self.peer_scan_rejections+=1;return False
        self.peer_scans[observer]=scan
        return True

    def _peer_evidence(self,target,now):
        tracks=[t for t in self.tracks.values() if t.alias==target or t.name==target]
        evidence=[]
        for observer,scan in self.peer_scans.items():
            if not 0<=now-scan.observed_s<=.2+1e-9:continue
            matches=[]
            for detection in scan.detections:
                angle=scan.ego_state[2]+detection.azimuth_rad
                ray=np.array([math.cos(angle),math.sin(angle)])
                s,d,heading=self.road.project(np.array(scan.ego_state[:2])+detection.distance_m*ray)
                projection=math.cos(heading-angle)
                speed=(detection.range_rate_m_s+float(velocity(scan.ego_state)@ray))/max(.01,projection)
                if projection<.7 or speed<-.25:continue
                near=[]
                for old in tracks:
                    age=scan.observed_s-old.observed_s
                    if 0<=age<=2. and math.hypot(s-old.s-old.speed*age,d-old.d-old.lateral*min(age,.5))<=2.+1.5*age*age:
                        near.append(old)
                if len(near)==1:matches.append((s,d,max(0.,speed),near[0].lateral,scan.observed_s,('peer:'+observer,scan.sequence)))
            # A single observer with multiple plausible objects cannot prove exit.
            if len(matches)==1:evidence.extend(matches)
        return evidence

    @staticmethod
    def _in_lane(s,d,lateral,ego_s):
        # V2V knowledge can be farther than the 120 m radar envelope (including
        # fresh relayed messages). Never discard a fresh radio target at 120 m.
        # Predict entry only near the lane boundary, not from a noisy lateral
        # derivative of a vehicle still centred in the adjacent lane.
        return 0<s-ego_s<=300. and (abs(d)<=1.9 or abs(d)<=2.8 and
                                   min(abs(d),abs(d+.3*lateral))<=1.9)

    def observe_scan(self, scan, now):
        now = self._time(now)
        if not isinstance(scan, Scan):
            raise ValueError('Scan required')
        if (scan.observed_s > now+1e-9 or now-scan.observed_s > RADAR_TTL+1e-9
                or self.scan is not None and (scan.sequence <= self.scan.sequence
                                             or scan.observed_s < self.scan.observed_s)):
            self.rejected_scans += 1
            return False
        proposed, fault = [], False
        for detection in scan.detections:
            angle = scan.ego_state[2]+detection.azimuth_rad
            ray = np.array([math.cos(angle), math.sin(angle)])
            s, d, heading = self.road.project(np.array(scan.ego_state[:2])+detection.distance_m*ray)
            projection = math.cos(heading-angle)
            speed = (detection.range_rate_m_s+float(velocity(scan.ego_state)@ray))/max(.01, projection)
            if projection < .7 or speed < -.25:
                fault = True
                continue
            proposed.append((s, d, max(0., speed)))
        if any(math.hypot(a[0]-b[0], a[1]-b[1]) < 1.
               for i,a in enumerate(proposed) for b in proposed[i+1:]):
            fault = True
        links = []
        for s, d, speed in proposed:
            fresh=[];coasted=[]
            for name, old in self.tracks.items():
                age = scan.observed_s-old.observed_s
                # Long-lived memory is used ONLY for matching a NEW observation.
                # It never supplies a control packet or a refreshed timestamp.
                distance=math.hypot(s-old.s-old.speed*age,d-old.d-old.lateral*min(age,.5))
                if 0<=age<=.5 and distance<=3.:fresh.append((distance,name))
                elif .5<age<=2. and distance<=2.+1.5*age*age:coasted.append((distance,name))
            # A dormant uncertainty gate must not veto an unambiguous fresh
            # match forever. Within the chosen freshness tier require a unique
            # best geometric match, separated by at least 1 m from alternatives.
            ranked=sorted(fresh or coasted)
            matches=[ranked[0][1]] if ranked and (len(ranked)==1 or ranked[1][0]-ranked[0][0]>=1.) else [n for _,n in ranked]
            links.append(matches)
        active = []
        for i,(s,d,speed) in enumerate(proposed):
            matches = links[i]
            if len(matches)>1 or matches and sum(matches[0] in m for m in links)>1:
                fault = True
                continue
            old = self.tracks[matches[0]] if matches else None
            if old is None and len(self.tracks) >= self.endpoint.max_peers:
                fault = True
                continue
            name = old.name if old else f'track-{len(self.tracks)+1}'
            dt = scan.observed_s-old.observed_s if old else 0.
            rate = max(-5., min(5., (d-old.d)/dt)) if dt>1e-9 else 0.
            lateral = .25*rate+.75*old.lateral if old and dt <= .3 else rate
            track = Track(name,scan.observed_s,s,d,speed,lateral,scan.sequence,old.alias if old else name)
            self.tracks[name] = track
            active.append(track)
        # A functioning detector can still miss a vehicle. Never turn its health
        # flag into proof that all traffic in a corridor has been observed.
        self.scan, self.active, self.scan_fault = replace(scan,complete=False), active, fault
        return True

    def _evidence(self, target, now):
        ego = self.endpoint.inbox.latest.get('ego')
        if target is None or ego is None or now-ego.observed_s > .2+1e-9:
            return None, False, None
        ego_s = self.road.project(ego.state[:2])[0]
        observations = []
        for name, alias in self.aliases.items():
            packet = self.endpoint.inbox.latest.get(name)
            if alias == target and packet is not None and 0<=now-packet.observed_s<=.4+1e-9:
                s,d,speed,lateral = self.road.canonical(packet.state)
                observations.append((s,d,speed,lateral,packet.observed_s,('radio',packet.sequence)))
        if self.scan is not None and 0<=now-self.scan.observed_s<=.2+1e-9 and not self.scan_fault:
            for track in self.active:
                if track.alias == target:
                    observations.append((track.s,track.d,track.speed,track.lateral,track.observed_s,('radar',track.sequence)))
        observations.extend(self._peer_evidence(target,now))
        if not observations:
            return None, False, None
        gaps = [s+speed*(now-stamp)-ego_s-4.6 for s,d,speed,lateral,stamp,_ in observations]
        # Measured exit (with margin), not just predicted disappearance. Require
        # every available fresh source to agree and no predicted near-term reentry.
        outside = all((s-ego_s < -5.) or abs(d)>2.3 and d*(d+.5*lateral)>0 and
                      min(abs(d),abs(d+.5*lateral))>2.3 for s,d,speed,lateral,stamp,key in observations)
        stamp = max(observations,key=lambda item:item[4])[-1]
        return min(gaps), outside, stamp

    def decide(self, now):
        promoted=False
        if self.selected is not None and self.selected.startswith('track-') and self.scan is not None and now-self.scan.observed_s<=.2+1e-9 and not self.scan_fault:
            same=[t for t in self.active if t.name==self.selected and t.alias!=self.selected]
            if len(same)==1:
                # A uniquely associated radio identity is the SAME observed
                # object, not evidence that an unseen predecessor departed.
                self.selected=same[0].alias
                self.follower.retarget(self.selected)
                self.pending,self.pending_frames=None,0
                promoted=True
        old = self.selected
        old_tracks={t.name for t in self.active if t.alias==old or t.name==old}
        gap, outside, stamp = self._evidence(old,now)
        if old != self.exit_target or not outside:
            self.exit_target, self.exit_frames, self.exit_stamp = old, 0, None
        if outside and stamp != self.exit_stamp:
            self.exit_frames += 1
            self.exit_stamp = stamp
        released = old is not None and self.exit_frames >= 3
        if released:
            self.selected = None
            self.pending, self.pending_frames = None, 0
            self.follower.retarget(None)
        command, info = super().decide(now)
        # The frozen selector can infer a departure from three complete scans.
        # Our incomplete scans prohibit that path. Enforce the stronger positive
        # exit rule even if a noisy marginal track made the older rule release.
        changed = old is not None and self.selected != old
        closer = gap is not None and info['target_gap_m'] is not None and info['target_gap_m'] < gap-.05
        same_object=old is not None and old.startswith('track-') and any(t.name in old_tracks and t.alias==self.selected for t in self.active)
        if changed and not released and not closer and not same_object:
            self.selected = old
            self.follower.retarget(old)
            command = Command(command.steering,-6.)
            self.previous = self.follower.base.previous = command
            info.update(selected_target=old,target_gap_m=gap,selection_event='release_blocked',
                        selection_brake=True,source='fallback_brake',reason='departure_not_observed',
                        sensor_source='none',selected_observed_s=None)
        elif released and self.selected != old:
            info['selection_event'] = 'positive_exit_release'
        info.update(positive_exit_frames=self.exit_frames,positive_exit_target=old,
                    identity_memory_s=2.,absence_is_departure=False,identity_promoted=bool(promoted or same_object),
                    peer_exit_evidence=[dict(observer=key[0],sequence=key[1],observed_s=stamp,s=s,d=d)
                        for s,d,speed,lateral,stamp,key in self._peer_evidence(old,now)])
        return command,info
