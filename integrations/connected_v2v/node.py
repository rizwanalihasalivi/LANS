"""Per-receiver discovery and original-age tracking, compatible with LANS Inbox."""
from collections import Counter
from integrations.unified_lans.traffic import Inbox, Packet
from .messages import Beacon, decode_beacon, encode_beacon, timestamp, vehicle_id


class V2VEndpoint:
    def __init__(self, name, *, inbox=None, expected_peers=(), max_peers=32, max_packet_age_s=.4):
        self.vehicle_id = vehicle_id(name)
        if type(max_peers) is not int or max_peers < 1:
            raise ValueError('positive integer peer capacity required')
        self.max_packet_age_s = timestamp(max_packet_age_s)
        if self.max_packet_age_s == 0:
            raise ValueError('positive maximum packet age required')
        self.max_peers = max_peers
        self.inbox = inbox if inbox is not None else Inbox()
        # Discovery on a nonempty inbox would leave inconsistent replay/identity state.
        if self.inbox.latest:
            raise ValueError('attach endpoint to an empty inbox before publishing observations')
        peers = {vehicle_id(p) for p in expected_peers}
        if self.vehicle_id in peers or len(peers) > max_peers:
            raise ValueError('invalid peer roster')
        self._known = peers
        self._arrival = {}
        self._local_sequence = -1
        self._send_sequence = -1
        self._last_publish = -1.
        self._now = 0.
        self.received = 0
        self.accepted = 0
        self.rejections = Counter()

    @property
    def expected(self):
        return frozenset(self._known)

    def _time(self, now):
        now = timestamp(now)
        if now < self._now - 1e-9:
            raise ValueError('receiver clock moved backwards')
        self._now = max(self._now, now)
        return now

    def observe_local(self, state, observed_s, now):
        """Trusted local sensing is separate from the network's reserved ego identity."""
        now = self._time(now)
        beacon = Beacon(self.vehicle_id, self._local_sequence + 1, observed_s, list(state))
        if beacon.observed_s > now + 1e-9:
            raise ValueError('future local observation')
        packet = Packet('ego', beacon.sequence, beacon.observed_s, beacon.state)
        if not self.inbox.ingest(packet, now):
            raise ValueError('local observation timestamp regressed')
        self._local_sequence += 1

    def publish(self, state, observed_s, now):
        now = self._time(now)
        beacon = Beacon(self.vehicle_id, self._send_sequence + 1, observed_s, list(state))
        if beacon.observed_s > now + 1e-9 or beacon.observed_s < self._last_publish:
            raise ValueError('future or regressing publication timestamp')
        payload = encode_beacon(beacon)
        self._send_sequence = beacon.sequence
        self._last_publish = beacon.observed_s
        return payload

    def receive(self, payload, now):
        now = self._time(now)
        self.received += 1
        try:
            beacon = decode_beacon(payload)
        except (ValueError, TypeError, OverflowError):
            return self._reject('malformed')
        if beacon.vehicle_id == self.vehicle_id:
            return self._reject('self_message')
        if beacon.observed_s > now + 1e-9:
            return self._reject('future')
        if now - beacon.observed_s > self.max_packet_age_s + 1e-9:
            return self._reject('expired_on_arrival')
        if beacon.vehicle_id not in self._known and len(self._known) >= self.max_peers:
            return self._reject('peer_capacity')
        packet = Packet(beacon.vehicle_id, beacon.sequence, beacon.observed_s, beacon.state)
        if not self.inbox.ingest(packet, now):
            return self._reject('replay_or_regression')
        self._known.add(beacon.vehicle_id)
        self._arrival[beacon.vehicle_id] = now
        self.accepted += 1
        return True

    def _reject(self, reason):
        self.rejections[reason] += 1
        return False

    def peers(self, now):
        now = self._time(now)
        result = {}
        for name in sorted(self._known):
            packet = self.inbox.latest.get(name)
            age = now - packet.observed_s if packet else None
            result[name] = dict(status=('missing' if packet is None else
                                       'fresh' if age <= self.max_packet_age_s + 1e-9 else 'stale'),
                                sequence=packet.sequence if packet else None,
                                observed_s=packet.observed_s if packet else None,
                                received_s=self._arrival.get(name), age_s=age)
        return result

    def sync_expected(self, pipeline):
        """Own the attached pipeline's complete peer roster; never forget stale peers."""
        if pipeline.inbox is not self.inbox:
            raise ValueError('pipeline and endpoint must share their inbox')
        if self.max_packet_age_s != pipeline.cfg.traffic_ttl:
            raise ValueError('endpoint and supervisor freshness thresholds must agree')
        if not set(pipeline.expected).issubset(self._known):
            raise ValueError('pipeline contains peers outside this endpoint roster')
        pipeline.expected = set(self._known)
