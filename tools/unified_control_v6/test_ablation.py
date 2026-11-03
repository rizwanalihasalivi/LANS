from integrations.unified_lans.physics import Config, Route
from integrations.unified_lans.traffic import Packet
from tools.unified_campaign.study import Clock
from tools.unified_control_v5.control import Controller as V5
from tools.unified_control_v6.ablation import controller_class, cases


def test_no_expiry_ablation_retains_source_age_and_uncertainty():
    full=controller_class(V5,'full')(Route('straight'),cfg=Config(),clock=Clock())
    ablated=controller_class(V5,'without_traffic_expiry')(Route('straight'),cfg=Config(),clock=Clock())
    ego=[0.,0.,0.,12.,0.,0.]
    for c in (full,ablated):
        c.expected={'lead'}
        c.inbox.ingest(Packet('lead',1,0.,(30.,0.,0.,8.,0.,0.)),0.)
    assert full.supervisor.assess(ego,full.inbox,full.expected,1.,1.).missing==('lead',)
    risk=ablated.supervisor.assess(ego,ablated.inbox,ablated.expected,1.,1.)
    assert not risk.missing and risk.max_age==1.
    assert risk.vehicles[0][2]==.6
    assert ablated.inbox.latest['lead'].observed_s==0.


def test_no_interaction_ablation_keeps_ego_loss_stop_and_complete_case_grid():
    c=controller_class(V5,'without_interaction_supervision')(Route('straight'),clock=Clock())
    c.supervisor.force_stop=True
    assert c.supervisor.assess([0.,0.,0.,12.,0.,0.],c.inbox,set(),0.,0.).state=='DANGER'
    grid=cases()
    assert len(grid)==64 and len({c['id'] for c in grid})==64
    assert len({c['fixture_id'] for c in grid})==16
    for fixture in {c['fixture_id'] for c in grid}:
        assert len([c for c in grid if c['fixture_id']==fixture])==4
