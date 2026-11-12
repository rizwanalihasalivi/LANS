import pytest
from .actuation import LongitudinalActuator,TorqueActuator


class Driver:
    def setBrakeIntensity(self,value):self.brake=value
    def setCruisingSpeed(self,value):self.cruise=value
    def setGear(self,value):self.gear=value
    def setThrottle(self,value):self.throttle=value


def test_target_speed_is_not_an_invented_hard_limit():
    d=Driver();a=LongitudinalActuator(lookahead_s=.2)
    row=a.update(d,16.,2.5,.001)
    assert d.cruise==pytest.approx(16.5*3.6)
    assert row['target_cruise_speed_m_s']>16.
    assert row['measured_accel_m_s2'] is None


def test_actuator_clamps_only_original_acceleration_and_native_speed_bounds():
    d=Driver();a=LongitudinalActuator(lookahead_s=1.)
    row=a.update(d,49.,100.,.001)
    assert row['bounded_requested_accel']==2.5 and row['target_cruise_speed_m_s']==50.
    row=a.update(d,.1,-100.,.001)
    assert row['bounded_requested_accel']==-6. and row['target_cruise_speed_m_s']==0.
    with pytest.raises(ValueError):a.update(d,float('nan'),0.,.001)
    with pytest.raises(ValueError):a.update(d,10.,0.,0.)


def native_longitudinal_acceleration(driver,speed):
    """Independent force balance for the frozen drivetrain, not a Webots test."""
    radius=.32
    motor_speed=speed/radius*6.5
    motor_torque=min(250.,100000./max(1.,motor_speed))*driver.throttle
    drive_force=motor_torque*6.5/radius
    brake_force=4*1000.*driver.brake/radius
    damping_force=4*.2*speed/radius**2
    return (drive_force-brake_force-damping_force)/1650.


@pytest.mark.parametrize('speed',[8.,12.,16.,20.])
@pytest.mark.parametrize('requested',[2.5,0.,-6.])
def test_torque_mapping_balances_acceleration_without_body_state_writes(speed,requested):
    # Driver deliberately supplies only public drivetrain methods. Positive
    # throttle must supply m*a and wheel loss; braking uses all four wheels.
    d=Driver();row=TorqueActuator().update(d,speed,requested,.001)
    assert native_longitudinal_acceleration(d,speed)==pytest.approx(requested,abs=1e-12)
    assert d.gear==2
    assert 0<=d.throttle<=1 and 0<=d.brake<=1
    assert not (d.throttle>0 and d.brake>0)
    assert row['measured_accel_m_s2'] is None


def test_torque_feedback_uses_past_measurements_and_recovers_under_extra_drag():
    # A point-mass drivetrain check exercises feedback under a force mismatch;
    # it does not stand in for the separate actual native calibration.
    d=Driver();a=TorqueActuator();speed=16.;actual=[]
    for _ in range(2000):
        row=a.update(d,speed,2.5,.001)
        acceleration=native_longitudinal_acceleration(d,speed)-.2
        speed+=acceleration*.001;actual.append(acceleration)
    assert actual[0]==pytest.approx(2.3)
    assert abs(sum(actual[-100:])/100-2.5)<abs(actual[0]-2.5)
    assert -0.5<=a.integral<=0.5
    assert row['feedback_accel_m_s2']>0


def test_native_power_and_brake_saturation_are_explicit():
    d=Driver();a=TorqueActuator();row=a.update(d,50.,100.,.001)
    assert row['bounded_requested_accel']==2.5
    assert d.throttle==1. and d.brake==0.
    # At50m/s100kW cannot supply1650kg*2.5m/s²; saturation is retained.
    assert native_longitudinal_acceleration(d,50.)<2.5
    row=a.update(d,16.,-100.,.001)
    assert row['bounded_requested_accel']==-6.
    assert d.throttle==0. and 0<d.brake<=1.
    a.update(d,0.,-6.,.001)
    assert d.throttle==d.brake==0.
    for speed,accel,dt in [(float('nan'),0.,.001),(16.,float('inf'),.001),(16.,0.,0.)]:
        with pytest.raises(ValueError):a.update(d,speed,accel,dt)
