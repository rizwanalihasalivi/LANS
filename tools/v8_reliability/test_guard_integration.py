"""V2 retains fail-closed behavior after replacing the traffic supervisor."""
import pytest
from integrations.unified_lans.physics import Route,Config
from integrations.unified_lans.traffic import Packet
from .traffic_guard import Controller


@pytest.mark.parametrize('source',['missing_ego','missing_peer','stale_peer'])
def test_v2_missing_knowledge_forces_braking_without_recourse(source):
    c=Controller(Route('straight'),cfg=Config(horizon=2.),penalty=16.,mpc=False)
    c.expected={'peer'};now=.5
    if source!='missing_ego':c.inbox.ingest(Packet('ego',1,now,(0.,.3,0.,12.,0.,0.)),now)
    if source=='stale_peer':c.inbox.ingest(Packet('peer',0,0.,(30.,0.,0.,8.,0.,0.)),now)
    r=c.decide(now)
    assert r['issued_accel']==-6. and r['recovery'] is None and r['source']!='ppo'


def test_v2_dead_reckoning_never_releases_ego_expiry_brake():
    c=Controller(Route('straight'),cfg=Config(horizon=2.),penalty=16.,mpc=False)
    z=(0.,.3,0.,12.,0.,0.);c.inbox.ingest(Packet('ego',0,0.,z),0.)
    for tick in range(6):
        now=tick*.05;c.decide(now);z=c.apply(now,z)
    r=c.decide(.3)
    assert r['ego_backup'] and r['issued_accel']==-6. and r['recovery'] is None
