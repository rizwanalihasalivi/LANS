import numpy as np
import os

def test_lqr_results_file_exists():
    assert os.path.exists('lqr_run_results.npz'), 'Run run_baseline.py to generate lqr_run_results.npz before running tests.'


def test_lqr_results_shape_and_metrics():
    data = np.load('lqr_run_results.npz')
    t = data['t']
    x = data['x']
    u = data['u']
    kref = data['kref']

    # basic shape checks
    assert t.ndim == 1
    assert x.ndim == 2 and x.shape[1] == 4
    assert u.ndim == 1 and u.shape[0] == t.shape[0]

    # simple performance check: max lateral error should be within a reasonable bound
    y = x[:, 2]
    max_y = float(np.max(np.abs(y)))
    assert max_y < 2.5, f'Max lateral error too large: {max_y} m (expected < 2.5 m)'

    # steering should not exceed saturation
    max_u = float(np.max(np.abs(u)))
    assert max_u <= 0.41, f'Steering exceeds expected saturation: {max_u} rad'
