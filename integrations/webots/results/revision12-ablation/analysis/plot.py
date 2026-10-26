"""Plot existing development rows; no simulation, fitting, or selection."""
import argparse
import csv
from pathlib import Path
from statistics import mean

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with (args.run / 'episodes.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1080
    score = lambda method: mean(float(r['penalized_rmse']) for r in rows if r['method'] == method)
    baseline = score('lqr')
    fig, ax = plt.subplots(figsize=(10.8, 5.4))
    variants = ['legacy', 'preview', 'lateral']
    for offset, proposer, color, label in [
        (-.24, 'fixed_m004', '#6a8b9e', 'Fixed -0.04 rad'),
        (0., 'fixed_p004', '#d98838', 'Fixed +0.04 rad'),
        (.24, 'student', '#4264a8', 'Frozen supervised student'),
    ]:
        gains = [100 * (1 - score(v + '_' + proposer) / baseline) for v in variants]
        bars = ax.bar([i + offset for i in range(3)], gains, width=.22, color=color, label=label)
        ax.bar_label(bars, labels=[f'{value:.2f}%' for value in gains], padding=4, fontsize=10)
    ax.set_xticks(range(3), ['Original gate', 'Preview predictor only', 'Lateral objective only'])
    ax.set_ylabel('Reduction in mean lateral RMSE versus LQR (%)')
    ax.set_ylim(0, 10.9)
    ax.set_title('Changing the gate objective helps fixed corrections most', loc='left', pad=20, fontsize=14)
    ax.legend(loc='upper left', frameon=False)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, alpha=.2)
    ax.spines[['top', 'right']].set_visible(False)
    fig.text(.08, .055, 'Development only: 108 episodes per method, all survived. No additional training.', fontsize=10)
    fig.text(.08, .018, 'The 9.12% result is nonlearned; heading/steering trade-offs appear in representative traces.', fontsize=10)
    fig.tight_layout(rect=(0, .09, 1, 1))
    fig.savefig(args.output, dpi=180, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    main()
