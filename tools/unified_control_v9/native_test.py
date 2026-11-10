"""Coordinate/unit checks for the native sensor bridge, without Webots imports."""
import math
import numpy as np
import pytest
from tools.unified_campaign.study import StudyRoute
from .native_adapter import Frame,measured_state


def test_map_offset_is_rigid_and_preserves_measured_velocity():
    state=np.array([23.,-9.,1.1,12.,.2,-.04]);original=state.copy()
    route=StudyRoute('sine',1,9.,1.15);frame=Frame(state,route,.3,.005)
    mapped=frame.transform(state);y,h,_=route.geometry(0.)
    np.testing.assert_allclose(mapped,[0.,y+.3,h+.005,12.,.2,-.04],atol=1e-12)
    np.testing.assert_array_equal(state,original)
    other=state.copy();other[:2]+=[3.,4.]
    assert np.linalg.norm(frame.transform(other)[:2]-mapped[:2])==pytest.approx(5.)


def test_native_sensor_body_axes_cg_and_left_sign():
    class Node:
        def getPosition(self):return [10.,20.,.3]
        def getOrientation(self):return [0.,-1.,0.,1.,0.,0.,0.,0.,1.]
        def getVelocity(self):return [-.4,8.,0.,0.,0.,.2]
    class Sensor:
        def __init__(self,value):self.value=value
        def getValue(self):return self.value
    state,steering=measured_state(Node(),Sensor(-.025),Sensor(-.035))
    np.testing.assert_allclose(state,[10.,21.4,math.pi/2,8.,.4,.2],atol=1e-12)
    assert steering==pytest.approx(.03)


def test_sensor_nonfinite_is_rejected():
    class Node:
        def getPosition(self):return [float('nan'),0.,0.]
        def getOrientation(self):return [1.,0.,0.,0.,1.,0.,0.,0.,1.]
        def getVelocity(self):return [1.,0.,0.,0.,0.,0.]
    class Sensor:
        def getValue(self):return 0.
    with pytest.raises(ValueError,match='nonfinite'):measured_state(Node(),Sensor(),Sensor())
