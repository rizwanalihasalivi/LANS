import numpy as np
import gymnasium as gym
from gymnasium import spaces
from integrators import rk4_step
from controller_helpers import saturate, steering_feedforward

class LQREnv(gym.Env):
    """
    Gymnasium environment wrapping a linearized 2-DOF bicycle model for lateral/path tracking.

    State: [vy, r, y, psi_error]
    Action: steering angle delta (rad), continuous
    Observation: [vy, r, y, psi_error, curvature_ref]

    Notes:
    - This environment uses small-angle linearization of the bicycle model.
    - It supports stepping with a fixed forward speed vx.
    - Reward is a simple quadratic penalty (can be customized for RL training).
    """
    metadata = {"render_modes": [], "render_fps": 60}

    def __init__(self,
                 dt=0.01,
                 vx=15.0,
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
        self.wheelbase = float(wheelbase)
        # vehicle params
        self.m = m
        self.Iz = Iz
        self.lf = lf
        self.lr = lr
        self.Cf = Cf
        self.Cr = Cr

        # action/observation spaces
        self.steering_limit = steering_limit
        self.action_space = spaces.Box(low=np.array([-steering_limit]), high=np.array([steering_limit]), dtype=np.float32)
        # obs: vy, r, y, psi_error, curvature_ref
        obs_high = np.array([5.0, 10.0, 5.0, 3.14, 1.0], dtype=np.float32)
        self.observation_space = spaces.Box(low=-obs_high, high=obs_high, dtype=np.float32)

        # runtime
        self.rate_limiter = None
        self.reset()

    def get_continuous_matrices(self):
        """
        Build continuous-time linear A,B matrices for states [vy, r, y, psi_error].
        Form used (small-angle linearization, common in literature).
        """
        m = self.m; Iz = self.Iz; vx = self.vx
        lf = self.lf; lr = self.lr
        Cf = self.Cf; Cr = self.Cr

        A = np.zeros((4, 4), dtype=float)
        B = np.zeros((4, 1), dtype=float)

        A[0, 0] = -2 * (Cf + Cr) / (m * vx)
        A[0, 1] = -vx - 2 * (Cf * lf - Cr * lr) / (m * vx)
        A[1, 0] = -2 * (Cf * lf - Cr * lr) / (Iz * vx)
        A[1, 1] = -2 * (Cf * lf ** 2 + Cr * lr ** 2) / (Iz * vx)
        # lateral kinematics
        A[2, 0] = 1.0
        A[2, 3] = vx
        A[3, 1] = 1.0

        B[0, 0] = 2 * Cf / m
        B[1, 0] = 2 * Cf * lf / Iz
        # the kinematic states not directly actuated

        return A, B

    def dyn(self, x, u, curvature_ref=0.0):
        """
        Continuous-time dynamics for dx/dt = A x + B u + feedforward (if curvature_ref provided).
        x: [vy, r, y, psi_error]
        u: scalar steering (rad)
        Returns dx/dt (4,)
        """
        A, B = self.get_continuous_matrices()
        x = np.asarray(x).reshape(-1)
        u = float(u)
        # feedforward enters through a desired psi_dot relation; here we just input it as external steering offset
        # For RL we keep dynamics linear: xdot = A x + B u
        xdot = A.dot(x) + B.flatten() * u
        # kinematic coupling: y_dot and psi_dot already in A
        return xdot

    def step(self, action):
        action = np.asarray(action).astype(float).ravel()[0]
        # initialize rate limiter lazily
        if self.rate_limiter is None:
            from controller_helpers import RateLimiter
            self.rate_limiter = RateLimiter(rate_limit=1.0)  # default rate limit, can be set externally

        # apply rate limit and saturation
        u_cmd = self.rate_limiter(action, self.dt)
        u_cmd = saturate(u_cmd, -self.steering_limit, self.steering_limit)

        # integrate dynamics with RK4
        x_next = rk4_step(lambda xx, uu: self.dyn(xx, uu), self.state, u_cmd, self.dt)
        self.state = x_next

        # observation: include current path curvature reference at the current s (if using a path server, set curvature)
        curvature_ref = getattr(self, "curvature_ref", 0.0)
        obs = np.array([self.state[0], self.state[1], self.state[2], self.state[3], curvature_ref], dtype=np.float32)

        # simple reward: quadratic penalty on lateral error and heading error + small control penalty
        reward = - (self.state[2] ** 2 + 0.1 * self.state[3] ** 2 + 0.01 * (u_cmd ** 2))

        # termination: none by default (RL training will provide curriculum)
        done = False
        info = {"steering": float(u_cmd)}

        return obs, float(reward), done, False, info

    def reset(self, *, seed=None, options=None):
        # initialize small random perturbations around zero
        self.state = np.zeros(4, dtype=float)
        self.curvature_ref = 0.0
        self.rate_limiter = None
        obs = np.array([0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        return obs, {}

    # Small helper API to set path-related references externally (for simulation harness)
    def set_curvature_reference(self, curvature):
        self.curvature_ref = float(curvature)
