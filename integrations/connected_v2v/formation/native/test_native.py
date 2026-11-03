import pytest
from .run import controller_source,prepare_native,validate_pose


def test_native_factorial_keeps_leader_cap_and_exposes_follower_recovery_cap(tmp_path):
    source=controller_source()
    assert 'FormationFollower as FusionFollower' in source
    assert 'following_for' in source and "os.environ['LANS_FORMATION_ADAPTER']" in source
    assert "8. if name == 'leader'" in source and 'else 16.' in source
    assert 'native_cap_m_s=native_cap' in source
    world=prepare_native(tmp_path/'world')
    assert world.read_text().count('name "local_radar"')==3
    assert world.read_text().count('size 2000 100 0.2')==2
    assert 'translation 500 0 -0.1' in world.read_text()
    assert 'native_pose=dict' in source
    assert 'getFromDef' not in source


@pytest.mark.parametrize('position,rpy', [([1600.,0.,.7],[0.,0.,0.]),
                                        ([150.,0.,-1.],[0.,0.,0.]),
                                        ([150.,0.,.7],[0.,.8,3.14])])
def test_invalid_native_fixture_pose_is_rejected(position,rpy):
    with pytest.raises(AssertionError):validate_pose(dict(native_pose=dict(position=position,rpy=rpy)))
