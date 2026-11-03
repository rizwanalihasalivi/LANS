"""Nominal pole placement, unchanged knowledge/braking rules, bounded catch-up."""
from dataclasses import replace
from integrations.connected_v2v.platoon import FollowingConfig
from integrations.connected_v2v.recovery.controller import FusionFollower
from integrations.unified_lans.physics import Command

VARIANTS = ('baseline', 'damped')
OVERSPEED_ALLOWANCE = 8.
OMEGA = .8


def following_for(variant, speed):
    if variant not in VARIANTS:
        raise ValueError('unknown formation variant')
    settings = FollowingConfig(cruise_speed_m_s=float(speed))
    if variant == 'damped':
        # For e=gap-d0-h*v, a=kp*e+kv*(v_front-v), constant front speed:
        # e''+(h*kp+kv)e'+kp*e=0. Choose (lambda+omega)^2.
        settings = replace(settings, position_gain=OMEGA**2,
                           velocity_gain=2*OMEGA-settings.time_headway_s*OMEGA**2)
    return settings


class FormationFollower(FusionFollower):
    def __init__(self, endpoint, predecessor=None, *, method='damped', cfg=None, following=None):
        if method not in VARIANTS:
            raise ValueError('unknown formation variant')
        self.variant = method
        speed = following.cruise_speed_m_s if following is not None else 12.
        chosen = following_for(method, speed)
        if following is not None and following != chosen:
            raise ValueError('settings differ from the declared analytical variant')
        super().__init__(endpoint, predecessor, method='fusion', cfg=cfg, following=chosen)

    def decide(self, now, *, leader_accel=None):
        command, info = super().decide(now, leader_accel=leader_accel)
        ego = self.endpoint.inbox.latest.get('ego')
        ceiling = self.following.cruise_speed_m_s + (OVERSPEED_ALLOWANCE if self.predecessor else 0.)
        limited = False
        if ego is not None and 0 <= now-ego.observed_s <= self.cfg.ego_ttl+1e-9 and command.accel > 0:
            # Apply the same envelope to BOTH variants; never reduce braking.
            available = max(0., (ceiling-ego.state[3])/self.cfg.dt)
            if command.accel > available:
                command = Command(command.steering, available)
                self.base.previous = command
                limited = True
        info.update(formation_variant=self.variant, recovery_speed_ceiling_m_s=ceiling,
                    speed_envelope_active=limited)
        return command, info
