"""Export scientific figures and full per-profile metrics; no baseline ranking."""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines()]
def number(value):return float(F(value))


def run(root,output):
    root,output=Path(root),Path(output);output.mkdir(parents=True,exist_ok=False)
    plan=json.loads((root/'plan.json').read_text())
    val=json.loads((root/'validation/summary.json').read_text())['results']
    plt.rcParams.update({'font.size':10,'axes.grid':True,'grid.alpha':.25,'pdf.fonttype':42})
    profile='adversarial_nominal';speed=16;seed=plan['validation_seeds'][0]
    r=rows(root/'validation'/f'{profile}-{speed}-{seed}'/'ticks.jsonl')
    t=[number(z['time']) for z in r]
    gap=[min(number(p[0]) for p in z['obstacles_before'].values())-number(z['ego_before'][0]) for z in r]
    fig,ax=plt.subplots(3,1,figsize=(8,8),sharex=True,constrained_layout=True)
    ax[0].plot(t,gap,label='Actual rear/front bumper gap')
    ax[0].axhline(2,color='crimson',ls='--',label='Required 2 m margin')
    ax[0].set_ylabel('Gap (m)');ax[0].legend(loc='upper right')
    ax[1].plot(t,[number(z['ego_before'][1]) for z in r],label='Actual ego speed')
    ax[1].plot(t,[number(z['certificate']['v']) for z in r],ls='--',label='Certified upper speed')
    ax[1].set_ylabel('Speed (m/s)');ax[1].legend()
    ax[2].plot(t,[number(z['nominal']) for z in r],label='Adversarial nominal request')
    ax[2].plot(t,[number(z['command']) for z in r],label='Shielded command')
    ax[2].set_ylabel('Acceleration (m/s²)');ax[2].set_xlabel('Simulated time (s)');ax[2].legend()
    fig.suptitle(f'Preselected first fresh seed: {profile}, {speed} m/s, seed {seed}\nLongitudinal reference model; leader emergency brakes at 9 s')
    for suffix in ('png','pdf'):fig.savefig(output/f'safety-shield-trace.{suffix}',dpi=180)
    plt.close(fig)
    r=rows(root/'validation'/f'dual_blackout-16-{seed}'/'ticks.jsonl');t=[number(z['time']) for z in r]
    fig,ax=plt.subplots(2,1,figsize=(8,6),sharex=True,constrained_layout=True)
    ax[0].plot(t,[number(z['ego_before'][0]) for z in r],label='Actual ego front')
    ax[0].plot(t,[number(z['certificate']['boundary']) for z in r],label='Retained spatial lower bound')
    ax[0].set_ylabel('Position (m)');ax[0].legend()
    ax[1].plot(t,[number(z['ego_before'][1]) for z in r],label='Ego speed')
    for a in ax:a.axvspan(8,14,color='orange',alpha=.18,label='Both channels unavailable' if a is ax[1] else None)
    ax[1].set_ylabel('Speed (m/s)');ax[1].set_xlabel('Simulated time (s)');ax[1].legend()
    fig.suptitle(f'Dual blackout with a valid old spatial bound, 16 m/s, seed {seed}')
    for suffix in ('png','pdf'):fig.savefig(output/f'blackout-memory-trace.{suffix}',dpi=180)
    plt.close(fig)
    lines=['# Fresh reference validation — safety and progress reported separately','',
        '| Profile | Runs | Minimum continuous gap (m) | Maximum spacing RMS (m) | Maximum stopped time (s) | Median progress (m) |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for profile in plan['profiles']:
        group=[z for z in val if z['profile']==profile]
        lines.append(f"| {profile} | {len(group)} | {min(z['minimum_continuous_gap_m'] for z in group):.6f} | {max(z['spacing_rms_m'] for z in group):.3f} | {max(z['stopped_s'] for z in group):.2f} | {statistics.median(z['progress_m'] for z in group):.3f} |")
    lines+=['','Every intersample minimum is checked exactly before decimal formatting.',
        'These are new 1-D bounded-error reference trials, not Webots validation of the theorem.',
        'Spacing/progress are descriptive and do not form a convergence or superiority claim.']
    (output/'validation-tables.md').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--output',required=True);a=p.parse_args();run(a.root,a.output)
