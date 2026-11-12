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


@dataclass
class TorqueActuator:
    """Force feedforward and measured acceleration PI through native drivetrain.

    All body/tire integration remains in Webots. Unlike moving cruise targets,
    this uses Driver TORQUE mode, its actual electric-engine curve and four
    physical brakes. Configuration is shared by every higher-level controller.
    """
    mass:float=1650.
    tire_radius:float=.32
    engine_max_torque:float=250.
    engine_max_power:float=100000.
    gear:int=2
    gear_ratio:float=6.5
    brake_coefficient:float=1000.
    wheel_damping:float=.2
    max_accel:float=2.5
    max_brake:float=6.
    kp:float=.1
    ki:float=.2
    last_speed:float|None=None
    filtered_accel:float=0.
    integral:float=0.
    elapsed:float=0.
    previous_sign:int=0

    def update(self,driver,measured_speed,requested_accel,dt):
        if not all(math.isfinite(x) for x in (measured_speed,requested_accel,dt)) or dt<=0:
            raise ValueError('finite physical measurements and positive sample period required')
        v=max(0.,float(measured_speed));a=min(self.max_accel,max(-self.max_brake,float(requested_accel)))
        observed=None if self.last_speed is None else (v-self.last_speed)/dt
        if observed is not None:self.filtered_accel+=(1-math.exp(-dt/.02))*(observed-self.filtered_accel)
        self.last_speed=v;self.elapsed+=dt
        sign=1 if a>0 else (-1 if a<0 else 0)
        if sign!=self.previous_sign:self.integral=0.;self.previous_sign=sign
        error=a-self.filtered_accel
        feedback=0.
        if self.elapsed>=.1 and observed is not None:
            self.integral=min(.5,max(-.5,self.integral+error*dt))
            feedback=self.kp*error+self.ki*self.integral
        # HingeJoint wheel loss is D*omega per wheel; compensate the same
        # explicitly frozen native damping instead of changing the high-level
        # requested acceleration or importing a measured future speed.
        rolling_force=4*self.wheel_damping*v/(self.tire_radius**2)
        force=self.mass*(a+feedback)+rolling_force
        if a<=0 and v<.02:force=0.;self.integral=0.
        omega=max(1.,v/self.tire_radius*self.gear_ratio)
        available=min(self.engine_max_torque,self.engine_max_power/omega)*self.gear_ratio
        throttle=min(1.,max(0.,force*self.tire_radius/max(available,1e-9)))
        brake=min(1.,max(0.,-force*self.tire_radius/(4*self.brake_coefficient)))
        driver.setGear(self.gear);driver.setThrottle(throttle);driver.setBrakeIntensity(brake)
        return dict(actuation_method='torque_pi',bounded_requested_accel=a,requested_accel=float(requested_accel),
            measured_speed_m_s=v,measured_accel_m_s2=observed,filtered_measured_accel_m_s2=self.filtered_accel,
            feedback_accel_m_s2=feedback,feedforward_force_n=self.mass*a,requested_force_n=force,
            modeled_wheel_damping_force_n=rolling_force,wheel_joint_damping=self.wheel_damping,
            throttle=throttle,brake_intensity=brake,gear=self.gear,gear_ratio=self.gear_ratio,
            engine_model_used=True,estimated_motor_rad_s=omega,brake_coefficient_nm=self.brake_coefficient)
