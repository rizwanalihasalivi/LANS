import math
import numpy as np
import pytest
from integrations.unified_lans.traffic import contact_time,conflict_time
from .traffic_guard import expanding_contact,occupancy_contact


def test_future_uncertainty_catches_a_nominal_near_tangent_miss():
    ego=np.array([0.,0.,0.,6.,0.,0.]);other=np.array([7.1,.005,math.pi/2,6.9,0.,0.])
    assert math.isinf(contact_time(ego,other,5.1))
    assert 0<expanding_contact(ego,other,5.1,.6)<2.


def test_vehicle_center_passing_does_not_erase_its_remaining_occupancy():
    ego=np.array([0.,0.,0.,4.,0.,0.]);other=np.array([4.,.1,math.pi/2,4.,0.,0.])
    assert math.isinf(conflict_time(ego,other,3.))
    assert occupancy_contact(ego,other,3.,0.)==pytest.approx(.25)
    other[1]=4.
    assert math.isinf(occupancy_contact(ego,other,3.,0.))


@pytest.mark.parametrize('growth',[0.,.6])
def test_parallel_stationary_and_receding_contacts(growth):
    ego=np.array([0.,0.,0.,0.,0.,0.]);other=np.array([10.,0.,0.,0.,0.,0.])
    t=expanding_contact(ego,other,5.,growth)
    assert t==pytest.approx(5/growth) if growth else math.isinf(t)
    other[3]=2.
    assert math.isinf(expanding_contact(ego,other,5.,growth))
