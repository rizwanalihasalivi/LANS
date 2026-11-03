"""Shared SI-unit bicycle plant/predictor and route geometry.

Positive steering/heading is left. State is x,y,heading,speed,lateral-speed,yaw-rate.
Nominal prediction and the test plant can have different cornering stiffness.
"""
from dataclasses import dataclass
from functools import lru_cache
import math
import numpy as np
from controllers.lqr_controller import get_lqr_controller
from models.bicycle_model import VEHICLE_PARAMS


@dataclass(frozen=True)
class Config:
    dt: float = .05
    steering_limit: float = .5
    steering_rate: float = .6
    residual_limit: float = .08
    max_accel: float = 2.5
    max_brake: float = 6.
    ego_ttl: float = .2
    traffic_ttl: float = .4
    proposal_ttl: float = .15
    horizon: float = .5
    vehicle_radius: float = 2.3
    buffer: float = .5
    uncertainty_rate: float = .6

    def __post_init__(self):
        if any(not math.isfinite(v) or v <= 0 for v in self.__dict__.values()):
            raise ValueError('configuration values must be finite and positive')


@dataclass(frozen=True)
class Command:
    steering: float = 0.
    accel: float = 0.


@dataclass(frozen=True)
class Route:
    kind: str = 'straight'

    def geometry(self, x):
        if self.kind == 'straight':
            return 0., 0., 0.
        if self.kind == 'sine':
            w = 2*math.pi/120
            y, d, dd = 1.5*math.sin(w*x), 1.5*w*math.cos(w*x), -1.5*w*w*math.sin(w*x)
        elif self.kind == 'lane_change':
            q = (x-30)/12
            t = math.tanh(q)
            y, d, dd = 1.75*(1+t), 1.75*(1-t*t)/12, -3.5*t*(1-t*t)/144
        else:
            raise ValueError('unknown route: '+self.kind)
        return y, math.atan(d), dd/(1+d*d)**1.5


def errors(state, route):
    x,y,psi,v,vy,r = state
    ref, heading, curvature = route.geometry(x)
    ep = math.atan2(math.sin(psi-heading), math.cos(psi-heading))
    return np.array([y-ref, vy+v*ep, ep, r-v*curvature]), curvature


@lru_cache(maxsize=128)
def _lqr(speed):
    return get_lqr_controller(speed)[1]


def baseline(state, route):
    e,k = errors(state,route)
    return _lqr(max(2., round(float(state[3])*2)/2))(e,k)


def constrain(command, previous, cfg, interval=None):
    if not np.isfinite([command.steering,command.accel]).all():
        raise ValueError('nonfinite command')
    delta = cfg.steering_rate*(cfg.dt if interval is None else interval)
    steer = np.clip(command.steering, previous.steering-delta, previous.steering+delta)
    return Command(float(np.clip(steer,-cfg.steering_limit,cfg.steering_limit)),
                   float(np.clip(command.accel,-cfg.max_brake,cfg.max_accel)))


def advance(state, command, duration, stiffness=1.):
    """RK4 with <=10 ms substeps; low-speed kinematic blend avoids 1/v singularity."""
    if duration < 0 or not math.isfinite(duration):
        raise ValueError('invalid prediction interval')
    z = np.asarray(state,dtype=float).copy()
    if z.shape != (6,) or not np.isfinite(z).all() or stiffness <= 0:
        raise ValueError('finite six-state vehicle required')
    def derivative(s):
        _,_,psi,v,vy,r = s
        v = max(0.,v)
        if v < 2.:
            target_r = v*math.tan(command.steering)/2.6
            dy,dr = -10*vy,10*(target_r-r)
        else:
            p = VEHICLE_PARAMS
            f = p['Cf']*stiffness*(command.steering-(vy+p['lf']*r)/v)
            b = p['Cr']*stiffness*(-(vy-p['lr']*r)/v)
            dy,dr = (f+b)/p['m']-v*r,(p['lf']*f-p['lr']*b)/p['Iz']
        a = command.accel if v > 0 or command.accel > 0 else 0.
        return np.array([v*math.cos(psi)-vy*math.sin(psi),v*math.sin(psi)+vy*math.cos(psi),r,a,dy,dr])
    count = max(1,math.ceil(duration/.01)); h = duration/count
    for _ in range(count):
        a = derivative(z); b = derivative(z+h*a/2); c = derivative(z+h*b/2); d = derivative(z+h*c)
        z += h*(a+2*b+2*c+d)/6
        z[3] = max(0.,z[3])
    return z
