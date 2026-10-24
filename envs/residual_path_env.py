"""One fusion owner: normalized residual -> LQR + 0.08 rad residual -> plant."""
import numpy as np
from gymnasium import spaces
from envs.path_tracking_env import PathTrackingEnv


class ResidualPathEnv(PathTrackingEnv):
    contract = 'world-bicycle-residual-v2'

    def __init__(self, mode='train', vx=25.):
        super().__init__(mode, vx)
        self.action_space = spaces.Box(-1., 1., (1,), np.float32)

    def step(self, action):
        raw = np.asarray(action).reshape(-1)
        if raw.size != 1 or not np.isfinite(raw).all():
            raise ValueError('one finite normalized residual required')
        baseline = self.lqr_control(self.state, self.curvature())
        correction = .08*float(np.clip(raw[0], -1., 1.))
        command = float(np.clip(baseline+correction, -.5, .5))
        obs, reward, terminated, truncated, info = super().step([command])
        info.update(lqr_steer=baseline, rl_steer=correction, beta=1.)
        return obs, reward, terminated, truncated, info
