"""Independent solve_ivp reference for response-delay forecasts (not plant accuracy)."""
import boot12
import json
import numpy as np
from scipy.integrate import solve_ivp
from compensation import forecast_state as old
from forecast12 import forecast_state as fixed
from comparison import configure_lqr
from core import GAINS


def reference(z, actuator, v, ks, gain, horizon):
    state = np.r_[z, actuator]
    t = 0.
    while t < horizon-1e-12:
        end = min(t+.01, horizon)
        k = np.interp(v*t, [0., 10., 20.], ks)
        vyref = (1.4*v-1650*1.2*v**3/(2.6*80000))*k
        ff = (2.6+1650/2.6*(1.4/80000-1.2/80000)*v*v)*k
        u = np.clip(ff-gain@(state[:4]-[0., vyref, -vyref/v, v*k]), -.5, .5)
        def rhs(at, value):
            ey, vy, ep, r, delta = value
            curvature = np.interp(v*at, [0., 10., 20.], ks)
            front = 80000*(delta-(vy+1.2*r)/v)
            rear = 80000*(-(vy-1.4*r)/v)
            return [vy+v*ep, (front+rear)/1650-v*r, r-v*curvature,
                    (1.2*front-1.4*rear)/4224, np.clip((u-delta)/.05, -.35, .35)]
        sol = solve_ivp(rhs, (t, end), state, method='DOP853', rtol=1e-12, atol=1e-13, max_step=.0005)
        assert sol.success
        state = sol.y[:, -1]
        t = end
    return state


def main(output):
    configure_lqr()
    rng = np.random.default_rng(12031)
    rows = []
    for i in range(24):
        v = (15., 20., 25.)[i % 3]
        args = (rng.normal(size=4)*[.15, .1, .02, .02], float(rng.uniform(-.04, .04)),
                v, rng.normal(size=3)*.002, GAINS[int(v)], (.01, .02, .04, .0137)[i % 4])
        exact = reference(*args)
        before, a, _ = old(*args)
        after, b, _ = fixed(*args)
        error = float(np.max(np.abs(np.r_[after, b]-exact)))
        assert error < 2e-6, (i, error)
        rows.append(dict(row=i, horizon_s=args[-1], speed=v,
                         old_max_abs_state_error=float(np.max(np.abs(np.r_[before, a]-exact))),
                         fixed_max_abs_state_error=error))
    result = dict(scope='24 fixed nominal-model forecasts; independent DOP853 reference; not hidden-plant validation', checks=rows)
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(samples=len(rows), old_max=max(r['old_max_abs_state_error'] for r in rows),
                          fixed_max=max(r['fixed_max_abs_state_error'] for r in rows))))


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=boot12.Path, required=True)
    main(p.parse_args().output)
