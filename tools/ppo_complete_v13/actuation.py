"""Shared native longitudinal actuation, with measured acceleration diagnostics.

This controls Webots' physical drivetrain through its public Driver API. It
never writes pose, velocity or force. A target speed is not a hard vehicle cap.
The same frozen low-level mapping is used for every higher-level controller.
"""
from dataclasses import dataclass
import math


@dataclass
class LongitudinalActuator:
    method:str='cruise_lookahead'
    lookahead_s:float=.05
    max_accel:float=2.5
    max_brake:float=6.
    native_max_speed:float=50.
    last_speed:float|None=None
    filtered_accel:float=0.

    def __post_init__(self):
        if self.method!='cruise_lookahead':raise ValueError('unknown native longitudinal mapping')
        if not all(math.isfinite(x) and x>0 for x in (self.lookahead_s,self.max_accel,self.max_brake,self.native_max_speed)):
            raise ValueError('positive finite actuator limits required')

    def update(self,driver,measured_speed,requested_accel,dt):
        if not all(math.isfinite(x) for x in (measured_speed,requested_accel,dt)) or dt<=0:
            raise ValueError('finite physical measurements and positive sample period required')
        v=max(0.,float(measured_speed));a=min(self.max_accel,max(-self.max_brake,float(requested_accel)))
        observed=None if self.last_speed is None else (v-self.last_speed)/dt
        if observed is not None:
            alpha=1-math.exp(-dt/.02)
            self.filtered_accel+=alpha*(observed-self.filtered_accel)
        self.last_speed=v
        target=min(self.native_max_speed,max(0.,v+a*self.lookahead_s))
        driver.setBrakeIntensity(0.)
        driver.setCruisingSpeed(target*3.6)
        return dict(actuation_method=self.method,lookahead_s=self.lookahead_s,
            requested_accel=float(requested_accel),bounded_requested_accel=a,
            target_cruise_speed_m_s=target,measured_speed_m_s=v,
            measured_accel_m_s2=observed,filtered_measured_accel_m_s2=self.filtered_accel,
            native_max_speed_m_s=self.native_max_speed)


def measured_forward_speed(node):
    rotation=node.getOrientation();velocity=node.getVelocity()
    yaw=math.atan2(rotation[3],rotation[0])
    return float(velocity[0]*math.cos(yaw)+velocity[1]*math.sin(yaw))
