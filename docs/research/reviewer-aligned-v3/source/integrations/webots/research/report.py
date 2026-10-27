"""Generate tables and figures only from verified completed evidence."""
import csv,datetime,hashlib,importlib.metadata,json,platform
from pathlib import Path
from statistics import mean
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'results/research-core'
verified=json.loads((out/'campaign-verification.json').read_text());assert verified['verified']
physics=json.loads((out/'physical-audit.json').read_text())
core=json.loads((out/'checks.json').read_text())
evaluation=json.loads((ROOT/'results/research-evaluation/summary.json').read_text())
lines=['# Verified campaign results','',f"Final training: **{verified['final_training_steps']:,} steps**, ten policies, five seeds per role.",
       'Surrogate comparison: **810 episodes**; native Webots transfer: **45 cases**. Failed cases remain in the denominators.','',
       '## Paired surrogate results','',
       '| Method | Survived / 135 | Corridor-clean / 135 | Mean failure-penalized RMSE (m) | SD across five seed means (m) |',
       '|---|---:|---:|---:|---:|']
for method,data in evaluation.items():
    lines.append(f"| {method} | {data['survived']} | {data['corridor_clean']} | {data['mean_penalized_rmse']:.6f} | {data['sample_sd_across_seeds']:.6f} |")
lines+=['','Each seed contributes 27 conditions per method. SD is across five seed means, not correlated time steps. Failure-penalized RMSE assigns 2.5 m error to the unexecuted remainder after tracking termination; it is a predefined score, not measured post-failure motion. Corridor checking is an additional sampled, non-ISO footprint metric.','',
        '## Native Webots transfer','',
        '| Mode | Added minimum delay (ms) | Survived / 15 | Mean tracking RMSE (m) | Mean fallback occupancy |','|---|---:|---:|---:|---:|']
for mode,delay in [('ppo',0),('fusion',0),('fusion',100)]:
    cells=[v for v in physics['transfer'].values() if v['mode']==mode and v['delay_ms']==delay]
    assert len(cells)==15
    fallback='—' if mode=='ppo' else f"{mean(v['fallback_fraction'] for v in cells):.3%}"
    lines.append(f"| {mode} | {delay} | {sum(v['survived'] for v in cells)} | {mean(v['rmse_m'] for v in cells):.6f} | {fallback} |")
lines+=['','These transfer RMSEs are over executed samples; consult survival and per-case CSVs rather than treating a truncated failed trajectory as a successful low-error run. Timing is diagnostic under cloud CPU contention, not a real-time deadline guarantee.','',
        '## Corrected LQR in Webots','',
        '| Speed (m/s) | Noiseless RMSE (m) | Noisy RMSE (m) | Noisy + 10 ms sensor-delay RMSE (m) |','|---|---:|---:|---:|']
for speed in (15,20,25):
    values=[physics['tracking'][f'lqr-v{speed}-noise{n}-delay{d}']['rmse_m'] for n,d in [(0,0),(1,0),(1,1)]]
    lines.append(f"| {speed} | {values[0]:.6f} | {values[1]:.6f} | {values[2]:.6f} |")
lines+=['','## Parameter and numerical checks','',
        '- Runtime composite audit: 1,650 kg, nominal CG 1.4 m from the rear axle, nominal yaw inertia 4,224 kg·m².',
        '- Wheel-inclusive track/geometry and steering sign/units checked from the actual world and motion.','',
        '| Speed (m/s), positive steer | Effective front stiffness (N/rad) | Effective rear stiffness (N/rad) |','|---|---:|---:|']
for speed in (15,20,25):
    x=physics['tire_identification'][f'open-v{speed}-d0.003'];lines.append(f"| {speed} | {x['effective_Cf_N_rad']:.1f} | {x['effective_Cr_N_rad']:.1f} |")
lines+=['','These are steady-state effective small-slip estimates from a native contact model, not Fiala identification or real-vehicle measurements.',
        f"- Fiala surrogate, 1 ms vs 0.5 ms maximum final-state difference: {core['one_ms_vs_half_ms_max_state_difference']:.3g} (mixed state units; see raw vector values).",'',
        '| Webots step | Relative steady-curvature difference vs 1 ms | Final lateral-position difference (m) |','|---|---:|---:|']
for step,value in physics['physics_convergence'].items():lines.append(f"| {step} ms | {value['relative_curvature_difference_vs_1ms']:.6%} | {value['final_y_difference_m']:.6f} |")
lines+=['','## Course feasibility','',
        '| Smoothed course | Peak curvature (1/m) | Lateral acceleration at 15 / 20 / 25 m/s (m/s²) | Passes 0.8 μg margin |','|---|---:|---|---|']
for name,value in core['path_screen'].items():
    acceleration=' / '.join(f"{value['speeds'][str(v)]['lateral_accel_m_s2']:.3f}" for v in (15,20,25))
    passes=' / '.join(str(value['speeds'][str(v)]['passes_margin']) for v in (15,20,25))
    lines.append(f"| {name} | {value['max_curvature_per_m']:.6f} | {acceleration} | {passes} |")
lines+=['','The 125 m result applies to the tested quintic smoothing of the proposed section lengths; it is not a statement about every possible 125 m path. The 220 m course is explicitly a different development geometry, with no ISO claim.','',
        '## Limits','',
        '- Held-out noise realizations, not unseen path geometries. Five seeds and these conditions do not establish general superiority or convergence.',
        '- Native Webots contact slip is small-slip calibrated but is not the surrogate Fiala tire law; large-angle/load-transfer equivalence is unvalidated.',
        '- PPO uses curvature previews; the analytical LQR uses local curvature. These are end-to-end comparisons, not a preview-information-matched learning ablation.',
        '- Surrogate delays are deterministic service-time simulations; only native fusion uses a real separate inference process. Wall and simulation clocks are not interchangeable.',
        '- Primary repository models, phase-1 experiments and specification remain unchanged. No real-vehicle safety or stability claim is made.','']
(out/'report.md').write_text('\n'.join(lines))
versions={name:importlib.metadata.version(name) for name in ['numpy','scipy','torch','stable-baselines3','gymnasium','numba']}
(out/'runtime.json').write_text(json.dumps({'recorded_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'python':platform.python_version(),'platform':platform.platform(),'packages':versions,'webots':'R2025a','cpu_quota':'4 CPUs in tested cloud instance','physics_rendering':'Mesa software/Xvfb'},indent=2)+'\n')
# Publication figures: actual episode/seed aggregates, not fabricated illustrations.
methods=list(evaluation)
fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
axes[0].bar(methods,[evaluation[m]['survived']/135 for m in methods],color='#347c92');axes[0].set_ylim(0,1.05);axes[0].set_ylabel('Episode survival fraction')
axes[1].bar(methods,[evaluation[m]['mean_penalized_rmse'] for m in methods],yerr=[evaluation[m]['sample_sd_across_seeds'] for m in methods],capsize=4,color='#bd7040');axes[1].set_ylabel('Penalized RMSE (m), seed SD')
for ax in axes:ax.tick_params(axis='x',rotation=35);ax.grid(axis='y',alpha=.2)
fig.savefig(out/'comparison.png',dpi=180);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
for role,ax in zip(('full','residual'),axes):
    for seed in range(5):
        episodes=[]
        for p in (ROOT/f'results/research-training/{role}-{seed}').glob('episodes-*.csv.monitor.csv'):
            with p.open() as f:next(f);episodes+=list(csv.DictReader(f))
        episodes.sort(key=lambda r:float(r['t']))
        lengths=np.array([int(r['l']) for r in episodes]);x=np.cumsum(lengths)
        if len(lengths)>=50:ax.plot(x[49:],np.convolve(lengths,np.ones(50)/50,mode='valid'),label=f'seed {seed}',linewidth=1)
    ax.set_title(role);ax.set_xlabel('Steps in completed episodes (excludes unfinished tails)');ax.set_ylabel('50-episode mean length (max 800)');ax.set_ylim(0,820);ax.legend(fontsize=7);ax.grid(alpha=.2)
fig.savefig(out/'learning.png',dpi=180);plt.close(fig)
print(out/'report.md')
