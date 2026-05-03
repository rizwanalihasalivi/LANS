import numpy as np
import gymnasium as gym
from gymnasium import spaces
from integrators import rk4_step
from controller_helpers import saturate

class LQREnv(gym.Env):
    """
    Gymnasium environment wrapping a linearized 2-DOF bicycle model for lateral/path tracking.
    
    State: [vy, r, y, psi_error]
    Action: steering angle delta (rad), continuous
    Observation: [vy, r, y, psi_error, curvature_ref]
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
                 steering_limit=0.4):
        super().__init__()
        self.dt = dt
        self.vx = float(vx)
        self.wheelbase = float(wheelbase)
        
        # Vehicle params
        self.m = m
        self.Iz = Iz
        self.lf = lf
        self.lr = lr
        self.Cf = Cf
        self.Cr = Cr

        # Action space: Steering angle
        self.steering_limit = steering_limit
        self.action_space = spaces.Box(
            low=np.array([-steering_limit], dtype=np.float32), 
            high=np.array([steering_limit], dtype=np.float32), 
            dtype=np.float32
        )
        
        # Observation space: [vy, r, y, psi_error, curvature_ref]
        obs_high = np.array([5.0, 10.0, 5.0, 3.14, 1.0], dtype=np.float32)
        self.observation_space = spaces.Box(low=-obs_high, high=obs_high, dtype=np.float32)

        # Runtime variables
        self.rate_limiter = None
        self.state = np.zeros(4, dtype=np.float32)
        self.curvature_ref = 0.0

    def get_continuous_matrices(self):
        """Build continuous-time linear A,B matrices for states [vy, r, y, psi_error]."""
        m = self.m; Iz = self.Iz; vx = self.vx
        lf = self.lf; lr = self.lr
        Cf = self.Cf; Cr = self.Cr

        A = np.zeros((4, 4), dtype=float)
        B = np.zeros((4, 1), dtype=float)

        A[0, 0] = -2 * (Cf + Cr) / (m * vx)
        A[0, 1] = -vx - 2 * (Cf * lf - Cr * lr) / (m * vx)
        A[1, 0] = -2 * (Cf * lf - Cr * lr) / (Iz * vx)
        A[1, 1] = -2 * (Cf * lf ** 2 + Cr * lr ** 2) / (Iz * vx)
        # Lateral kinematics
        A[2, 0] = 1.0
        A[2, 3] = vx
        A[3, 1] = 1.0

        B[0, 0] = 2 * Cf / m
        B[1, 0] = 2 * Cf * lf / Iz

        return A, B

    def dyn(self, x, u):
        """Continuous-time dynamics: dx/dt = Ax + Bu"""
        A, B = self.get_continuous_matrices()
        x = np.asarray(x).reshape(-1)
        u = float(u)
        xdot = A.dot(x) + B.flatten() * u
        return xdot

    def step(self, action):
        action = np.asarray(action).astype(float).ravel()[0]
        
        # Initialize rate limiter if not already done
        if self.rate_limiter is None:
            from controller_helpers import RateLimiter
            self.rate_limiter = RateLimiter(rate_limit=1.0)

        # Apply rate limit and saturation
        u_cmd = self.rate_limiter(action, self.dt)
        u_cmd = saturate(u_cmd, -self.steering_limit, self.steering_limit)

        # Integrate dynamics using RK4
        self.state = rk4_step(lambda xx, uu: self.dyn(xx, uu), self.state, u_cmd, self.dt)

        # Build observation
        obs = np.array([self.state[0], self.state[1], self.state[2], self.state[3], self.curvature_ref], dtype=np.float32)

        # Reward: Quadratic penalty on lateral error (y) and heading error (psi)
        reward = - (self.state[2] ** 2 + 0.1 * self.state[3] ** 2 + 0.01 * (u_cmd ** 2))

        return obs, float(reward), False, False, {"steering": float(u_cmd)}

    def reset(self, *, seed=None, options=None):
        """Reset environment to initial conditions."""
        super().reset(seed=seed)
        
        # Reset state to zeros [vy, r, y, psi_error]
        self.state = np.zeros(4, dtype=np.float32)
        self.rate_limiter = None
        self.curvature_ref = 0.0

        obs = np.array([0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        return obs, {}

    def set_curvature_reference(self, curvature):
        """Set path curvature reference externally."""
        self.curvature_ref = float(curvature)