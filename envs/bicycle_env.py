import gymnasium as gym
import numpy as np
from gymnasium import spaces
from path_utils import generate_double_lane_change  # Reuse your path generator

class BicycleEnv(gym.Env):
    """
    Gymnasium environment for PPO training on 2-DOF bicycle model path tracking.
    - State: [e_y, e_ψ, v_y, r, vx] (lateral error, heading error, lateral vel, yaw rate, long. speed)
    - Action: steering delta (rad) in [-0.4, 0.4]
    - Reward: - (e_y² + k_ψ e_ψ²) - k_smooth |δ| - k_rate |δ - prev_δ|
    - Episode ends on large error (>2m) or timeout
    """
    metadata = {"render_modes": ["human"], "render_fps": 30}

    def __init__(self,
                 dt=0.01,
                 vx=10.0,                # Source scenario: low speed
                 max_episode_steps=2000,
                 wheelbase=2.7,
                 m=1500.0,
                 Iz=3000.0,
                 lf=1.1,
                 lr=1.6,
                 Cf=80000.0,
                 Cr=80000.0,
                 steering_limit=0.4,
                 steering_rate_limit=1.0):
        super().__init__()

        self.dt = dt
        self.vx = float(vx)
        self.max_episode_steps = max_episode_steps

        # Vehicle params (same as LQR baseline)
        self.m = m
        self.Iz = Iz
        self.lf = lf
        self.lr = lr
        self.Cf = Cf
        self.Cr = Cr

        # Action space: steering δ
        self.steering_limit = steering_limit
        self.steering_rate_limit = steering_rate_limit
        self.action_space = spaces.Box(low=-steering_limit, high=steering_limit, shape=(1,), dtype=np.float32)

        # Observation space: [e_y, e_ψ, v_y, r, vx]
        obs_high = np.array([5.0, np.pi/2, 5.0, 2.0, 30.0], dtype=np.float32)
        self.observation_space = spaces.Box(low=-obs_high, high=obs_high, dtype=np.float32)

        # Internal state
        self.state = None              # [e_y, e_ψ, v_y, r, vx]
        self.current_pos = None        # [x, y, ψ]
        self.prev_steering = 0.0
        self.current_step = 0

        # Reference path (double lane change)
        self.ref_path = generate_double_lane_change()  # Assume returns (x, y, psi_ref) arrays
        self.ref_x = self.ref_path[:, 0]
        self.ref_y = self.ref_path[:, 1]
        self.ref_psi = self.ref_path[:, 2]

    def reset(self, *, seed=None, options=None):
        """
        Reset to initial state.
        """
        super().reset(seed=seed)

        self.current_step = 0
        self.prev_steering = 0.0

        # Initial state: on path, zero errors, zero velocities
        self.current_pos = np.array([0.0, 0.0, 0.0], dtype=np.float32)  # [x, y, ψ]
        self.state = np.array([0.0, 0.0, 0.0, 0.0, self.vx], dtype=np.float32)  # [e_y, e_ψ, v_y, r, vx]

        return self.state, {}

    def step(self, action):
        action = np.clip(action[0], -self.steering_limit, self.steering_limit)

        # Rate limit steering (smooth control)
        delta = np.clip(action, self.prev_steering - self.steering_rate_limit * self.dt,
                        self.prev_steering + self.steering_rate_limit * self.dt)
        self.prev_steering = delta

        # Get current dynamics matrices
        A, B = self._get_continuous_matrices()

        # Current state vector
        x = self.state[:4]  # [e_y, e_ψ, v_y, r]

        # Continuous dynamics: dx/dt = A x + B δ
        x_dot = A @ x + B.flatten() * delta

        # Simple Euler integration (for speed; can upgrade to RK4 later)
        x_next = x + x_dot * self.dt

        # Update global position (kinematic)
        psi = self.current_pos[2] + x_next[1] * self.dt  # yaw rate integration
        x_pos = self.current_pos[0] + self.vx * np.cos(psi) * self.dt
        y_pos = self.current_pos[1] + self.vx * np.sin(psi) * self.dt
        self.current_pos = np.array([x_pos, y_pos, psi])

        # Update errors (find closest point on ref path)
        idx = np.argmin(np.abs(self.ref_x - x_pos))
        ref_y = self.ref_y[idx]
        ref_psi = self.ref_psi[idx]
        e_y = y_pos - ref_y
        e_ψ = psi - ref_psi

        # New state
        self.state = np.array([e_y, e_ψ, x_next[2], x_next[3], self.vx], dtype=np.float32)

        # Reward: negative errors + smoothness penalties
        reward = - (e_y**2 + 0.5 * e_ψ**2) - 0.1 * abs(delta) - 0.05 * abs(delta - self.prev_steering)

        # Done conditions
        self.current_step += 1
        terminated = abs(e_y) > 2.0 or self.current_step >= self.max_episode_steps
        truncated = False

        if terminated and abs(e_y) > 2.0:
            reward -= 100.0  # big penalty for going off-track

        info = {"e_y": e_y, "e_ψ": e_ψ, "steering": delta}

        return self.state, reward, terminated, truncated, info

    def _get_continuous_matrices(self):
        """Same A, B as in your LQR baseline (copy from lqr_utils or hardcode)"""
        m, Iz, lf, lr, Cf, Cr, vx = self.m, self.Iz, self.lf, self.lr, self.Cf, self.Cr, self.vx

        A = np.array([
            [-2*(Cf+Cr)/(m*vx), -vx - 2*(Cf*lf - Cr*lr)/(m*vx), 0, 0],
            [-2*(Cf*lf - Cr*lr)/(Iz*vx), -2*(Cf*lf**2 + Cr*lr**2)/(Iz*vx), 0, 0],
            [1, 0, 0, vx],
            [0, 1, 0, 0]
        ])

        B = np.array([
            [2*Cf/m],
            [2*Cf*lf/Iz],
            [0],
            [0]
        ])

        return A, B

    def render(self):
        """Optional: simple text or matplotlib render (for later visualization)"""
        pass