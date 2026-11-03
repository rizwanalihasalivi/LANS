"""Seeded logical-time per-link channel; no radio or real-time fidelity claim."""
from collections import Counter
from dataclasses import dataclass
import heapq
import math
import numpy as np
from .messages import decode_beacon, timestamp, vehicle_id


@dataclass(frozen=True)
class Link:
    delay_s: float = 0.
    jitter_s: float = 0.
    loss: float = 0.
    duplicate: float = 0.
    range_m: float = 150.
    blackout: tuple = ()

    def __post_init__(self):
        for name in ('delay_s', 'jitter_s', 'loss', 'duplicate', 'range_m'):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError('finite nonnegative channel settings required')
        if self.loss > 1 or self.duplicate > 1 or self.range_m <= 0:
            raise ValueError('probabilities must be <=1 and range must be positive')
        windows = []
        for start, end in self.blackout:
            start, end = timestamp(start), timestamp(end)
            if start >= end:
                raise ValueError('blackout interval must be nonempty')
            windows.append((start, end))
        object.__setattr__(self, 'blackout', tuple(windows))

    def offline(self, now):
        return any(start <= now < end for start, end in self.blackout)


class SimulatedChannel:
    def __init__(self, seed=1, default=None, links=None, max_pending=4096):
        if type(max_pending) is not int or max_pending < 1:
            raise ValueError('positive queue capacity required')
        self.default = Link() if default is None else default
        self.links = dict(links or {})
        if not isinstance(self.default, Link):
            raise ValueError('Link configuration required')
        for (sender, receiver), link in self.links.items():
            vehicle_id(sender); vehicle_id(receiver)
            if sender == receiver or not isinstance(link, Link):
                raise ValueError('distinct peer IDs and Link configuration required')
        self.rng = np.random.default_rng(seed)
        self.max_pending = max_pending
        self._queue = []
        self._serial = 0
        self._now = 0.
        self.attempted = 0
        self.scheduled = 0
        self.delivered = 0
        self.dropped = Counter()

    @property
    def pending(self):
        return len(self._queue)

    def _time(self, now):
        now = timestamp(now)
        if now < self._now - 1e-9:
            raise ValueError('channel clock moved backwards')
        self._now = max(self._now, now)
        return now

    def transmit(self, sender, receiver, payload, now, *, distance_m=0.):
        now = self._time(now)
        vehicle_id(sender); vehicle_id(receiver)
        beacon = decode_beacon(payload)
        if sender == receiver or beacon.vehicle_id != sender or beacon.observed_s > now + 1e-9:
            raise ValueError('invalid simulation sender/receiver identity or timestamp')
        if not math.isfinite(distance_m) or distance_m < 0:
            raise ValueError('nonnegative finite distance required')
        self.attempted += 1
        link = self.links.get((sender, receiver), self.default)
        reason = ('out_of_range' if distance_m > link.range_m else
                  'blackout' if link.offline(now) else
                  'loss' if self.rng.random() < link.loss else '')
        if reason:
            self.dropped[reason] += 1
            return
        copies = 2 if self.rng.random() < link.duplicate else 1
        for _ in range(copies):
            if self.pending >= self.max_pending:
                self.dropped['queue_full'] += 1
                continue
            delay = max(0., link.delay_s + self.rng.uniform(-link.jitter_s, link.jitter_s))
            self._serial += 1
            heapq.heappush(self._queue, (now + delay, self._serial, sender, receiver, payload))
            self.scheduled += 1

    def deliver(self, now, endpoints):
        """Receipt time is this poll's time, never the scheduled or observation time."""
        now = self._time(now)
        events = []
        while self._queue and self._queue[0][0] <= now + 1e-9:
            due, _, sender, receiver, payload = heapq.heappop(self._queue)
            link = self.links.get((sender, receiver), self.default)
            if link.offline(now) or receiver not in endpoints:
                self.dropped['blackout_at_delivery' if link.offline(now) else 'recipient_missing'] += 1
                continue
            endpoint = endpoints[receiver]
            if endpoint.vehicle_id != receiver:
                raise ValueError('endpoint mapping identity mismatch')
            beacon = decode_beacon(payload)
            accepted = endpoint.receive(payload, now)
            self.delivered += 1
            events.append(dict(sender=sender, receiver=receiver, sequence=beacon.sequence,
                               observed_s=beacon.observed_s, scheduled_s=due, received_s=now,
                               age_s=now-beacon.observed_s, accepted=accepted,
                               message=payload.decode('utf-8')))
        return events
