"""Causal packet lifecycle and bounded residual predictive authority."""
import math
from common import HERE
import json
import numpy as np
from numba import njit

P = json.loads((HERE / 'protocol.json').read_text())


@njit(cache=True)
def predicted_cost(estimate, actuator, command, previous_command, speed, curvature, gain):
    z = estimate.copy()
    delta = actuator
    cost = 0.
    vyref = (1.4*speed-1650*1.2*speed**3/(2.6*80000))*curvature
    target = np.array([0., vyref, -vyref/speed, speed*curvature])
    ff = (2.6+1650/2.6*(1.4/80000-1.2/80000)*speed**2)*curvature
    old = previous_command
    for step in range(20):
        u = command if step < 5 else max(-.5, min(.5, ff-np.dot(gain, z-target)))
        delta += .01*max(-.35, min(.35, (u-delta)/.05))
        ey, vy, ep, r = z
        front = 80000*(delta-(vy+1.2*r)/speed)
        rear = 80000*(-(vy-1.4*r)/speed)
        z += .01*np.array([vy+speed*ep, (front+rear)/1650-speed*r,
                          r-speed*curvature, (1.2*front-1.4*rear)/4224])
        cost += .01*((z[0]/.5)**2+.2*(z[2]/.1)**2+
                     .01*((z[3]-target[3])/.2)**2+.001*(u/.5)**2+
                     .01*((u-old)/.005)**2)
        old = u
    return cost+.1*((z[0]/.5)**2+.2*(z[2]/.1)**2)


class Controller:
    def __init__(self, mode='predictive'):
        if mode not in ('predictive', 'fixed', 'latency', 'no_recovery', 'lqr'):
            raise ValueError(mode)
        self.mode = mode
        self.packet = None
        self.pending = None
        self.sequence = 0
        self.last_sequence = -1
        self.weight = 0.
        self.good = 0
        self.last_command = 0.
        self.last_costs = (math.nan, math.nan)

    def deliver(self, t):
        if self.pending is not None and self.pending[0] <= t+1e-9:
            self.packet = self.pending[1]
            self.pending = None

    def submit(self, t, residual, service):
        if self.pending is not None:
            return False
        if not math.isfinite(residual) or service < 0:
            raise ValueError('finite residual and nonnegative service required')
        self.sequence += 1
        packet = (self.sequence, t, float(np.clip(residual, -.08, .08)))
        if service == 0:
            self.packet = packet
        else:
            self.pending = (t+service, packet)
        return True

    def choose(self, t, baseline, estimate, actuator, speed, curvature, gain):
        self.last_costs = (math.nan, math.nan)
        def reject(reason):
            self.weight = 0.
            self.good = 0
            self.last_command = baseline
            return baseline, reason
        if self.mode == 'lqr':
            return reject('baseline')
        if self.packet is None:
            return reject('missing')
        seq, observed, residual = self.packet
        age = t-observed
        if not np.isfinite([t, baseline, observed, residual, actuator, speed, curvature, *estimate]).all():
            return reject('nonfinite')
        if age < 0 or age >= .05-1e-12:
            return reject('age')
        if seq < self.last_sequence:
            return reject('sequence')
        self.last_sequence = seq
        if abs(estimate[0]) > 1.5 or abs(estimate[2]) > .25:
            return reject('envelope')
        if self.mode in ('fixed', 'latency'):
            w = .5 if self.mode == 'fixed' else .5*math.exp(-.8*max(0., age*1000-5.))
            self.weight = w
            self.last_command = float(np.clip(baseline+w*residual, -.5, .5))
            return self.last_command, 'fixed' if self.mode == 'fixed' else 'latency'
        base_cost = predicted_cost(estimate, actuator, baseline, self.last_command, speed, curvature, gain)
        best, selected, command = base_cost, 0., baseline
        fresh = min(1., max(0., (.05-age)/.04))
        for cap in (.1, .25, .5):
            w = min(cap*fresh, self.weight+.05)
            u = float(np.clip(baseline+w*residual, -.5, .5))
            cost = predicted_cost(estimate, actuator, u, self.last_command, speed, curvature, gain)
            if cost < best:
                best, selected, command = cost, w, u
        if not np.isfinite([base_cost, best]).all():
            return reject('prediction_invalid')
        self.last_costs = (base_cost, best)
        if selected == 0 or base_cost-best < max(1e-7, .01*base_cost):
            return reject('cost')
        self.good += 1
        if self.mode != 'no_recovery' and self.good < 3:
            self.weight = 0.
            self.last_command = baseline
            return baseline, 'recovery'
        self.weight = selected
        self.last_command = command
        return command, 'accepted'


def observation(state, estimate, speed, curvatures, ctrl, t):
    ey, vy, ep, r = estimate
    packet = ctrl.packet
    value = np.zeros(20, dtype=np.float32)
    value[:9] = [ey/3, ep/.3, (vy+speed*ep)/5, r/.5, speed/25, state[5]/.5,
                 *[k/.02 for k in curvatures]]
    value[9:14] = [ctrl.weight, min(ctrl.good, 3)/3,
                    packet[2]/.08 if packet else 0., (t-packet[1])/.1 if packet else 0.,
                    float(packet is not None)]
    value[18] = ctrl.last_command/.5
    if not np.isfinite(value).all():
        raise ValueError('nonfinite observation')
    return value
