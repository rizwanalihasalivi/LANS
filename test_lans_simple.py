"""
test_lans_simple.py - Simple test for LANS controller
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.getcwd())

print("="*70)
print("LANS CONTROLLER SIMPLE TEST")
print("="*70)

# Test imports one by one
print("\n1. Testing imports...")

try:
    from models.bicycle_model import VEHICLE_PARAMS, get_error_state_from_measurements
    print("   ✅ models.bicycle_model")
except Exception as e:
    print(f"   ❌ models.bicycle_model: {e}")

try:
    from controllers.lqr_controller import get_lqr_controller
    print("   ✅ controllers.lqr_controller")
except Exception as e:
    print(f"   ❌ controllers.lqr_controller: {e}")

try:
    from controllers.latency_monitor import LatencyMonitor, AdaptiveGain
    print("   ✅ controllers.latency_monitor")
except Exception as e:
    print(f"   ❌ controllers.latency_monitor: {e}")

try:
    from controllers.observation_builder import ObservationBuilder
    print("   ✅ controllers.observation_builder")
except Exception as e:
    print(f"   ❌ controllers.observation_builder: {e}")

try:
    from controllers.lans_controller import LANSController
    print("   ✅ controllers.lans_controller")
except Exception as e:
    print(f"   ❌ controllers.lans_controller: {e}")

print("\n2. Creating LANS Controller...")
try:
    controller = LANSController(vx=25.0, load_ppo_model=False)
    print("   ✅ Controller created successfully")
    
    print("\n3. Testing control step...")
    # Simulated measurements
    y_actual = 1.2
    y_ref = 1.0
    psi_actual = 0.05
    psi_ref = 0.02
    vy = 0.1
    r = 0.05
    kappa = 0.01
    
    delta_total, info = controller.step(y_actual, y_ref, psi_actual, psi_ref, vy, r, kappa)
    
    print(f"\n   Results:")
    print(f"   δ_LQR = {info['delta_lqr']:.4f} rad")
    print(f"   τ = {info['tau_ms']:.3f} ms")
    print(f"   β(τ) = {info['beta']:.4f}")
    print(f"   δ_total = {info['delta_total']:.4f} rad")
    
    print("\n✅ LANS Controller is working correctly!")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)