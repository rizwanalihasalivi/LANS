import numpy as np

def double_lane_change(t, vx=15, lane_width=3.5):
    s = vx * t  # distance along path (vx = 15 m/s)
    y = np.zeros_like(t)
    
    # First lane change: 20m to 45m (25m transition)
    mask1 = (s >= 20) & (s < 45)
    y[mask1] = lane_width * np.sin(np.pi * (s[mask1] - 20) / 25)
    
    # Second lane change: 70m to 95m (back to 0)
    mask2 = (s >= 70) & (s < 95)
    y[mask2] = lane_width - lane_width * np.sin(np.pi * (s[mask2] - 70) / 25)
    
    return y