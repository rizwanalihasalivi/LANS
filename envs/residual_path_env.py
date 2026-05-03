import gymnasium as gym
import numpy as np
import time
from envs.path_tracking_env import PathTrackingEnv

class ResidualPathEnv(PathTrackingEnv):
    def __init__(self):
        super().__init__()
        
        # ========== CORRECTED LQR GAIN (From Methodology) ==========
        # From your paper: K = [0.52, 0.12, 0.31, 0.04]
        self.K = np.array([0.52, 0.12, 0.31, 0.04])
        
        # ========== LATENCY PARAMETERS ==========
        self.tau_th = 5.0          # Latency threshold (ms)
        self.tau_scale = 20.0      # Decay rate (ms)
        self.latency_history = []   # For τ_pred
        self.latency_window = 10    # Moving average window
        self.last_tau = 0.0         # Last measured latency
        
        # ========== VEHICLE PARAMETERS ==========
        self.target_speed = 25.0    # 90 km/h (not 15 m/s)
        self.dt = 0.01
        self.car_x = 0.0
        self.max_steering = 0.5     # Maximum steering angle (rad)
        
    def _compute_adaptive_gain(self, tau):
        """β(τ) from Equation (34)"""
        if tau < self.tau_th:
            return 1.0
        else:
            return np.exp(-(tau - self.tau_th) / self.tau_scale)
    
    def _get_reference_heading(self, x):
        """Calculate reference heading ψ_ref from path"""
        if x < 25 or x >= 145:
            return 0.0
        elif 25 <= x < 65:
            # First lane change
            t = (x - 25) / 40
            # Derivative of cosine transition
            dy_dx = (3.5 * np.pi / 80) * np.sin(np.pi * t)
            return np.arctan2(dy_dx, 1.0)
        elif 65 <= x < 105:
            # Straight section (heading = 0)
            return 0.0
        elif 105 <= x < 145:
            # Second lane change
            t = (x - 105) / 40
            dy_dx = -(3.5 * np.pi / 80) * np.sin(np.pi * t)
            return np.arctan2(dy_dx, 1.0)
        return 0.0
    
    def step(self, rl_action):
        # ========== STEP 1: MEASURE START TIME ==========
        t_start = time.perf_counter()
        
        # ========== STEP 2: GET CURRENT STATE ==========
        # State is [e_y, e_y_dot, e_ψ, e_ψ_dot]
        current_state = self.state if hasattr(self, 'state') else np.zeros(4)
        
        # ========== STEP 3: LQR BASELINE ==========
        δ_LQR = -np.dot(self.K, current_state)
        δ_LQR = np.clip(δ_LQR, -self.max_steering, self.max_steering)
        
        # ========== STEP 4: ADAPTIVE GAIN (Key Innovation) ==========
        β = self._compute_adaptive_gain(self.last_tau)
        
        # ========== STEP 5: PPO RESIDUAL ==========
        # Scale RL action to steering range (0.5 rad max)
        residual_correction = rl_action[0] * 0.5
        residual_correction = np.clip(residual_correction, -0.5, 0.5)
        
        # ========== STEP 6: TOTAL STEERING COMMAND ==========
        δ_total = δ_LQR + β * residual_correction
        δ_total = np.clip(δ_total, -self.max_steering, self.max_steering)
        
        # ========== STEP 7: MEASURE END TIME & LATENCY ==========
        t_end = time.perf_counter()
        τ = (t_end - t_start) * 1000  # milliseconds
        
        # Update latency history for prediction
        self.latency_history.append(τ)
        if len(self.latency_history) > self.latency_window:
            self.latency_history.pop(0)
        self.last_tau = τ
        τ_pred = np.mean(self.latency_history) if self.latency_history else 0.0
        
        # ========== STEP 8: PHYSICS STEP ==========
        obs, reward, terminated, truncated, info = super().step(
            np.array([δ_total], dtype=np.float32)
        )
        
        # ========== STEP 9: UPDATE POSITION ==========
        self.car_x += self.target_speed * self.dt
        
        # ========== STEP 10: CALCULATE ACTUAL POSITION ==========
        # Get reference at current x
        ref_y = self.get_ref_y(self.car_x)
        ψ_ref = self._get_reference_heading(self.car_x)
        
        # Error from state (after physics update)
        e_y = self.state[0] if hasattr(self, 'state') else 0.0
        e_ψ = self.state[2] if hasattr(self, 'state') else 0.0
        
        # Actual position = reference - error
        actual_y = ref_y - e_y
        actual_ψ = ψ_ref + e_ψ
        
        # ========== STEP 11: CHECK TERMINATION ==========
        if self.car_x >= 195:
            terminated = True
        
        # ========== STEP 12: INFO DICTIONARY ==========
        info.update({
            'x_phys': self.car_x,
            'y_phys': actual_y,
            'ref_y': ref_y,
            'lqr_steer': δ_LQR,
            'rl_steer': residual_correction,
            'total_steer': δ_total,
            'beta': β,
            'latency': τ,
            'latency_pred': τ_pred,
            'error': e_y,
            'heading_error': e_ψ
        })
        
        return obs, reward, terminated, truncated, info
    
    def get_ref_y(self, x):
        """
        ISO 3888-2 Double Lane Change Profile
        Smooth cosine transitions for continuous acceleration
        """
        lane_width = 3.5  # meters
        
        # First lane change (0 to +3.5m)
        if x < 25:
            return 0.0
        elif 25 <= x < 65:
            t = (x - 25) / 40  # 40m transition
            return (lane_width / 2) * (1 - np.cos(np.pi * t))
        
        # Stay in left lane
        elif 65 <= x < 105:
            return lane_width
        
        # Return to original lane (+3.5m to 0)
        elif 105 <= x < 145:
            t = (x - 105) / 40  # 40m transition
            return lane_width - (lane_width / 2) * (1 - np.cos(np.pi * t))
        
        # Back to original lane
        else:
            return 0.0
    
    def reset(self, seed=None, options=None):
        """Reset environment with latency history cleared"""
        self.car_x = 0.0
        self.latency_history = []
        self.last_tau = 0.0
        return super().reset(seed=seed, options=options)