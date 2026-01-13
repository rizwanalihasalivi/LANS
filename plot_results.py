import numpy as np
import matplotlib.pyplot as plt
import os

def plot_lqr_results(npz_path='lqr_run_results.npz', show=True, out_png='lqr_run_results.png'):
    if not os.path.exists(npz_path):
        raise FileNotFoundError(f"Results file not found: {npz_path}")
    data = np.load(npz_path)
    t = data['t']
    x = data['x']
    u = data['u']
    kref = data['kref']

    y = x[:, 2]
    psi = x[:, 3]
    vy = x[:, 0]
    r = x[:, 1]

    fig, axs = plt.subplots(4, 1, figsize=(10, 10), sharex=True)
    axs[0].plot(t, y, label='lateral error y (m)')
    axs[0].set_ylabel('m')
    axs[0].legend(); axs[0].grid()

    axs[1].plot(t, psi, label='heading error psi (rad)')
    axs[1].set_ylabel('rad')
    axs[1].legend(); axs[1].grid()

    axs[2].plot(t, vy, label='vy (m/s)')
    axs[2].plot(t, r, label='r (rad/s)')
    axs[2].set_ylabel('state')
    axs[2].legend(); axs[2].grid()

    axs[3].plot(t, u, label='steering (rad)')
    axs[3].plot(t, kref * 0.0, '--', label='ref curvature (not scaled)')
    axs[3].set_ylabel('rad'); axs[3].set_xlabel('time (s)')
    axs[3].legend(); axs[3].grid()

    plt.tight_layout()
    fig.savefig(out_png)
    if show:
        plt.show()

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--npz', default='lqr_run_results.npz')
    p.add_argument('--out', default='lqr_run_results.png')
    args = p.parse_args()
    plot_lqr_results(args.npz, show=True, out_png=args.out)
