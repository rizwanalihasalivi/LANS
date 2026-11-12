import pytest
from .actuation import LongitudinalActuator


class Driver:
    def setBrakeIntensity(self,value):self.brake=value
    def setCruisingSpeed(self,value):self.cruise=value


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
