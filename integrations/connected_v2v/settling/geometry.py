"""Route-normal steering without a forward-monotone Cartesian graph restriction."""
from functools import lru_cache
import math
import numpy as np
from controllers.lqr_controller import get_lqr_controller
from integrations.connected_v2v.autonomy.road import Road


@lru_cache(maxsize=128)
def scheduled(speed):return get_lqr_controller(speed)[1]


class CircularRoad(Road):
    def geometry(self,x):
        # Compatibility only for the frozen inner follower's temporary steering;
        # the selected output uses route_steering below on the full unwrapped arc.
        if not self.radius:return 0.,0.,0.
        q=max(-.99999999,min(.99999999,x/self.radius))
        return self.radius-self.radius*math.sqrt(1-q*q),math.asin(q),1/self.radius


def route_steering(state,road,offset=0.):
    s,d,heading=road.project(state[:2])
    e=math.atan2(math.sin(state[2]-heading),math.cos(state[2]-heading))
    v=max(0.,float(state[3]));vy=float(state[4]);yaw=float(state[5])
    tangential=v*math.cos(e)-vy*math.sin(e)
    lateral=v*math.sin(e)+vy*math.cos(e)
    curvature=1/(road.radius-offset) if road.radius else 0.
    error=np.array([d-offset,lateral,e,yaw-tangential*curvature])
    return scheduled(max(2.,round(v*2)/2))(error,curvature)
