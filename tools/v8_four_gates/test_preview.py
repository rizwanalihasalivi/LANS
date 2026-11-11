import numpy as np
import pytest
from .preview_centered import gains


@pytest.mark.parametrize('speed,stiffness',[(8.,.8),(12.,1.),(16.,1.2)])
def test_preview_has_no_constant_curvature_steering_bias(speed,stiffness):
    k,p,eq=gains(speed,stiffness,4.,16.,8.);curvature=.004
    # At the independent steady bicycle equilibrium, the steering increment
    # must vanish. Magnitude penalties must not bias exact steady tracking.
    assert -k@(eq*curvature)+p@np.full(len(p),curvature)==pytest.approx(0.,abs=1e-10)
