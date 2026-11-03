"""Bounded-rate forwarding of already validated ORIGINAL beacon bytes."""
from integrations.connected_v2v.messages import decode_beacon


class PendingRelays:
    def __init__(self):
        self.pending={};self.cursor=''

    def add(self,payload):
        beacon=decode_beacon(payload)
        self.pending[beacon.vehicle_id]=payload

    def take(self,now,road=None):
        self.pending={name:raw for name,raw in self.pending.items()
                      if 0<=now-decode_beacon(raw).observed_s<=.25+1e-9}
        if not self.pending:return None
        names=sorted(self.pending)
        if road is not None:
            relevant=[name for name in names if abs(road.project(decode_beacon(self.pending[name]).state[:2])[1])<=1.9]
            if relevant:names=relevant
        name=next((n for n in names if n>self.cursor),names[0])
        self.cursor=name
        return self.pending.pop(name)  # No decoding/re-encoding or timestamp refresh.
