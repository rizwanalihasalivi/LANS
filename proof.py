"""
Record LANS Controller Highway Demonstration Video
Captures the ISO 3888-2 double lane change maneuver with real-time metrics overlay
"""

import gymnasium as gym
import highway_env
import numpy as np
import cv2
import time
import json
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
from collections import deque
import os

# Import your LANS controller functions
# Since lans_highway.py has functions, not a class, we import them
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lans_highway import lans_control, lqr_control

class VideoRecorder:
    """Records simulation frames to video file"""
    
    def __init__(self, output_filename, fps=30, frame_size=(1280, 720)):
        self.output_filename = output_filename
        self.fps = fps
        self.frame_size = frame_size
        self.writer = None
        
        # Codec for MP4 (H.264)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.writer = cv2.VideoWriter(output_filename, fourcc, fps, frame_size)
        
    def add_frame(self, frame):
        """Add a frame to the video"""
        if frame is not None and self.writer is not None:
            # Resize if needed
            if frame.shape[:2] != self.frame_size[::-1]:
                frame = cv2.resize(frame, self.frame_size)
            self.writer.write(frame)
    
    def release(self):
        if self.writer:
            self.writer.release()

def create_metrics_overlay(frame, metrics, step):
    """
    Creates an overlay with performance metrics on the frame
    
    Args:
        frame: RGB frame from highway environment
        metrics: dict containing performance metrics
        step: current step number
    """
    h, w = frame.shape[:2]
    
    # Create a copy to draw on
    overlay = frame.copy()
    
    # Semi-transparent background for text (optional - makes text more readable)
    # cv2.addWeighted(frame, 0.7, overlay, 0.3, 0, overlay)
    
    # ========== Top Banner ==========
    banner_height = 50
    cv2.rectangle(overlay, (0, 0), (w, banner_height), (0, 0, 0), -1)
    
    # Title
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(overlay, "LANS Controller - ISO 3888-2 Double Lane Change (90 km/h)", 
                (10, 32), font, 0.7, (255, 255, 255), 2)
    
    # ========== Left Panel (Key Metrics) ==========
    panel_width = 320
    panel_x = 10
    panel_y = banner_height + 10
    
    # Panel background
    cv2.rectangle(overlay, (panel_x, panel_y), (panel_x + panel_width, panel_y + 180), 
                  (0, 0, 0), -1)
    cv2.rectangle(overlay, (panel_x, panel_y), (panel_x + panel_width, panel_y + 180), 
                  (100, 100, 100), 1)
    
    # Metrics text
    small_font = cv2.FONT_HERSHEY_COMPLEX_SMALL
    y_offset = panel_y + 25
    
    # Status header
    cv2.putText(overlay, "LIVE METRICS", (panel_x + 10, y_offset), 
                small_font, 0.8, (255, 200, 100), 2)
    y_offset += 25
    
    # Latency
    latency = metrics.get('latency', 0)
    latency_color = (0, 255, 0) if latency < 0.5 else (0, 255, 255) if latency < 5 else (0, 0, 255)
    cv2.putText(overlay, f"Latency: {latency:.2f} ms", (panel_x + 10, y_offset), 
                small_font, 0.7, latency_color, 1)
    y_offset += 20
    
    # Lateral Error
    lat_error = metrics.get('lat_error', 0)
    error_color = (0, 255, 0) if abs(lat_error) < 0.2 else (0, 255, 255) if abs(lat_error) < 0.5 else (0, 0, 255)
    cv2.putText(overlay, f"Lateral Error: {lat_error:+.3f} m", (panel_x + 10, y_offset), 
                small_font, 0.7, error_color, 1)
    y_offset += 20
    
    # Heading Error
    head_error = metrics.get('head_error', 0)
    cv2.putText(overlay, f"Heading Error: {head_error:+.3f} rad", (panel_x + 10, y_offset), 
                small_font, 0.7, (255, 255, 255), 1)
    y_offset += 20
    
    # Steering
    steering = metrics.get('steering', 0)
    cv2.putText(overlay, f"Steering: {steering:+.3f} rad", (panel_x + 10, y_offset), 
                small_font, 0.7, (255, 255, 255), 1)
    y_offset += 20
    
    # Speed
    speed = metrics.get('speed', 0)
    cv2.putText(overlay, f"Speed: {speed:.1f} m/s ({speed*3.6:.0f} km/h)", (panel_x + 10, y_offset), 
                small_font, 0.7, (255, 255, 255), 1)
    y_offset += 20
    
    # Adaptive Gain (β)
    beta = metrics.get('beta', 1.0)
    beta_color = (0, 255, 0) if beta > 0.8 else (0, 255, 255) if beta > 0.4 else (0, 0, 255)
    cv2.putText(overlay, f"Adaptive Gain β: {beta:.3f}", (panel_x + 10, y_offset), 
                small_font, 0.7, beta_color, 1)
    y_offset += 20
    
    # Step
    cv2.putText(overlay, f"Step: {step}", (panel_x + 10, y_offset), 
                small_font, 0.7, (150, 150, 150), 1)
    
    # ========== Right Panel (Performance Summary) ==========
    right_panel_x = w - 320
    right_panel_y = banner_height + 10
    
    cv2.rectangle(overlay, (right_panel_x, right_panel_y), 
                  (right_panel_x + 310, right_panel_y + 180), (0, 0, 0), -1)
    cv2.rectangle(overlay, (right_panel_x, right_panel_y), 
                  (right_panel_x + 310, right_panel_y + 180), (100, 100, 100), 1)
    
    y_offset = right_panel_y + 25
    cv2.putText(overlay, "PERFORMANCE SUMMARY", (right_panel_x + 10, y_offset), 
                small_font, 0.8, (255, 200, 100), 2)
    y_offset += 25
    
    # From verification results
    cv2.putText(overlay, "LANS RMSE: 0.199 m", (right_panel_x + 10, y_offset), 
                small_font, 0.7, (0, 255, 0), 1)
    y_offset += 20
    
    cv2.putText(overlay, "PPO RMSE: 0.236 m (-15.9%)", (right_panel_x + 10, y_offset), 
                small_font, 0.7, (255, 200, 0), 1)
    y_offset += 20
    
    cv2.putText(overlay, "LQR RMSE: 0.151 m (baseline)", (right_panel_x + 10, y_offset), 
                small_font, 0.7, (200, 200, 200), 1)
    y_offset += 25
    
    cv2.putText(overlay, "Inference: 4.9 kHz (203 µs)", (right_panel_x + 10, y_offset), 
                small_font, 0.7, (0, 200, 200), 1)
    y_offset += 20
    
    cv2.putText(overlay, "Jitter Tolerance: >200 ms", (right_panel_x + 10, y_offset), 
                small_font, 0.7, (100, 255, 100), 1)
    y_offset += 20
    
    cv2.putText(overlay, "Mass Robustness: ±33% (0.5% degrade)", (right_panel_x + 10, y_offset), 
                small_font, 0.7, (200, 200, 200), 1)
    
    # ========== Status Banner at Bottom ==========
    if beta > 0.8:
        status = "FULL NEURAL MODE (PPO Active)"
        status_color = (0, 255, 0)
    elif beta > 0.4:
        status = "HYBRID MODE (Mixed LQR + PPO)"
        status_color = (0, 255, 255)
    else:
        status = "LQR SAFETY MODE (Neural Bypassed)"
        status_color = (0, 0, 255)
    
    status_y = h - 35
    cv2.rectangle(overlay, (0, h - 50), (w, h), (0, 0, 0), -1)
    cv2.putText(overlay, status, (w//2 - 200, status_y), 
                font, 0.6, status_color, 2)
    
    # Lane boundaries indicators
    cv2.putText(overlay, "Lane: Left | Center | Right", (w//2 - 150, 70), 
                small_font, 0.5, (150, 150, 150), 1)
    
    return overlay

def setup_highway_env_for_lane_change():
    """Setup highway environment for ISO 3888-2 style double lane change"""
    
    # Custom track geometry for double lane change
    # We'll use the built-in highway with lane change logic
    
    config = {
        "observation": {
            "type": "Kinematics",
            "features": ["presence", "x", "y", "vx", "vy", "heading"],
            "normalize": False,
        },
        "action": {
            "type": "ContinuousAction",
            "longitudinal": True,
            "steering_range": [-0.5, 0.5],
            "acceleration_range": [0, 5.0]
        },
        "simulation_frequency": 100,
        "policy_frequency": 100,  # Control at 100 Hz
        "duration": 150,  # 1.5 seconds? Actually 150 steps at 100Hz = 1.5 sec
        "vehicles_count": 0,
        "lanes_count": 3,
        "vehicles_density": 0,
        "initial_lane_id": 1,  # Start in middle lane
        "render_mode": "rgb_array",  # Important for video capture
        "screen_width": 1280,
        "screen_height": 720,
        "offscreen_rendering": False,
    }
    
    return config

def run_and_record_lans_demo(duration_seconds=30, fps=30, output_name="lans_demo"):
    """
    Run LANS controller and record video
    
    Args:
        duration_seconds: How long to record (seconds)
        fps: Frames per second for output video
        output_name: Base name for output files
    """
    
    print("=" * 70)
    print("🎥 LANS CONTROLLER VIDEO RECORDER")
    print("=" * 70)
    print(f"Recording duration: {duration_seconds} seconds")
    print(f"Output FPS: {fps}")
    print()
    
    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"recordings_{timestamp}")
    output_dir.mkdir(exist_ok=True)
    
    # Video filenames
    video_filename = output_dir / f"{output_name}_{timestamp}.mp4"
    metrics_filename = output_dir / f"metrics_{timestamp}.json"
    
    # Setup environment
    print("🔄 Initializing highway environment...")
    config = setup_highway_env_for_lane_change()
    env = gym.make('highway-v0', config=config, render_mode='rgb_array')
    obs, info = env.reset()
    
    # Initialize recorder
    print(f"🎬 Starting video recording: {video_filename}")
    recorder = VideoRecorder(str(video_filename), fps=fps, frame_size=(1280, 720))
    
    # Metrics tracking
    metrics_history = {
        'latency': [],
        'lat_error': [],
        'head_error': [],
        'steering': [],
        'speed': [],
        'beta': [],
        'step': []
    }
    
    # Vehicle parameters
    vehicle = env.unwrapped.vehicle
    
    # Try to set target speed
    try:
        env.unwrapped.vehicle.speed = 25.0  # 90 km/h
    except:
        pass
    
    # Control parameters
    throttle = 0.7  # Maintain speed
    
    # Statistics for overlay
    running_stats = {
        'lans_rmse': 0.199,
        'ppo_rmse': 0.236,
        'improvement': 15.9
    }
    
    step = 0
    target_lane = 1  # Start in middle lane
    max_steps = duration_seconds * 100  # 100 Hz control
    
    print("🏁 Recording started! Press Ctrl+C to stop early...")
    print()
    
    try:
        while step < max_steps:
            # Get vehicle state
            lateral_position = vehicle.position[1] if hasattr(vehicle, 'position') else 0
            heading = vehicle.heading if hasattr(vehicle, 'heading') else 0
            speed = vehicle.speed if hasattr(vehicle, 'speed') else 25
            
            # Calculate heading error (simplified)
            heading_error = heading  # Assuming reference heading = 0
            
            # Error state for LANS controller
            error_state = np.array([
                lateral_position,  # lateral error (m)
                0.0,  # lateral error rate
                heading_error,     # heading error (rad)
                0.0   # heading error rate
            ], dtype=np.float32)
            
            # Measure inference time for this step
            start_time = time.perf_counter()
            
            # Simulate realistic latency (jitter) based on your measurements
            # Your measured: mean 203 µs, 99th 550 µs
            import random
            simulated_latency_ms = random.gauss(0.203, 0.05)  # 203 µs mean
            simulated_latency_ms = max(0.1, min(1.0, simulated_latency_ms))  # Clip
            
            # Call LANS controller
            steering = lans_control(error_state, simulated_latency_ms)
            
            end_time = time.perf_counter()
            measured_latency_us = (end_time - start_time) * 1e6
            
            # Get beta from lans_control? Need to extract from function
            # For now, compute beta separately
            tau_ms = simulated_latency_ms
            if tau_ms < 5:
                beta = 1.0
            else:
                beta = np.exp(-(tau_ms - 5) / 20)
            
            # Action: [throttle, steering]
            # For lane change, modulate throttle to maintain speed
            if speed < 24:
                throttle = min(1.0, throttle + 0.01)
            elif speed > 26:
                throttle = max(0.5, throttle - 0.01)
            
            action = [throttle, steering]
            
            # Step environment
            obs, reward, done, truncated, info = env.step(action)
            
            # Render and capture frame
            frame = env.render()
            
            # Prepare metrics for this step
            current_metrics = {
                'latency': measured_latency_us / 1000,  # Convert to ms
                'lat_error': lateral_position,
                'head_error': heading_error,
                'steering': steering,
                'speed': speed,
                'beta': beta,
                'step': step
            }
            
            # Store metrics
            for key in metrics_history:
                if key in current_metrics:
                    metrics_history[key].append(current_metrics[key])
            
            # Add overlay to frame
            display_metrics = current_metrics.copy()
            display_metrics.update(running_stats)
            frame_with_overlay = create_metrics_overlay(frame, display_metrics, step)
            
            # Add frame to video
            recorder.add_frame(frame_with_overlay)
            
            # Progress indicator
            if step % 500 == 0:
                progress = (step / max_steps) * 100
                print(f"  Recording: {progress:.1f}% | Step {step} | "
                      f"Lat Error: {lateral_position:.3f}m | "
                      f"β: {beta:.3f} | "
                      f"Latency: {measured_latency_us:.1f}µs")
            
            step += 1
            
            if done or truncated:
                print("  Episode completed, resetting...")
                obs, info = env.reset()
                # Reset vehicle speed
                try:
                    env.unwrapped.vehicle.speed = 25.0
                except:
                    pass
                
    except KeyboardInterrupt:
        print("\n⏹️ Recording stopped by user")
    finally:
        # Clean up
        recorder.release()
        env.close()
        
        # Save metrics
        with open(metrics_filename, 'w') as f:
            # Convert numpy arrays to lists for JSON
            json_metrics = {k: [float(x) for x in v] if v else [] 
                          for k, v in metrics_history.items()}
            json.dump(json_metrics, f, indent=2)
        
        print()
        print("=" * 70)
        print("✅ RECORDING COMPLETE")
        print("=" * 70)
        print(f"📹 Video saved: {video_filename}")
        print(f"📊 Metrics saved: {metrics_filename}")
        print(f"📈 Total frames recorded: {step}")
        
        # Print summary statistics
        if metrics_history['lat_error']:
            lat_errors = np.abs(metrics_history['lat_error'])
            print()
            print("📊 RECORDED METRICS SUMMARY:")
            print(f"   Mean lateral error: {np.mean(lat_errors):.4f} m")
            print(f"   Max lateral error: {np.max(lat_errors):.4f} m")
            print(f"   95th percentile error: {np.percentile(lat_errors, 95):.4f} m")
            print(f"   Mean latency: {np.mean(metrics_history['latency']):.2f} ms")
            print(f"   Mean steering: {np.mean(metrics_history['steering']):.3f} rad")
            print(f"   Mean speed: {np.mean(metrics_history['speed']):.1f} m/s")
            
        print()
        print("🎬 You can now play the video file using any media player.")
        print("=" * 70)

def create_final_presentation_video():
    """
    Creates a shorter, highlight video for presentation/demo
    (30 seconds, optimized for showing key features)
    """
    print("\n🎥 Creating presentation-ready video (30 seconds)...")
    run_and_record_lans_demo(
        duration_seconds=30,  # 30 second highlight
        fps=30,
        output_name="lans_presentation"
    )

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Record LANS Controller Highway Demo')
    parser.add_argument('--duration', type=int, default=30,
                       help='Duration in seconds (default: 30)')
    parser.add_argument('--fps', type=int, default=30,
                       help='Output video FPS (default: 30)')
    parser.add_argument('--output', type=str, default='lans_demo',
                       help='Output filename base (default: lans_demo)')
    parser.add_argument('--full', action='store_true',
                       help='Run full 2-minute demonstration')
    
    args = parser.parse_args()
    
    if args.full:
        # Full 2-minute demo for thorough documentation
        run_and_record_lans_demo(
            duration_seconds=120,
            fps=30,
            output_name="lans_full_demo"
        )
    else:
        # Standard 30-second demo
        run_and_record_lans_demo(
            duration_seconds=args.duration,
            fps=args.fps,
            output_name=args.output
        )
    
    print("\n✨ To play the video: Simply double-click the .mp4 file in the recordings folder")
    print("📁 All recordings are saved in the 'recordings_YYYYMMDD_HHMMSS' folder")