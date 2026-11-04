"""Formation-role priority under the unchanged one-packet/100 ms relay budget."""
from integrations.connected_v2v.robustness.relay import PendingRelays
from integrations.connected_v2v.messages import decode_beacon


class FormationRelays(PendingRelays):
    def __init__(self,head='leader',member='follower'):
        super().__init__();self.head=head;self.member=member;self.turn=0
        self.last_tx=float('-inf')

    def take(self,now,road=None):
        if now-self.last_tx<.1-1e-9:return None
        self.pending={n:raw for n,raw in self.pending.items() if 0<=now-decode_beacon(raw).observed_s<=.25+1e-9}
        if not self.pending:return None
        self.turn+=1
        # Membership roles configure routing, not the ego's selected target.
        # Two head slots per member slot protect the recovery information path.
        preferred=(self.member,self.head) if self.turn%3==0 else (self.head,self.member)
        for name in preferred:
            if name in self.pending:
                self.last_tx=now
                return self.pending.pop(name)
        raw=super().take(now,road)
        if raw is not None:self.last_tx=now
        return raw
