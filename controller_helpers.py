import numpy as np

def saturate(u, umin, umax):
    """Elementwise saturation."""
    return np.minimum(np.maximum(u, umin), umax)

def steering_feedforward(curvature, wheelbase):
    """
    Simple geometric feedforward for small angles:
    delta_ff = arctan(L * curvature). For small L*k, arctan approx L*k.
    """
    return np.arctan(wheelbase * curvature)

class RateLimiter:
    """Simple symmetric rate limiter for actuator commands."""
    def __init__(self, rate_limit):
        self.rate_limit = rate_limit
        self.last_u = None

    def __call__(self, u_cmd, dt):
        if self.last_u is None:
            self.last_u = u_cmd
            return u_cmd
        max_delta = self.rate_limit * dt
        delta = np.clip(u_cmd - self.last_u, -max_delta, max_delta)
        self.last_u = self.last_u + delta
        return self.last_u
