import math
import numpy as np
import pytest
from integrations.unified_lans.traffic import conflict_time


def test_conflict_starts_at_first_simultaneous_occupancy():
    # Intersection at (20,0): ego occupancy [1.5,2.5], other [0.5,2.5].
    ego=np.array([0.,0.,0.,10.,0.,0.])
    other=np.array([20.,-7.5,math.pi/2,5.,0.,0.])
    assert conflict_time(ego,other,5.)==pytest.approx(1.5)
    assert conflict_time(other,ego,5.)==pytest.approx(1.5)


def test_one_vehicle_already_in_zone_does_not_make_future_overlap_immediate():
    ego=np.array([0.,0.,0.,10.,0.,0.])
    other=np.array([20.,-1.,math.pi/2,2.,0.,0.])
    assert conflict_time(ego,other,5.)==pytest.approx(1.5)


def test_current_joint_occupancy_and_disjoint_intervals():
    ego=np.array([0.,0.,0.,10.,0.,0.])
    assert conflict_time(ego,np.array([1.,-1.,math.pi/2,10.,0.,0.]),5.)==0.
    assert math.isinf(conflict_time(ego,np.array([20.,-100.,math.pi/2,5.,0.,0.]),5.))
