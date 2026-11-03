"""Known single-route geometry, not a source of vehicle or membership truth."""
from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class Road:
    radius: float = 0.

    def __post_init__(self):
        if not math.isfinite(self.radius) or self.radius < 0:
            raise ValueError('nonnegative finite radius required')

    def position(self, s, d=0.):
        if not self.radius:
            return np.array([s, d])
        a = s/self.radius
        return np.array([(self.radius-d)*math.sin(a),
                         self.radius-(self.radius-d)*math.cos(a)])

    def project(self, position):
        x, y = position
        if not self.radius:
            return float(x), float(y), 0.
        a = math.atan2(x, self.radius-y)
        return self.radius*a, self.radius-math.hypot(x, self.radius-y), a

    def geometry(self, x):
        if not self.radius:
            return 0., 0., 0.
        # The validation fixture is restricted to the forward monotone arc.
        if abs(x) >= .9*self.radius:
            raise ValueError('outside declared circular fixture')
        return self.radius-math.sqrt(self.radius**2-x*x), math.asin(x/self.radius), 1/self.radius

    def canonical(self, state):
        s, d, heading = self.project(state[:2])
        angle = state[2]-heading
        speed = state[3]*math.cos(angle)-state[4]*math.sin(angle)
        lateral = state[3]*math.sin(angle)+state[4]*math.cos(angle)
        return s, d, speed, lateral
