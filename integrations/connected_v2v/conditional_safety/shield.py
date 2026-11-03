"""Exact-rational reference shield for the contract in THEOREM.md.

Coordinates are front/rear bumper stations on ONE fixed straight corridor.
This is not a formal refinement of the existing bicycle/Webots implementation.
An old observation supplies a retained spatial lower bound, never fresh state.
"""
from dataclasses import dataclass
from fractions import Fraction as F
import math


def rational(value):
    if isinstance(value, bool):
        raise ValueError('boolean is not a physical value')
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('finite rational value required')
    try:
        return F(str(value)) if not isinstance(value, F) else value
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        raise ValueError('finite rational value required') from exc


@dataclass(frozen=True)
class Contract:
    brake: F = F('5.5')
    uncertainty: F = F('.25')
    margin: F = F('2')
    horizon: F = F('.05')
    maximum_command: F = F('2.5')
    quantum: F = F('.25')

    def __post_init__(self):
        for name, value in self.__dict__.items():
            object.__setattr__(self, name, rational(value))
        if min(self.brake, self.margin, self.horizon, self.quantum) <= 0 or self.uncertainty < 0 or self.maximum_command < 0:
            raise ValueError('positive brake/margin/horizon/quantum and nonnegative uncertainty/max command required')

    @property
    def emergency(self):
        return -self.brake-self.uncertainty


def envelope(speed, acceleration, duration):
    """Maximum non-reversing displacement and speed under constant upper a."""
    v, a, h = map(rational, (speed, acceleration, duration))
    if v < 0 or h < 0:
        raise ValueError('nonnegative upper speed and duration required')
    if a < 0 and v+a*h < 0:
        return -v*v/(2*a), F(0)
    return v*h+a*h*h/2, v+a*h


class ContractViolation(ValueError):
    """The theorem is inapplicable; braking does not repair a false premise."""


class SafetyShield:
    def __init__(self, front_upper, speed_upper, *, contract=None):
        self.cfg = contract or Contract()
        self.x, self.v = rational(front_upper), rational(speed_upper)
        if self.v < 0:
            raise ValueError('nonnegative upper speed required')
        self.bounds = {}
        self.history = {}
        self.now = F(0)
        self.rejections = 0

    def observe(self, name, source, sequence, observed, now, lower, ttl):
        """Input adapter MUST establish lower <= actual rear at observation.

        Age/replay checks alone cannot establish sensor containment or identity.
        Taking max of valid lower bounds is sound only for non-reversing objects.
        """
        observed, now, lower, ttl = map(rational, (observed, now, lower, ttl))
        if now < self.now or ttl <= 0:
            raise ValueError('monotonic clock and positive TTL required')
        self.now = now
        key = (name, source)
        old = self.history.get(key)
        valid = (isinstance(name, str) and bool(name) and source in ('radar', 'v2v')
                 and type(sequence) is int and sequence >= 0 and 0 <= observed <= now
                 and now-observed <= ttl and (old is None or sequence > old[0] and observed >= old[1]))
        if not valid:
            self.rejections += 1
            return False
        self.history[key] = (sequence, observed)
        self.bounds[name] = max(lower, self.bounds.get(name, lower))
        return True

    def refine_ego(self, front_upper, speed_upper):
        """Intersect predicted upper envelopes with VALID current sensor bounds."""
        x, v = rational(front_upper), rational(speed_upper)
        if v < 0:
            raise ValueError('nonnegative upper speed required')
        self.x, self.v = min(self.x, x), min(self.v, v)

    def choose(self, nominal):
        if not self.bounds:
            raise ContractViolation('no initially protected obstacle; no clear-road theorem')
        c = self.cfg
        boundary = min(self.bounds.values())
        budget = boundary-self.x-c.margin
        invariant = 2*c.brake*budget-self.v*self.v
        if invariant < 0:
            raise ContractViolation('initial/admission recoverability invariant false')
        nominal = max(c.emergency, min(c.maximum_command, rational(nominal)))
        # Enumerated grid avoids floating root/bisection rounding at the boundary.
        n = (nominal-c.emergency)//c.quantum
        candidates = [c.emergency+k*c.quantum for k in range(int(n), -1, -1)]
        for u in candidates:
            a = u+c.uncertainty
            distance, next_v = envelope(self.v, a, c.horizon)
            cost = 2*c.brake*distance+next_v*next_v
            if cost <= 2*c.brake*budget:
                certificate = dict(x=str(self.x), v=str(self.v), boundary=str(boundary),
                    command=str(u), upper_accel=str(a), displacement=str(distance),
                    next_v=str(next_v), next_x=str(self.x+distance),
                    invariant_scaled=str(invariant), guard_slack_scaled=str(2*c.brake*budget-cost))
                self.x += distance
                self.v = next_v
                return u, certificate
        raise AssertionError('the emergency feasibility lemma was violated')
