"""Posthoc visualization of frozen revision13 evidence; never selects a controller.

Run with the project Python: python plot.py [--results PATH] [--output PATH]
Inputs are completed, verified phase reports and their full episode CSVs.
"""
import argparse
import csv
import json
import math
import os
from pathlib import Path
from statistics import mean

os.environ.setdefault('MPLCONFIGDIR', '/tmp/lans-r13-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

METRICS = ('penalized_rmse', 'penalized_heading_rmse', 'actuator_rate_rms', 'actuator_total_variation')
SUBSETS = {
    'original_positive': lambda r: r['geometry'] in ('sine120', 'dlc220') and int(r['sign']) == 1,
    'original_mirrored': lambda r: r['geometry'] in ('sine120', 'dlc220') and int(r['sign']) == -1,
    'new_positive': lambda r: r['geometry'] not in ('sine120', 'dlc220') and int(r['sign']) == 1,
    'new_mirrored': lambda r: r['geometry'] not in ('sine120', 'dlc220') and int(r['sign']) == -1,
}


def load_phase(results, phase):
    folder = results / phase
    summary = json.loads((folder / 'summary.json').read_text())
    verification = json.loads((folder / 'verification.json').read_text())
    complete = json.loads((folder / 'complete.json').read_text())
    if not (verification['verified'] is True and summary['phase'] == verification['phase'] == complete['phase'] == phase):
        raise ValueError('phase verification mismatch')
    if not (summary['protocol'] == verification['protocol'] == complete['protocol']):
        raise ValueError('protocol mismatch')
    if not (summary['source_commit'] == verification['source_commit'] == complete['source_commit']):
        raise ValueError('source mismatch')
    with (folder / 'episodes.csv').open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != complete['episodes'] or len(rows) != verification['episodes']:
        raise ValueError('incomplete episode input')
    tables = [('all', summary['summary'], rows)]
    if phase == 'confirmation':
        tables.extend((name, summary['replication_subsets'][name], [r for r in rows if predicate(r)])
                      for name, predicate in SUBSETS.items())
    for population, table, population_rows in tables:
        for method, reported in table.items():
            values = [r for r in population_rows if r['method'] == method]
            if len(values) != reported['episodes'] or len(values) != (432 if population == 'all' else 108):
                raise ValueError('wrong population size')
            for metric in METRICS:
                actual = mean(float(r[metric]) for r in values)
                if not math.isclose(actual, reported[metric], rel_tol=1e-12, abs_tol=1e-12):
                    raise ValueError('full-episode mean disagrees with summary')
            if sum(r['survived'].lower() == 'true' for r in values) != reported['survived']:
                raise ValueError('survival denominator mismatch')
    return summary


def change(table, method, metric):
    return 100 * (table[method][metric] / table['lqr'][metric] - 1)


def label(method):
    gate, proposer = method.rsplit('_', 1)
    if method.endswith('fixed_p004'):
        gate, proposer = method[:-len('_fixed_p004')], 'fixed +0.04'
    elif method.endswith('fixed_m004'):
        gate, proposer = method[:-len('_fixed_m004')], 'fixed -0.04'
    return gate.replace('balanced_', '').capitalize() + ' / ' + proposer


def create(results, output):
    confirmation = load_phase(results, 'confirmation')
    development = load_phase(results, 'development')
    if confirmation['source_commit'] != development['source_commit'] or confirmation['protocol'] != development['protocol']:
        raise ValueError('confirmation and development are not the same frozen implementation')
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':10, 'axes.spines.top':False,
                         'axes.spines.right':False, 'figure.facecolor':'white'})
    fig = plt.figure(figsize=(15, 13.5))
    grid = fig.add_gridspec(2, 1, height_ratios=(1, 1.55), hspace=.67)
    ax = fig.add_subplot(grid[0])
    populations = list(SUBSETS) + ['full_grid']
    names = ['Original +\n108 cells', 'Original mirrored\n108 cells',
             'New +\n108 cells', 'New mirrored\n108 cells', 'Full mirrored grid\n432 cells']
    methods = ['lateral_fixed_p004', 'lateral_fixed_m004', 'lateral_student']
    styles = [('Fixed +0.04', '#23659c'), ('Fixed -0.04', '#72abc7'), ('Frozen student', '#b57629')]
    for index, (method, (name, color)) in enumerate(zip(methods, styles)):
        values = [-change(confirmation['summary'] if population == 'full_grid' else confirmation['replication_subsets'][population],
                          method, 'penalized_rmse') for population in populations]
        bars = ax.bar(np.arange(5)+(index-1)*.24, values, width=.23, label=name, color=color)
        ax.bar_label(bars, labels=[f'{value:.2f}%' for value in values], padding=4, fontsize=9)
    ax.set_xticks(np.arange(5), names)
    ax.set_ylim(min(0, ax.get_ylim()[0]), max(11, ax.get_ylim()[1]*1.15))
    ax.axhline(5, linestyle='--', linewidth=1, color='#777777', alpha=.6)
    ax.axvline(3.5, color='#777777', alpha=.45, linewidth=1)
    ax.set_ylabel('Lateral RMSE reduction vs paired LQR (%)\nHigher is better')
    ax.set_title('A  Fresh-noise confirmation: lateral gate, different road populations', loc='left', fontweight='bold', pad=16)
    ax.legend(ncol=3, loc='upper right', frameon=False)
    ax.text(0, -.27, 'Original: sine120 / DLC220. New: sine150 / DLC264. Each subset has 3 pairs × 3 speeds × 2 roads × 6 conditions.\n'
            'Dashed 5% line is the original-positive replication screen only. Opposite fixed signs exchange performance under reflection.',
            transform=ax.transAxes, fontsize=9, color='#555555', va='top')
    ax.grid(axis='y', alpha=.15)
    ax.set_axisbelow(True)

    ax = fig.add_subplot(grid[1])
    table = development['summary']
    dev_methods = [name for name in table if name != 'lqr']
    actual = np.array([[-change(table, method, METRICS[0])] + [change(table, method, metric) for metric in METRICS[1:]]
                       for method in dev_methods])
    desirability = actual * np.array([1, -1, -1, -1])
    color_limit = 20
    ax.imshow(desirability, cmap='RdBu', vmin=-color_limit, vmax=color_limit, aspect='auto')
    for i in range(actual.shape[0]):
        for j in range(actual.shape[1]):
            ax.text(j, i, f'{actual[i,j]:+.2f}%', ha='center', va='center', fontsize=11,
                    color='white' if abs(desirability[i,j]) > color_limit*.65 else '#202020')
    ax.set_yticks(np.arange(len(dev_methods)), [label(method) for method in dev_methods])
    ax.set_xticks(np.arange(4), ['Lateral RMSE reduction\npositive is better', 'Heading RMSE change\nnegative is better',
                                'Actuator rate RMS change\nnegative is better', 'Actuator total variation change\nnegative is better'])
    ax.tick_params(axis='both', length=0, pad=10)
    ax.xaxis.tick_top()
    ax.set_title('B  Balanced-objective development: every method has the same 432-cell grid', loc='left', fontweight='bold', pad=55)
    for boundary in (2.5, 5.5, 8.5):
        ax.axhline(boundary, color='white', linewidth=3)
    for spine in ax.spines.values():
        spine.set_visible(False)
    selected = development['selected_candidate'] or 'none (frozen criteria not met)'
    ax.text(0, -.065, 'Every value is a ratio of equally weighted full-episode means against paired LQR; no representative-trace substitution.\n'
            'Blue = favorable change; red = unfavorable change. Color scale clips at ±20%; annotations show exact changes.\n'
            f'Development selected candidate: {selected}. Students are comparators, not selection candidates.',
            transform=ax.transAxes, fontsize=9, color='#555555', va='top')
    fig.suptitle('Revision13 | replicated lateral benefit and the cost of balancing it', x=.08, y=.985,
                 ha='left', fontsize=17, fontweight='bold')
    fig.text(.08, .951, f"Frozen implementation {confirmation['source_commit'][:7]} · confirmation and development use independent noise streams",
             fontsize=10, color='#555555')
    fig.text(.08, .016, 'Mirrors share transformed noise and initial conditions; they are correlated symmetry checks, not independent seeds.\n'
             'Lateral/heading means use declared failure penalties. All six conditions, including exact-LQR 100 ms fallback, remain in the means.',
             fontsize=9, color='#555555')
    fig.subplots_adjust(left=.22, right=.97, top=.91, bottom=.13)
    fig.savefig(output, dpi=180, facecolor='white')
    plt.close(fig)

    print('| Confirmation population | Fixed + gain | Fixed - gain | Student gain | Cells/method |')
    print('|---|---:|---:|---:|---:|')
    for population in populations:
        values = confirmation['summary'] if population == 'full_grid' else confirmation['replication_subsets'][population]
        gains = [-change(values, method, 'penalized_rmse') for method in methods]
        print(f'| {population} | {gains[0]:.4f}% | {gains[1]:.4f}% | {gains[2]:.4f}% | {values["lqr"]["episodes"]} |')
    print('\n| DEV controller | RMSE (m) | Lateral gain | Heading change | Rate change | TV change | Survival |')
    print('|---|---:|---:|---:|---:|---:|---:|')
    for method, values in zip(dev_methods, actual):
        row = table[method]
        print(f'| {method} | {row["penalized_rmse"]:.8f} | {values[0]:+.4f}% | {values[1]:+.4f}% | {values[2]:+.4f}% | {values[3]:+.4f}% | {row["survived"]}/{row["episodes"]} |')
    print('\nSelected candidate:', selected)
    for method, assessment in development['assessments'].items():
        print(method + ': ' + ', '.join(k for k,v in assessment['checks'].items() if not v))
        print('  Versus same-sign lateral gate: rate reduction '
              f"{assessment['rate_reduction_vs_same_sign_lateral_percent']:.4f}%, "
              f"TV reduction {assessment['tv_reduction_vs_same_sign_lateral_percent']:.4f}%")
    print('Plot:', output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    create(args.results, args.output or args.results/'comparison.png')
