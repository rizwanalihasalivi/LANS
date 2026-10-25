"""Plot recorded physical traces; missing data and ambiguous states fail explicitly."""
import argparse
import csv
from pathlib import Path
import numpy as np
from scenarios.double_lane_change import double_lane_change


def generate_reference_path(t, vx=25.):
    """Geometry helper only; plotting requires the recorded reference."""
    return double_lane_change(float(vx)*np.asarray(t), lane_width=3.5)


def compute_rmse(y_actual, y_ref):
    actual, reference = np.asarray(y_actual), np.asarray(y_ref)
    if actual.ndim != 1 or actual.size == 0 or actual.shape != reference.shape:
        raise ValueError('aligned nonempty one-dimensional signals required')
    if not np.isfinite(actual).all() or not np.isfinite(reference).all():
        raise ValueError('finite recorded signals required')
    return float(np.sqrt(np.mean((actual-reference)**2)))


def signals(data, state_layout=None):
    if state_layout not in (None, 'absolute_vy_r_y_psi', 'error_ey_eydot_epsi_epsidot'):
        raise ValueError('unsupported state layout')
    t = np.asarray(data['t'], dtype=float)
    reference = np.asarray(data['y_ref'], dtype=float)
    if 'y_actual' in data:
        actual = np.asarray(data['y_actual'], dtype=float)
    elif state_layout is not None:
        x = np.asarray(data['x'], dtype=float)
        if x.shape != (len(t),4):
            raise ValueError('explicit state layout requires an N by 4 state array')
        actual = x[:,2] if state_layout == 'absolute_vy_r_y_psi' else reference+x[:,0]
    else:
        raise ValueError('recorded y_actual or explicit --state-layout is required; magnitude guessing is retired')
    steering = np.asarray(data['u'], dtype=float).reshape(-1)
    rmse = compute_rmse(actual, reference)
    if t.shape != actual.shape or steering.shape != t.shape or not np.isfinite(t).all() or not np.isfinite(steering).all() or np.any(np.diff(t)<=0):
        raise ValueError('time/steering must be finite, aligned and time strictly increasing')
    return t, actual, reference, steering, rmse


def load_lqr_results(filepath, selectors=None):
    path = Path(filepath)
    if path.suffix == '.npz':
        with np.load(path, allow_pickle=False) as archive:
            return {k:archive[k] for k in archive.files}
    with path.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    for key, value in (selectors or {}).items():
        if value is not None:
            rows = [row for row in rows if row.get(key)==str(value)]
    if not rows:
        raise ValueError('no recorded trace rows match the selection')
    case_fields = [k for k in ('method','seed','speed','delay_ms') if k in rows[0]]
    if len({tuple(row[k] for k in case_fields) for row in rows}) != 1:
        raise ValueError('select one method/seed/speed/delay case before plotting')
    return dict(t=np.array([float(r['state_time_s']) for r in rows]),
                y_actual=np.array([float(r['y_phys']) for r in rows]),
                y_ref=np.array([float(r['y_ref']) for r in rows]),
                u=np.array([float(r['steering']) for r in rows]))


def plot_lqr_results(data, output, state_layout=None):
    t, actual, reference, steering, rmse = signals(data, state_layout)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    fig, axes = plt.subplots(3,1,figsize=(10,8),layout='constrained')
    axes[0].plot(t,reference,'k--',label='Recorded reference')
    axes[0].plot(t,actual,label='Recorded physical position')
    axes[0].set(ylabel='Lateral position (m)',title=f'Executed-sample RMSE: {rmse:.6f} m');axes[0].legend()
    axes[1].plot(t,actual-reference);axes[1].set(ylabel='Lateral error (m)')
    axes[2].plot(t,steering);axes[2].set(ylabel='Steering (rad)',xlabel='State time (s)')
    fig.savefig(out/'tracking.png',dpi=180);plt.close(fig)
    (out/'README.txt').write_text(f'Executed-sample RMSE: {rmse:.9f} m. Inspect episode survival and failed tails separately; this plot does not establish completion or safety.\n')
    return rmse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--state-layout',choices=['absolute_vy_r_y_psi','error_ey_eydot_epsi_epsidot'])
    for key in ('method','seed','speed','delay_ms'):
        parser.add_argument('--'+key.replace('_','-'))
    args = parser.parse_args()
    selectors = {k:getattr(args,k) for k in ('method','seed','speed','delay_ms')}
    print(plot_lqr_results(load_lqr_results(args.input,selectors),args.output,args.state_layout))


if __name__ == '__main__':
    main()
