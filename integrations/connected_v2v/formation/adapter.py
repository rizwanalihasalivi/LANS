"""Reuse the immutable v2 simulator/replayer through a scoped in-process adapter."""
from contextlib import contextmanager
from integrations.connected_v2v.recovery import study as v2_study, verify as v2_verify
from .controller import FormationFollower, following_for


@contextmanager
def configured(variant):
    old = v2_study.FusionFollower, v2_study.FollowingConfig, v2_verify.FusionFollower
    try:
        v2_study.FusionFollower = FormationFollower
        v2_study.FollowingConfig = lambda cruise_speed_m_s: following_for(variant, cruise_speed_m_s)
        v2_verify.FusionFollower = FormationFollower
        yield
    finally:
        v2_study.FusionFollower, v2_study.FollowingConfig, v2_verify.FusionFollower = old
