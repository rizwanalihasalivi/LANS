"""
Evaluation harness to compare controllers (LQR vs PPO) using standard metrics.
Saves a CSV or prints metrics.
"""
import numpy as np
import os

def compute_metrics(npz_path):
    data = np.load(npz_path)
    t = data['t']
    x = data['x']
    u = data['u']

    y = x[:, 2]
    psi = x[:, 3]

    dt = t[1] - t[0]
    rmse_y = float(np.sqrt(np.mean(y ** 2)))
    max_y = float(np.max(np.abs(y)))
    iae_y = float(np.sum(np.abs(y)) * dt)
    rmse_psi = float(np.sqrt(np.mean(psi ** 2)))
    mean_abs_u = float(np.mean(np.abs(u)))
    sat_rate = float(np.mean(np.isclose(np.abs(u), 0.4, atol=1e-3)))

    metrics = {
        'rmse_y': rmse_y,
        'max_y': max_y,
        'iae_y': iae_y,
        'rmse_psi': rmse_psi,
        'mean_abs_u': mean_abs_u,
        'sat_rate': sat_rate
    }
    return metrics

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--npz', default='lqr_run_results.npz')
    args = p.parse_args()
    if not os.path.exists(args.npz):
        raise FileNotFoundError('Provide a results npz to evaluate.')
    m = compute_metrics(args.npz)
    for k,v in m.items():
        print(f"{k}: {v}")
