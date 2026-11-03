import pytest
from integrations.connected_v2v.autonomy.controller import Scan,Detection
from integrations.connected_v2v.autonomy.test_controller import EGO,radio,scan
from .test_controller import robust
from .perception import encode_peer_scan,decode_peer_scan


def peer_scan(t,sequence,*,x_offset=0.):
    return Scan(sequence,t,(-10.+12.*t+x_offset,3.5,0.,12.,0.,0.),(Detection(35.,0.,0.),),False)


def test_real_anonymous_peer_observations_can_prove_an_occluded_exit():
    node,control=robust();control.observe_scan(scan(),0.);control.decide(0.)
    old=control.selected
    for i,t in enumerate((1.1,1.2,1.3)):
        node.observe_local(EGO,t,t)
        radio(node,'observer',-10.+12.*t,3.5,now=t,sequence=i)
        radio(node,'far',80.,now=t,sequence=i)
        raw=encode_peer_scan('observer',peer_scan(t,i))
        assert control.observe_peer_scan(raw,t)
        command,info=control.decide(t)
    assert control.selected!=old and control.selected==control.aliases['far']
    assert info['selection_event']=='positive_exit_release'
    assert info['peer_exit_evidence'] and all(t-e['observed_s']<=.2 for e in info['peer_exit_evidence'])


def test_peer_scan_age_replay_and_pose_consistency_are_independent_checks():
    node,control=robust();node.observe_local(EGO,1.1,1.1)
    radio(node,'observer',3.2,3.5,now=1.1)
    raw=encode_peer_scan('observer',peer_scan(1.1,4))
    assert control.observe_peer_scan(raw,1.1)
    assert not control.observe_peer_scan(raw,1.1)
    assert not control.observe_peer_scan(encode_peer_scan('observer',peer_scan(1.1,5,x_offset=20.)),1.1)
    assert not control.observe_peer_scan(encode_peer_scan('observer',peer_scan(1.1,6)),1.4)
    assert control.peer_scans['observer'].sequence==4


def test_unknown_observer_or_empty_scan_cannot_fabricate_a_departure():
    node,control=robust();control.observe_scan(scan(),0.);control.decide(0.)
    old=control.selected
    for i,t in enumerate((.1,.2,.3,.4)):
        node.observe_local(EGO,t,t)
        radio(node,'observer',-10.+12.*t,3.5,now=t,sequence=i)
        empty=Scan(i,t,(-10.+12.*t,3.5,0.,12.,0.,0.),(),True)
        assert control.observe_peer_scan(encode_peer_scan('observer',empty),t)
        assert not control.observe_peer_scan(encode_peer_scan('unknown',empty),t)
        control.decide(t)
    assert control.selected==old and control.exit_frames==0


@pytest.mark.parametrize('raw',[b'{}',b'not-json',b'x'*8193,
    b'{"version":1,"version":1,"kind":"range_scan","observer_id":"p","scan":{}}'])
def test_peer_schema_rejects_malformed_oversize_or_duplicate_fields(raw):
    with pytest.raises(ValueError):decode_peer_scan(raw)
