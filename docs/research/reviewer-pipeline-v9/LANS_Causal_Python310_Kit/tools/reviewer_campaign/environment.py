"""Shared causal training/evaluation plant, mirrored sensing and executed reward."""
import common
import math
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from supervisor import Controller, observation, P
from comparison import configure_lqr
from kernels import measure, lqr, path_values
from plant import advance
from core import GAINS

PATHS = {'sine120': (0., 2.5, 120., .3), 'dlc220': (1., 0., 0., 0.),
         'heldout_sine145': (0., 1.7, 145., -.2)}
CASES = {'nominal': (.9, 1., 0.), 'tire': (.9, .7, 0.),
         'delay20': (.9, 1., .02), 'delay100': (.9, 1., .1),
         'stall1000': (.9, 1., 1.)}


class CausalEnv(gym.Env):
    def __init__(self, pair=0, slot=0, seed=2701, mode='predictive', case=None):
        super().__init__()
        configure_lqr()
        self.gains = np.array([GAINS[v] for v in (15, 20, 25)])
        self.pair, self.slot, self.initial_seed = pair, slot, seed
        self.mode, self.fixed_case = mode, case
        self.action_space = spaces.Discrete(5)
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(20,), dtype=np.float32)
        self.index = -1

    def reset(self, *, seed=None, options=None):
        super().reset(seed=self.initial_seed if self.index < 0 and seed is None else seed)
        self.index += 1
        if self.fixed_case:
            speed, path, sign, scenario, noise_id = self.fixed_case
        else:
            speed = int(self.np_random.choice([15, 20, 25]))
            path = ['sine120', 'dlc220'][int(self.np_random.integers(2))]
            sign = int(self.np_random.choice([-1, 1]))
            scenario = list(CASES)[:4][int(self.np_random.integers(4))]
            noise_id = P['training_noise_base']+self.pair*1000000+self.slot*10000+self.index
        self.speed, self.path_name, self.sign, self.scenario = speed, path, sign, scenario
        self.path = PATHS[path]
        self.mu, self.stiffness, self.service = CASES[scenario]
        self.noise_id = noise_id
        self.horizon = int(math.ceil((220/speed+2)/.01))
        self.noise = np.random.default_rng(noise_id).normal(0, [.03, math.radians(.17), .01, .1], (self.horizon+1, 4))
        y, h, _ = path_values(0., self.path)
        self.state = np.array([0., sign*(y+.15), sign*(h+.01), 0., 0., 0.])
        self.estimate = np.zeros(4)
        self.cov = np.eye(4)*.01
        self.previous = np.zeros(4)
        self.ctrl = Controller(self.mode)
        self.tick = 0
        self.last_executed = 0.
        self._sense()
        return self.obs.copy(), {'noise_id': noise_id}

    def _sense(self):
        # Canonical coordinates implement an exact physical left/right mirror.
        # All lateral quantities, initial errors and sensor-noise signs mirror.
        transform = np.array([1., self.sign, self.sign, self.sign, self.sign, self.sign])
        canonical = self.state*transform
        previous = self.previous.copy()
        previous[:3] *= self.sign
        est, self.cov, previous, self.measured_speed, k = measure(
            canonical, float(self.speed), self.path, self.noise[self.tick], 0,
            self.estimate*self.sign, self.cov, previous, self.tick == 0, 1.)
        self.estimate = est*self.sign
        previous[:3] *= self.sign
        self.previous = previous
        self.curvature = k*self.sign
        self.baseline, self.gain = lqr(self.estimate, self.measured_speed, self.curvature, self.gains)
        previews = [self.sign*path_values(self.state[0]+d, self.path)[2] for d in (0., 10., 20.)]
        self.ctrl.deliver(self.tick*.01)
        self.obs = observation(self.state, self.estimate, self.measured_speed, previews, self.ctrl, self.tick*.01)

    def step(self, action):
        index = int(np.asarray(action).item())
        if not 0 <= index < 5:
            raise ValueError('categorical action required')
        return self.step_residual(P['candidates_rad'][index])

    def step_residual(self, residual):
        t = self.tick*.01
        available = self.ctrl.pending is None
        submitted = self.ctrl.submit(t, residual, self.service)
        packet = self.ctrl.packet
        start_weight = self.ctrl.weight
        command, reason = self.ctrl.choose(t, self.baseline, self.estimate, self.state[5],
                                           self.measured_speed, self.curvature, self.gain)
        old = self.state[5]
        self.state = advance(self.state, command, float(self.speed), self.mu, self.stiffness)
        self.tick += 1
        y, h, _ = path_values(self.state[0], self.path)
        ey, ep = self.state[1]-self.sign*y, self.state[2]-self.sign*h
        failed = abs(ey) > 2.5 or abs(ep) > .6 or not np.isfinite(self.state).all()
        reward = (-(ey/.5)**2-.2*(ep/.1)**2-.005*(command/.5)**2
                  -.001*((command-self.last_executed)/.005)**2-10*failed)
        info = dict(tick=self.tick-1, observation_time_s=t, command_time_s=t,
                    x=float(self.state[0]), y=float(self.state[1]), heading=float(self.state[2]),
                    reference_y=float(self.sign*y), reference_heading=float(self.sign*h),
                    lateral_error=float(ey), heading_error=float(ep), command=float(command),
                    baseline=float(self.baseline), actuator=float(self.state[5]),
                    steering_rate=float((self.state[5]-old)/.01), weight=float(self.ctrl.weight),
                    previous_weight=float(start_weight), reason=reason, submitted=bool(submitted),
                    worker_available=bool(available), proposed_residual=float(residual),
                    packet_seq=packet[0] if packet else -1,
                    packet_observed_s=packet[1] if packet else None,
                    packet_age_s=t-packet[1] if packet else None,
                    packet_residual=packet[2] if packet else 0., reward=float(reward),
                    failed=bool(failed), **{f'obs{i}':float(v) for i,v in enumerate(self.obs)})
        self.last_executed = command
        done = self.tick >= self.horizon
        if not failed and not done:
            self._sense()
        return self.obs.copy(), float(reward), bool(failed), bool(done), info
