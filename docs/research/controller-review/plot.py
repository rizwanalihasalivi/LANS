"""Plot reviewed CSV evidence without rerunning training or simulator campaigns."""
import csv
from pathlib import Path
from statistics import mean
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
def rows(path):
    with path.open() as f:
        return list(csv.DictReader(f))

data = rows(HERE/'aggregates.csv')
regions = ['nominal','tire_mismatch','low_friction','sensor_stress','latency20','latency100']
labels = ['Nominal','Tire/contact mismatch','Low friction','Sensor stress','20 ms delay','100 ms delay']
fig, axes = plt.subplots(1, 3, figsize=(17, 5.2), layout='constrained')
colors = ['#3973ac','#2c9276','#cf8130']
for i,(stage,method,label) in enumerate([
    ('revision2-test','gated_residual','V2 surrogate: 5 seeds'),
    ('revision2-native-test','gated_residual','V2 Webots: 5 seeds'),
    ('revision3-600k','baseline600','V3 600k development: 2 seeds')]):
    values=[]
    for region in regions:
        name='contact_softening' if stage=='revision2-native-test' and region=='tire_mismatch' else region
        values.append(next(float(r['improvement_vs_lqr_pct']) for r in data if
                           r['stage']==stage and r['method']==method and r['region']==name))
    axes[0].barh(np.arange(6)+(i-1)*.23, values, height=.23, color=colors[i], label=label)
axes[0].axvline(0,color='#333333',lw=.8)
axes[0].set(yticks=np.arange(6),yticklabels=labels,xlabel='RMSE reduction vs paired LQR (%)',
            title='Small gains; no consistent large advantage')
axes[0].invert_yaxis();axes[0].legend(fontsize=7,loc='lower right')
curve=rows(ROOT/'integrations/webots/results/revision3-600k/learning-curve.csv')
for seed,color in [('101',colors[0]),('202',colors[1])]:
    subset=[r for r in curve if r['region']=='all' and r['seed']==seed]
    axes[1].plot([int(r['steps'])/1000 for r in subset],
                 [float(r['mean_penalized_rmse']) for r in subset], 'o-', color=color,label=f'Seed {seed}')
for method,label,color in [('lqr','LQR','#777777'),('legacy_gated','Old gated 1M','#b54141')]:
    values=[float(r['mean_rmse_m']) for r in data if r['stage']=='revision3-600k' and r['method']==method]
    axes[1].axhline(mean(values),ls='--',color=color,label=label)
axes[1].set(xlabel='Training steps (thousands)',ylabel='Mean RMSE (m), zoomed axis',
            title='600k curve: mixed, nearly flat')
axes[1].legend(fontsize=8);axes[1].grid(alpha=.2)
diagnostics=rows(HERE/'diagnostics.csv')
for i,(method,label,color) in enumerate([('lqr','LQR',colors[0]),('600k_gated','600k + gate',colors[1]),('600k_direct','600k direct',colors[2])]):
    values=[float(next(r for r in diagnostics if r['scenario']==region and r['diagnostic']==method)['penalized_rmse']) for region in ('nominal','tire_mismatch')]
    axes[2].bar(np.arange(2)+(i-1)*.23,values,width=.23,label=label,color=color)
axes[2].set(xticks=[0,1],xticklabels=['Nominal','Tire mismatch'],ylabel='RMSE (m)',
            title='Diagnostic: removing the gate worsens error')
axes[2].legend(fontsize=8)
fig.suptitle('LANS controller review — 24 October 2026',fontsize=15)
fig.supxlabel('Left: separate historical grids, not a cross-stage ranking. Right: one seed, 25 m/s, DLC220; development diagnostic only.',fontsize=9)
fig.savefig(HERE/'review-chart.png',dpi=180)
plt.close(fig)
