"""Independent reduced-model arithmetic check of the user-pasted Doubao claim.

This does not execute or reproduce Doubao's unavailable proof scripts, validate
its ISS constants, or certify the nonlinear vehicle, switching, queues or WCET.
The model, gain and timestep below are taken from the pasted conversation.
"""
import argparse
import json
from pathlib import Path
import numpy as np


def augmented(A, B, K, delay):
    """x+=A*x+B*q[0], q=[oldest,...,newest], u=-K*predicted_arrival."""
    n, m = B.shape
    assert m == 1 and delay > 0
    G = np.hstack([np.linalg.matrix_power(A, delay-1-j) @ B for j in range(delay)])
    M = np.zeros((n+delay, n+delay))
    M[:n, :n] = A
    M[:n, n:n+1] = B
    if delay > 1:
        M[n:-1, n+1:] = np.eye(delay-1)
    M[-1, :n] = -K @ np.linalg.matrix_power(A, delay)
    M[-1, n:] = -K @ G
    # For this invertible A, p=A**delay*x+G*q is an invertible state change.
    T = np.block([[np.linalg.matrix_power(A, delay), G],
                  [np.zeros((delay, n)), np.eye(delay)]])
    N = np.zeros_like(M)
    N[:n, :n] = A-B@K
    if delay > 1:
        N[n:-1, n+1:] = np.eye(delay-1)
    N[-1, :n] = -K
    return M, T, N


def main(output):
    h, speed, length = .01, 25., 2.6
    A = np.array([[1., speed*h], [0., 1.]])
    B = np.array([[0.], [speed*h/length]])
    K = .25*np.array([[.2952169, 1.4098921]])
    F = A-B@K
    checks = []
    for delay in range(1, 21):
        M, T, N = augmented(A, B, K, delay)
        coordinate_error = float(np.max(np.abs(T@M-N@T)))
        errors = []
        for z in (1.3+.4j, .7+.6j, -1.2+.3j):
            actual = np.linalg.det(z*np.eye(len(M))-M)
            expected = z**delay*np.linalg.det(z*np.eye(2)-F)
            errors.append(float(abs(actual-expected)/max(abs(expected),1e-15)))
        assert coordinate_error < 1e-12 and max(errors) < 1e-11
        checks.append(dict(delay_ticks=delay, coordinate_identity_error=coordinate_error,
                           max_relative_characteristic_identity_error=max(errors)))
    # A general switching counterexample: stable modes alone are insufficient.
    S1=np.array([[.5,2.],[0.,.5]]);S2=S1.T
    result=dict(
        scope='Independent arithmetic for exact, fixed, known integer input delay and full-state linear predictor. Not a full LANS validation.',
        source='Numeric parameters transcribed from user-pasted Doubao conversation; original scripts unavailable.',
        A=A.tolist(),B=B.tolist(),K=K.tolist(),
        no_delay_eigenvalues=[[float(z.real),float(z.imag)] for z in np.linalg.eigvals(F)],
        spectral_radius=float(max(abs(np.linalg.eigvals(F)))),checks=checks,
        max_coordinate_error=max(r['coordinate_identity_error'] for r in checks),
        max_characteristic_relative_error=max(r['max_relative_characteristic_identity_error'] for r in checks),
        lag_from_beta_0_1175_s=float(-h/np.log(1-.1175)),
        small_angle_kinematic_example=dict(delta_rad=.01,speed_m_s=speed,length_m=length,
            yaw_rate_rad_s=speed*.01/length,lateral_acceleration_m_s2=speed**2*.01/length,
            limitation='Illustrative kinematic approximation, not measured LANS contribution or nonlinear tire prediction.'),
        switching_counterexample=dict(mode_radii=[float(max(abs(np.linalg.eigvals(S)))) for S in (S1,S2)],
            two_step_product_radius=float(max(abs(np.linalg.eigvals(S2@S1)))),
            limitation='Generic mathematical counterexample, not a simulated LANS failure.'),
        not_checked=['Doubao original theorem derivation files','actuator-augmented gain and matrices','ISS constants1279/3028',
                     'platoon theorem or simulations','time-varying delay','saturation/rate limiting/nonlinear vehicle',
                     'RTOS/WCET/schedulability or physical safety'])
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('spectral_radius','max_coordinate_error','max_characteristic_relative_error','small_angle_kinematic_example','switching_counterexample')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)
