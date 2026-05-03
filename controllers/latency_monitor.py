"""
latency_monitor.py - Implements Latency Monitor and Adaptive Gain β(τ)
Equations (24)-(26) from your paper
"""

import time
import numpy as np
from collections import deque

class LatencyMonitor:
    """
    Measures inference latency and computes adaptive gain β(τ)
    """
    
    def __init__(self, tau_threshold_ms=5.0, tau_scale_ms=20.0, window_size=10):
        """
        Args:
            tau_threshold_ms: threshold for full neural contribution (default 5ms)
            tau_scale_ms: scaling factor for exponential decay (default 20ms)
            window_size: moving average window for prediction (default 10)
        """
        self.tau_threshold = tau_threshold_ms
        self.tau_scale = tau_scale_ms
        self.window_size = window_size
        
        self.latency_history = deque(maxlen=window_size)
        self.current_latency = 0.0
        
    def measure_start(self):
        """Call at beginning of inference"""
        self.start_time = time.perf_counter()
        
    def measure_end(self):
        """Call at end of inference, returns latency in ms"""
        end_time = time.perf_counter()
        tau_ms = (end_time - self.start_time) * 1000
        self.current_latency = tau_ms
        self.latency_history.append(tau_ms)
        return tau_ms
    
    def get_adaptive_gain(self, tau_ms=None):
        """
        Compute adaptive gain β(τ) - Equation (26)
        
        Args:
            tau_ms: latency in ms (uses current if None)
        
        Returns:
            β(τ) in [0, 1]
        """
        if tau_ms is None:
            tau_ms = self.current_latency
            
        if tau_ms < self.tau_threshold:
            return 1.0
        else:
            return np.exp(-(tau_ms - self.tau_threshold) / self.tau_scale)
    
    def get_predicted_latency(self):
        """
        Compute predicted latency via moving average - Equation (25)
        
        Returns:
            τ_pred(t) in ms
        """
        if len(self.latency_history) == 0:
            return self.current_latency
        return np.mean(self.latency_history)
    
    def get_context(self):
        """
        Get context vector c_t = [τ(t), τ_pred(t)] - Equation (8)
        """
        return np.array([self.current_latency, self.get_predicted_latency()])


class AdaptiveGain:
    """
    Implements the adaptive gain β(τ) - Equation (26)
    """
    
    def __init__(self, tau_threshold_ms=5.0, tau_scale_ms=20.0):
        self.tau_threshold = tau_threshold_ms
        self.tau_scale = tau_scale_ms
        
    def compute(self, tau_ms):
        """Compute β(τ) for given latency"""
        if tau_ms < self.tau_threshold:
            return 1.0
        else:
            return np.exp(-(tau_ms - self.tau_threshold) / self.tau_scale)
    
    def __call__(self, tau_ms):
        return self.compute(tau_ms)


if __name__ == "__main__":
    print("="*60)
    print("Latency Monitor & Adaptive Gain Verification")
    print("="*60)
    
    monitor = LatencyMonitor()
    adaptive = AdaptiveGain()
    
    print("\nAdaptive Gain β(τ) - Equation (26):")
    print(f"  β(τ) = 1                    for τ < 5ms")
    print(f"  β(τ) = exp(-(τ-5)/20)       for τ ≥ 5ms")
    
    print("\nTest values:")
    for tau in [0, 2, 5, 10, 20, 50, 100, 130]:
        beta = adaptive.compute(tau)
        print(f"  τ = {tau:3d}ms → β = {beta:.4f}")
    
    # Simulate measurement
    print("\nSimulating measurement cycle:")
    monitor.measure_start()
    time.sleep(0.001)  # Simulate 1ms work
    tau = monitor.measure_end()
    beta = monitor.get_adaptive_gain()
    
    print(f"  Measured latency: {tau:.3f}ms")
    print(f"  Adaptive gain β: {beta:.4f}")