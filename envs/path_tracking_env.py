"""Corrected world-coordinate bicycle plant; action is FULL steering in radians.

This version is incompatible with legacy root checkpoints. Reference geometry
never moves the vehicle. Controllers own fusion; this class owns physics only.
"""
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from models.bicycle_model import VEHICLE_PARAMS
from controllers.lqr_controller import get_lqr_controller
from scenarios.double_lane_change import double_lane_change


class PathTrackingEnv(gym.Env):
    contract = 'world-bicycle-v2'

    def __init__(self, mode='train', vx=25.):
        super().__init__()
        self.mode = mode; self.dt = .01; self.params = VEHICLE_PARAMS.copy()
        self.observation_space = spaces.Box(-np.inf, np.inf, (11,), np.float32)
        self.action_space = spaces.Box(-.5, .5, (1,), np.float32)
        self.vx = float(vx); self.y_ref = None; self.done = True
        self.last_latency = 0.; self.latency_history = []

    @property
    def target_speed(self):
        return self.vx

    @target_speed.setter
    def target_speed(self, value):
        if not np.isfinite(value) or value <= 0:
            raise ValueError('speed must be positive')
        self.vx = float(value)
        self.K_lqr, self.lqr_control = get_lqr_controller(self.vx, self.params)
        # Physical paths are stored against distance, never reindexed by new speed.

    @property
    def car_x(self):
        return self.x_position

    def _generate_reference_path(self):
        self.path_x = np.linspace(0., 300., 3001)
        kind = self.np_random.choice(['DLC', 'Sine']) if self.mode == 'train' else 'DLC'
        self.y_ref = double_lane_change(self.path_x, lane_width=3.5) if kind == 'DLC' else 2.*np.sin(2*np.pi*self.path_x/150.)
        slope = np.gradient(self.y_ref, self.path_x)
        self.path_heading = np.arctan(slope)
        self.path_curvature = np.gradient(slope, self.path_x)/(1+slope*slope)**1.5

    def _get_reference_y(self, x):
        return float(np.interp(x, self.path_x, self.y_ref))

    get_ref_y = _get_reference_y

    def _get_reference_heading(self, x):
        return float(np.interp(x, self.path_x, self.path_heading))

    def curvature(self):
        return float(np.interp(self.x_position, self.path_x, self.path_curvature))

    def _refresh(self):
        x, y, psi, vy, r = self.physical
        self.x_position = float(x); self.y_actual = float(y)
        ep = float(np.arctan2(np.sin(psi-self._get_reference_heading(x)), np.cos(psi-self._get_reference_heading(x))))
        self.state = np.array([y-self._get_reference_y(x), vy+self.vx*ep, ep, r-self.vx*self.curvature()])

    def _get_future_error(self, steps):
        return self.y_actual-self._get_reference_y(self.x_position+steps*self.vx*self.dt)

    def _get_observation(self):
        return np.array([*self.state, self.vx, *[self._get_future_error(i) for i in range(1,5)],
                         self.last_latency, np.mean(self.latency_history) if self.latency_history else 0.], dtype=np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.target_speed = self.vx
        self._generate_reference_path()
        options = options or {}
        self.physical = np.array([0., self._get_reference_y(0.)+options.get('lateral_error',0.),
                                  self._get_reference_heading(0.)+options.get('heading_error',0.), 0., 0.])
        self.t_step = 0; self.prev_steering = 0.; self.last_latency = 0.; self.latency_history = []; self.done = False
        self._refresh()
        return self._get_observation(), {'contract':self.contract}

    def _derivative(self, z, command):
        _, _, psi, vy, r = z; p = self.params; v = self.vx
        front = p['Cf']*(command-(vy+p['lf']*r)/v)
        rear = p['Cr']*(-(vy-p['lr']*r)/v)
        return np.array([v*np.cos(psi)-vy*np.sin(psi), v*np.sin(psi)+vy*np.cos(psi), r,
                         (front+rear)/p['m']-v*r, (p['lf']*front-p['lr']*rear)/p['Iz']])

    def step(self, action):
        if self.done:
            raise RuntimeError('reset required after termination/truncation')
        raw = np.asarray(action).reshape(-1)
        if raw.size != 1 or not np.isfinite(raw).all():
            raise ValueError('one finite steering command required')
        command = float(np.clip(raw[0], -.5, .5)); z = self.physical; dt = self.dt
        a=self._derivative(z,command); b=self._derivative(z+dt*a/2,command)
        c=self._derivative(z+dt*b/2,command); d=self._derivative(z+dt*c,command)
        self.physical = z+dt*(a+2*b+2*c+d)/6
        self.t_step += 1; self._refresh()
        ey, _, ep, _ = self.state
        failed = bool(abs(ey)>2.5 or abs(ep)>.6 or not np.isfinite(self.physical).all())
        truncated = self.t_step >= 1000
        reward = float(np.exp(-(ey/.5)**2-.2*(ep/.1)**2)+.05-.005*(command/.5)**2
                       -.001*((command-self.prev_steering)/.5)**2-10*failed)
        self.prev_steering=command; self.done=failed or truncated
        info = dict(error=ey, heading_error=ep, x_phys=self.x_position, y_phys=self.y_actual,
                    y_ref=self._get_reference_y(self.x_position), steering=command, total_steer=command,
                    command_time_s=(self.t_step-1)*dt, state_time_s=self.t_step*dt,
                    latency=self.last_latency, failed=failed, contract=self.contract)
        return self._get_observation(), reward, failed, bool(truncated), info
