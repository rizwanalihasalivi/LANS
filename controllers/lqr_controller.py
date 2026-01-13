import numpy as np
from scipy.linalg import solve_continuous_are

def lqr_gain(A, B):
    # Tuned Q and R for smooth tracking (reduced oscillations)
    Q = np.diag([10.0, 10.0, 5.0, 5.0])   # Balanced: less aggressive on position
    R = np.array([[20.0]])                 # Higher penalty on steering → smoother
    P = solve_continuous_are(A, B, Q, R)
    K = np.linalg.inv(R) @ B.T @ P
    return K