"""
observation_builder.py - Implements the Observation Builder from your diagram
Equations (7)-(8) from your paper
"""

import numpy as np
from collections import deque

class ObservationBuilder:
    """
    Builds observation vector o_t and context vector c_t
    o_t = [x(t), vx, e_y(t+1), e_y(t+2), e_y(t+3), e_y(t+4)] - Equation (7)
    c_t = [τ(t), τ_pred(t)] - Equation (8)
    """
    
    def __init__(self, lookahead_steps=4, latency_window=10):
        """
        Args:
            lookahead_steps: number of future lateral error steps (default 4)
            latency_window: window size for latency moving average (default 10)
        """
        self.lookahead_steps = lookahead_steps
        self.latency_window = latency_window
        
        # Storage for future predictions
        self.future_errors = deque(maxlen=lookahead_steps + 1)
        
        # Storage for latency history
        self.latency_history = deque(maxlen=latency_window)
        
        # Current values
        self.current_error_state = np.zeros(4)
        self.current_vx = 25.0
        self.current_latency = 0.0
        
    def update_error_state(self, error_state):
        """Update current error state x(t)"""
        self.current_error_state = error_state.copy()
        
    def update_future_errors(self, future_errors):
        """
        Update future lateral errors
        future_errors: list of [e_y(t+1), e_y(t+2), e_y(t+3), e_y(t+4)]
        """
        self.future_errors.clear()
        for err in future_errors[:self.lookahead_steps]:
            self.future_errors.append(err)
            
    def update_latency(self, tau_ms):
        """Update measured latency τ(t)"""
        self.current_latency = tau_ms
        self.latency_history.append(tau_ms)
        
    def get_observation(self):
        """
        Build observation vector o_t - Equation (7)
        
        Returns:
            o_t: 9-dimensional vector
                [e_y, ė_y, e_ψ, ė_ψ, vx, e_y(t+1), e_y(t+2), e_y(t+3), e_y(t+4)]
        """
        obs = np.zeros(9)
        
        # Current error state (4 dimensions)
        obs[0:4] = self.current_error_state
        
        # Longitudinal velocity (1 dimension)
        obs[4] = self.current_vx
        
        # Future lateral errors (4 dimensions)
        for i in range(self.lookahead_steps):
            if i < len(self.future_errors):
                obs[5 + i] = self.future_errors[i]
            else:
                obs[5 + i] = 0.0
                
        return obs
    
    def get_context(self):
        """
        Build context vector c_t - Equation (8)
        
        Returns:
            c_t: 2-dimensional vector
                [τ(t), τ_pred(t)]
        """
        # Predicted latency via moving average
        if len(self.latency_history) > 0:
            tau_pred = np.mean(self.latency_history)
        else:
            tau_pred = self.current_latency
            
        return np.array([self.current_latency, tau_pred])
    
    def get_full_input(self):
        """
        Get complete input for PPO: [o_t, c_t] concatenated
        """
        obs = self.get_observation()
        ctx = self.get_context()
        return np.concatenate([obs, ctx])  # 9 + 2 = 11 dimensions


if __name__ == "__main__":
    print("="*60)
    print("Observation Builder Verification")
    print("="*60)
    
    builder = ObservationBuilder(lookahead_steps=4, latency_window=10)
    
    # Simulate updates
    builder.update_error_state(np.array([0.5, 0.1, 0.05, 0.02]))
    builder.update_future_errors([0.48, 0.45, 0.42, 0.38])
    builder.update_latency(2.5)
    
    obs = builder.get_observation()
    ctx = builder.get_context()
    full = builder.get_full_input()
    
    print(f"\nObservation o_t (9 dims):")
    print(f"  [e_y, ė_y, e_ψ, ė_ψ, vx, e_y(t+1), e_y(t+2), e_y(t+3), e_y(t+4)]")
    print(f"  {obs}")
    
    print(f"\nContext c_t (2 dims):")
    print(f"  [τ(t), τ_pred(t)] = {ctx}")
    
    print(f"\nFull PPO input (11 dims): {full}")