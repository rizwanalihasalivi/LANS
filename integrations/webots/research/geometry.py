"""Explicit non-ISO development corridor and conservative rectangular vehicle outline."""
import math
from numba import njit
from core import reference

@njit(cache=True)
def corridor_margin(x,y,heading,path):
    # World-vertical strip +/-1.75 m around y_ref(x), not normal-width ISO geometry.
    maximum=0.
    # Wheel-inclusive width 1.8 m; body spans CG-relative x=-2.0 .. +1.8 m.
    for longitudinal in (-2.,0.,1.8):
        for lateral in (-.9,0.,.9):
            corner_x=x+longitudinal*math.cos(heading)-lateral*math.sin(heading)
            corner_y=y+longitudinal*math.sin(heading)+lateral*math.cos(heading)
            reference_y,_,_=reference(corner_x,*path)
            maximum=max(maximum,abs(corner_y-reference_y))
    return 1.75-maximum
