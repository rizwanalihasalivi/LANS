"""
path_tracking_env.py - Path Tracking Environment for LANS Controller
FIXED: Double lane change now works correctly
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import time
from models.bicycle_model import bicycle_model
from scenarios.double_lane_change import double_lane_change

class PathTrackingEnv(gym.Env):
    def __init__(self, mode="train"):
        super(PathTrackingEnv, self).__init__()
        self.mode = mode
        
        # Observation space: [o_t; c_t] = 11 dimensions
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(11,), dtype=np.float32)
        self.action_space = spaces.Box(low=-0.5, high=0.5, shape=(1,), dtype=np.float32)

        # Simulation parameters
        self.dt = 0.01  # 100 Hz
        self.vx = 25.0  # 90 km/h (default)
        
        # Vehicle parameters
        self.params = {
            "m": 1650.0,
            "Iz": 4224.0,
            "lf": 1.2,
            "lr": 1.4,
            "Cf": 80000.0,
            "Cr": 80000.0
        }
        
        # LQR gain
        self.K_lqr = np.array([0.52, 0.12, 0.31, 0.04])
        
        # Latency tracking
        self.latency_history = []
        self.latency_window = 10
        self.last_latency = 0.0
        self.pred_latency = 0.0
        
        # Position tracking
        self.x_position = 0.0
        self.y_actual = 0.0
        
        # State: [e_y, e_y_dot, e_ψ, e_ψ_dot]
        self.state = np.zeros(4, dtype=np.float32)
        
        # Step tracking
        self.t_step = 0
        self.prev_steering = 0.0
        
        # Reference path storage
        self.y_ref = None

    def _generate_reference_path(self):
        """Generate the reference path based on mode"""
        # Time array (10 seconds at 100 Hz)
        t = np.arange(0, 10.01, self.dt)
        
        # Convert time to distance (meters)
        s = self.vx * t
        
        if self.mode == "train":
            # Random path for training
            path_type = np.random.choice(["DLC", "Snake", "Sine"])
            if path_type == "DLC":
                self.y_ref = double_lane_change(s, lane_width=3.5)
            elif path_type == "Snake":
                self.y_ref = 2.5 * np.sin(2 * np.pi * 0.4 * t)
            else:  # Sine
                self.y_ref = 3.0 * np.sin(2 * np.pi * 0.1 * t)
        else:
            # Evaluation: Always use Double Lane Change
            self.y_ref = double_lane_change(s, lane_width=3.5)
        
        return self.y_ref

    def _get_reference_y(self, x_pos):
        """Get reference y at current x position"""
        if self.y_ref is None:
            return 0.0
        
        # Calculate index based on distance traveled
        distance = x_pos
        idx = int(distance / (self.vx * self.dt))
        idx = min(idx, len(self.y_ref) - 1)
        idx = max(idx, 0)
        
        return self.y_ref[idx]

    def _get_reference_heading(self, x_pos):
        """Calculate reference heading from path derivative"""
        if self.y_ref is None or len(self.y_ref) < 2:
            return 0.0
        
        distance = x_pos
        idx = int(distance / (self.vx * self.dt))
        idx = min(idx, len(self.y_ref) - 2)
        idx = max(idx, 0)
        
        if idx > 0 and idx < len(self.y_ref) - 1:
            dy = self.y_ref[idx + 1] - self.y_ref[idx - 1]
            dx = 2 * self.vx * self.dt
            return np.arctan2(dy, dx) if dx > 0 else 0.0
        return 0.0

    def _get_future_error(self, steps):
        """Get future lateral error at 'steps' ahead"""
        future_x = self.x_position + steps * self.vx * self.dt
        future_idx = int(future_x / (self.vx * self.dt))
        future_idx = min(future_idx, len(self.y_ref) - 1) if self.y_ref is not None else 0
        future_idx = max(future_idx, 0)
        
        y_ref_future = self.y_ref[future_idx] if self.y_ref is not None else 0
        current_y = self._get_reference_y(self.x_position) - self.state[0]
        
        return y_ref_future - current_y

    def _get_observation(self):
        """Build 11-dim observation"""
        e_y = self.state[0]
        e_y_dot = self.state[1]
        e_ψ = self.state[2]
        e_ψ_dot = self.state[3]
        
        # Preview (4 steps ahead)
        preview = [
            self._get_future_error(1),
            self._get_future_error(2),
            self._get_future_error(3),
            self._get_future_error(4)
        ]
        
        o_t = np.array([e_y, e_y_dot, e_ψ, e_ψ_dot, self.vx] + preview, dtype=np.float32)
        
        # Context vector
        τ_current = self.last_latency
        τ_pred = np.mean(self.latency_history) if self.latency_history else 0.0
        self.pred_latency = τ_pred
        c_t = np.array([τ_current, τ_pred], dtype=np.float32)
        
        return np.concatenate([o_t, c_t])

    def _compute_adaptive_gain(self, tau):
        """β(τ) adaptive gain"""
        tau_th = 5.0
        tau_scale = 20.0
        if tau < tau_th:
            return 1.0
        return np.exp(-(tau - tau_th) / tau_scale)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        
        # Reset all state variables
        self.state = np.zeros(4, dtype=np.float32)
        self.x_position = 0.0
        self.y_actual = 0.0
        self.prev_steering = 0.0
        self.t_step = 0
        self.latency_history = []
        self.last_latency = 0.0
        self.pred_latency = 0.0
        
        # Update vehicle dynamics
        self.A, self.B = bicycle_model(self.vx, self.params)
        self.B = self.B.flatten()
        self.A_d = np.eye(4) + self.A * self.dt
        self.B_d = self.B * self.dt
        
        # Generate reference path
        self._generate_reference_path()
        
        return self._get_observation(), {}

    def step(self, action):
        t_start = time.perf_counter()
        
        # Get references
        y_ref = self._get_reference_y(self.x_position)
        ψ_ref = self._get_reference_heading(self.x_position)
        
        # PPO residual
        δ_RL = np.clip(action[0], -0.5, 0.5)
        
        # LQR baseline
        δ_LQR = -np.dot(self.K_lqr, self.state)
        δ_LQR = np.clip(δ_LQR, -0.5, 0.5)
        
        # Adaptive gain
        β = self._compute_adaptive_gain(self.last_latency)
        
        # Total steering
        δ_total = δ_LQR + β * δ_RL
        δ_total = np.clip(δ_total, -0.5, 0.5)
        
        # Vehicle dynamics update
        self.state = self.A_d @ self.state + self.B_d * δ_total
        self.t_step += 1
        self.x_position += self.vx * self.dt
        
        e_y = self.state[0]
        e_ψ = self.state[2]
        self.y_actual = y_ref - e_y
        
        # Measure latency
        t_end = time.perf_counter()
        τ = (t_end - t_start) * 1000
        
        self.latency_history.append(τ)
        if len(self.latency_history) > self.latency_window:
            self.latency_history.pop(0)
        self.last_latency = τ
        
        # Calculate reward
        R_tracking = -10.0 * (e_y ** 2) - 5.0 * (e_ψ ** 2)
        R_control = -0.1 * (δ_RL ** 2) - 0.5 * ((δ_RL - self.prev_steering) ** 2)
        R_latency = -0.01 * τ - 0.1 * max(0, τ - 5.0) ** 2
        
        reward = 1.0 * R_tracking + 0.1 * R_control + 0.05 * R_latency
        
        if abs(e_y) < 0.05:
            reward += 20.0
        reward += 1.0
        
        self.prev_steering = δ_RL
        
        # Check termination
        terminated = bool(abs(e_y) > 2.5 or self.t_step >= len(self.y_ref) - 1 if self.y_ref is not None else False)
        
        info = {
            "error": e_y,
            "y_phys": self.y_actual,
            "y_ref": y_ref,
            "x_phys": self.x_position,
            "steering": δ_total,
            "latency": τ,
            "beta": β,
            "δ_LQR": δ_LQR,
            "δ_RL": δ_RL,
            "heading_error": e_ψ,
            "pred_latency": self.pred_latency
        }
        
        return self._get_observation(), reward, terminated, False, info