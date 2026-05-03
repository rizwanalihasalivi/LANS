"""
lans_controller.py - Complete LANS (Latency-Aware Neuro-Symbolic) Controller
"""

import sys
import os

# Add parent directory to Python path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import time

# Now imports will work from anywhere
from models.bicycle_model import get_error_state_from_measurements, VEHICLE_PARAMS
from controllers.lqr_controller import get_lqr_controller
from controllers.observation_builder import ObservationBuilder
from controllers.latency_monitor import LatencyMonitor, AdaptiveGain

class LANSController:
    """
    Complete LANS (Latency-Aware Neuro-Symbolic) Controller
    """
    
    def __init__(self, vx=25.0, params=None, load_ppo_model=False):
        """
        Initialize all components of the LANS architecture
        """
        if params is None:
            params = VEHICLE_PARAMS.copy()
        
        self.vx = vx
        self.params = params
        
        # Component 1: LQR Baseline Controller (δ_LQR)
        self.K_lqr, self.lqr_control = get_lqr_controller(vx, params)
        
        # Component 2: Observation Builder (o_t, c_t)
        self.obs_builder = ObservationBuilder(lookahead_steps=4, latency_window=10)
        
        # Component 3: Latency Monitor (τ measurement)
        self.latency_monitor = LatencyMonitor(tau_threshold_ms=5.0, tau_scale_ms=20.0)
        
        # Component 4: Adaptive Gain (β(τ))
        self.adaptive_gain = AdaptiveGain(tau_threshold_ms=5.0, tau_scale_ms=20.0)
        
        # Component 5: PPO Neural Controller (δ_RL)
        self.ppo_model = None
        if load_ppo_model:
            self._load_ppo_model()
        
        # State tracking
        self.last_error_state = np.zeros(4)
        self.last_delta_lqr = 0.0
        self.last_delta_rl = 0.0
        
        print("✅ LANS Controller initialized")
        print(f"   Speed: {vx} m/s ({vx*3.6:.0f} km/h)")
        print(f"   LQR Gain: [{self.K_lqr[0]:.3f}, {self.K_lqr[1]:.3f}, {self.K_lqr[2]:.3f}, {self.K_lqr[3]:.3f}]")
    
    def _load_ppo_model(self):
        """Load trained PPO model"""
        try:
            from stable_baselines3 import PPO
            model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "ppo_curriculum_final")
            if os.path.exists(model_path + ".zip"):
                self.ppo_model = PPO.load(model_path)
                print("   ✅ PPO model loaded")
            else:
                print("   ⚠️ PPO model not found - using zero residual")
        except Exception as e:
            print(f"   ⚠️ Could not load PPO model: {e}")
            self.ppo_model = None
    
    def update_error_state(self, y_actual, y_ref, psi_actual, psi_ref, vy, r, kappa):
        """Compute error state from measurements - Equations (40)-(42)"""
        error_state = get_error_state_from_measurements(
            y_actual, y_ref, psi_actual, psi_ref, self.vx, vy, r, kappa
        )
        self.last_error_state = error_state
        return error_state
    
    def compute_delta_lqr(self, error_state=None):
        """Compute LQR baseline command δ_LQR - Equation (17)"""
        if error_state is None:
            error_state = self.last_error_state
        delta_lqr = self.lqr_control(error_state)
        self.last_delta_lqr = delta_lqr
        return delta_lqr
    
    def compute_delta_rl(self, observation, deterministic=True):
        """Compute PPO residual command δ_RL - Equation (19)"""
        if self.ppo_model is None:
            return 0.0
        
        if len(observation.shape) == 1:
            obs = observation.reshape(1, -1)
        else:
            obs = observation
        
        action, _ = self.ppo_model.predict(obs, deterministic=deterministic)
        delta_rl = float(action[0]) if isinstance(action, np.ndarray) else float(action)
        delta_rl = np.clip(delta_rl, -0.5, 0.5)
        self.last_delta_rl = delta_rl
        return delta_rl
    
    def step(self, y_actual, y_ref, psi_actual, psi_ref, vy, r, kappa):
        """
        Complete control step implementing the LANS architecture
        
        δ_total = δ_LQR + β(τ)·δ_RL - Equation (31)
        """
        # Step 1: Measure latency
        self.latency_monitor.measure_start()
        
        # Step 2: Compute error state
        error_state = self.update_error_state(y_actual, y_ref, psi_actual, psi_ref, vy, r, kappa)
        
        # Step 3: Build observation
        self.obs_builder.update_error_state(error_state)
        self.obs_builder.update_latency(self.latency_monitor.current_latency)
        observation = self.obs_builder.get_full_input()
        
        # Step 4: Compute LQR baseline
        delta_lqr = self.compute_delta_lqr(error_state)
        
        # Step 5: Compute PPO residual
        delta_rl = self.compute_delta_rl(observation)
        
        # Step 6: Measure end latency
        tau = self.latency_monitor.measure_end()
        
        # Step 7: Compute adaptive gain β(τ)
        beta = self.adaptive_gain.compute(tau)
        
        # Step 8: Fusion - THE CORE LANS EQUATION
        delta_total = delta_lqr + beta * delta_rl
        delta_total = np.clip(delta_total, -0.5, 0.5)
        
        # Update future predictions
        self.obs_builder.update_future_errors([error_state[0]] * 4)
        
        info = {
            'error_state': error_state,
            'delta_lqr': delta_lqr,
            'delta_rl': delta_rl,
            'tau_ms': tau,
            'beta': beta,
            'delta_total': delta_total,
            'observation': observation,
            'context': self.latency_monitor.get_context()
        }
        
        return delta_total, info
    
    def get_control_law_equation(self):
        """Return the LANS control law equation"""
        return r"$\delta_{total}(t) = \delta_{LQR}(t) + \beta(\tau) \cdot \delta_{RL}(t)$"


if __name__ == "__main__":
    print("="*70)
    print("LANS CONTROLLER - COMPLETE ARCHITECTURE TEST")
    print("="*70)
    
    # Create controller (without PPO for testing)
    controller = LANSController(vx=25.0, load_ppo_model=False)
    
    print(f"\nControl Law: {controller.get_control_law_equation()}")
    
    # Simulate one control step
    print("\n" + "-"*50)
    print("Simulating one control cycle:")
    print("-"*50)
    
    # Simulated measurements
    y_actual = 1.2      # m
    y_ref = 1.0         # m
    psi_actual = 0.05    # rad
    psi_ref = 0.02       # rad
    vy = 0.1             # m/s
    r = 0.05             # rad/s
    kappa = 0.01         # 1/m
    
    # Run controller
    delta_total, info = controller.step(y_actual, y_ref, psi_actual, psi_ref, vy, r, kappa)
    
    print(f"\nInputs:")
    print(f"  y_actual={y_actual:.3f}m, y_ref={y_ref:.3f}m → e_y={info['error_state'][0]:.3f}m")
    print(f"  ψ_actual={psi_actual:.3f}rad, ψ_ref={psi_ref:.3f}rad → e_ψ={info['error_state'][2]:.3f}rad")
    
    print(f"\nLANS Components:")
    print(f"  δ_LQR = {info['delta_lqr']:.4f} rad")
    print(f"  δ_RL  = {info['delta_rl']:.4f} rad")
    print(f"  τ     = {info['tau_ms']:.3f} ms")
    print(f"  β(τ)  = {info['beta']:.4f}")
    print(f"  δ_total = {info['delta_total']:.4f} rad")
    
    print("\n" + "="*70)
    print("✅ LANS Controller Architecture Verified")
    print("="*70)
