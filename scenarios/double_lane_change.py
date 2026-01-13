import numpy as np

def double_lane_change(t, vx=15.0, lane_width=3.5):
    """
    Smooth double lane change reference path using sine transitions.
    - vx: longitudinal speed (m/s) — used to convert time to distance
    - lane_width: amplitude of lane change (m)
    """
    s = vx * t  # distance along path
    y = np.zeros_like(t)
    
    # First lane change: 20 m to 45 m distance (25 m transition)
    mask1 = (s >= 20) & (s < 45)
    y[mask1] = lane_width * np.sin(np.pi * (s[mask1] - 20) / 25)
    
    # Second lane change: 70 m to 95 m (back to 0)
    mask2 = (s >= 70) & (s < 95)
    y[mask2] = lane_width - lane_width * np.sin(np.pi * (s[mask2] - 70) / 25)
    
    return y