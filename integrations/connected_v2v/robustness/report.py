"""Descriptive validation tables/figures; no baseline or thesis benchmarking."""
import argparse
import json
import math
import os
from pathlib import Path
import statistics
os.environ.setdefault('MPLCONFIGDIR','/workspace/LANS/.matplotlib-cache')
os.environ.setdefault('XDG_CACHE_HOME','/workspace/LANS/.matplotlib-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def read(path):return json.loads(Path(path).read_text())


def save(fig,path):
    fig.savefig(path.with_suffix('.png'),dpi=220,bbox_inches='tight')
    fig.savefig(path.with_suffix('.pdf'),bbox_inches='tight')
    plt.close(fig)


def coverage(data,title,path):
    cases=sorted({r['case'] for r in data});speeds=sorted({r['speed'] for r in data})
    grid=np.zeros((len(cases),len(speeds)))
    fig,ax=plt.subplots(figsize=(6.,.45*len(cases)+1.5))
    for i,c in enumerate(cases):
        for j,s in enumerate(speeds):
            group=[r for r in data if r['case']==c and r['speed']==s]
            passed=sum(r['passed'] for r in group);grid[i,j]=passed/len(group)
            ax.text(j,i,f'{passed}/{len(group)}',ha='center',va='center',fontsize=10)
    ax.imshow(grid,vmin=0,vmax=1,cmap='RdYlGn',alpha=.45,aspect='auto')
    ax.set_xticks(range(len(speeds)),[f'{s:g} m/s' for s in speeds]);ax.set_yticks(range(len(cases)),cases)
    ax.set_title(title+'\nExecuted passes / trials; finite scenario coverage',fontsize=11)
    ax.set_xlabel('Configured cruise speed');save(fig,path)


def trace(root,data,path):
    chosen=sorted((r for r in data if r['case']=='dense_curved' and r['speed']==12.),key=lambda r:r['seed'])[0]
    folder=root/'validation'/f"dense_curved-12-{chosen['seed']}";spec=read(folder/'config.json')
    traces={name:[json.loads(s) for s in (folder/f'{name}.jsonl').read_text().splitlines()] for name in spec['starts']}
    fig,axes=plt.subplots(4,1,figsize=(10,13),gridspec_kw={'height_ratios':[2.2,1.,1.,1.2]})
    radius=spec['profile']['radius'];s=np.linspace(-90.,650.,500)
    for d in (-1.75,1.75,5.25):
        axes[0].plot((radius-d)*np.sin(s/radius),radius-(radius-d)*np.cos(s/radius),'--',color='.75',lw=.8)
    colors={'follower':'#1764ab','intruder':'#c44e52','leader':'#333333'}
    for name,rows in traces.items():
        axes[0].plot([r['state'][0] for r in rows],[r['state'][1] for r in rows],
                     color=colors.get(name,'#999999'),lw=2. if name in colors else .9,label=name)
    axes[0].set_aspect('equal',adjustable='datalim');axes[0].set_ylabel('World y (m)');axes[0].set_xlabel('World x (m)')
    axes[0].legend(ncol=4,fontsize=8);axes[0].set_title(f"Native eight-Car curve, radius {radius:g} m; radio {spec.get('radio_range_m',150.):g} m; seed {chosen['seed']}\nRepresentative profile and first validation seed, not best-case selection")
    time=[r['time_s'] for r in traces['follower']]
    for name in colors:
        axes[1].plot(time,[r['state'][3] for r in traces[name]],color=colors[name],label=name)
    axes[1].set_ylabel('Measured speed (m/s)');axes[1].legend(ncol=3,fontsize=8)
    code={'none':0,'disagreement':0,'radar':1,'v2v':2}
    ego=traces['follower']
    axes[2].step(time,[code[r['decision']['sensor_source']] for r in ego],where='post',lw=1.,label='Following input')
    witness=[r['time_s'] for r in ego if r['decision'].get('peer_exit_evidence')]
    axes[2].scatter(witness,[2.4]*len(witness),s=4,color='#228833',label='Fresh neighbor track observations')
    axes[2].set_yticks([0,1,2],['Unavailable','Local radar','V2V']);axes[2].set_ylim(-.2,2.8);axes[2].legend(fontsize=8)
    gap=[r['decision']['target_gap_m'] if r['decision']['target_gap_m'] is not None else math.nan for r in ego]
    axes[3].plot(time,gap,label='Observed selected-target gap',color=colors['follower'])
    axes[3].plot(time,[6.+1.2*r['state'][3] for r in ego],'--',label='Nominal desired gap',color='#ddaa33')
    axes[3].set_ylabel('Gap (m)');axes[3].set_xlabel('Simulation time (s)');axes[3].legend(fontsize=8)
    for ax in axes[1:]:
        ax.axvspan(6.,9.,alpha=.07,color='grey');ax.axvspan(20.,23.,alpha=.07,color='grey');ax.grid(alpha=.2)
    fig.suptitle('Development validation trace: scripted NPC maneuvers, observation-driven ego selection',fontsize=11)
    fig.tight_layout();save(fig,path)


def table(data,seconds):
    lines=['| Profile | Passed | Progress / cruise distance (median; min–max) | Max stopped time | Correct-target spacing RMS (median; max) | Censored stable return |',
           '| --- | --- | --- | --- | --- | --- |']
    for case in sorted({r['case'] for r in data}):
        group=[r for r in data if r['case']==case]
        ratios=[r['progress_m']/(seconds*r['speed']) for r in group if 'progress_m' in r]
        stopped=max((r.get('stopped_ticks',0)*.05 for r in group),default=0.)
        censored=sum(r.get('return_censored',True) for r in group)
        spacing=[r['spacing_rms_on_correct_target_m'] for r in group if r.get('spacing_rms_on_correct_target_m') is not None]
        lines.append(f"| {case} | {sum(r['passed'] for r in group)}/{len(group)} | {statistics.median(ratios):.3f}; {min(ratios):.3f}–{max(ratios):.3f} | {stopped:.2f} s | {statistics.median(spacing):.2f}; {max(spacing):.2f} m | {censored}/{len(group)} |")
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--python',required=True);p.add_argument('--native',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    python,native=Path(a.python),Path(a.native);output=Path(a.output);output.mkdir(parents=True,exist_ok=False)
    data={}
    for name,root,counts in [('python',python,(72,240)),('native',native,(12,36))]:
        for stage,count in zip(('development','validation'),counts):
            summary=read(root/stage/'summary.json');assert len(summary['results'])==count
            data[name+'_'+stage]=summary
    py=data['python_validation']['results'];nat=data['native_validation']['results']
    coverage(py,'Python fresh validation',output/'python-validation-coverage')
    coverage(nat,'Native Webots fresh validation',output/'native-validation-coverage')
    trace(native,nat,output/'native-curved-trace')
    text='# Fresh robustness validation tables\n\nDescriptive results, not final thesis benchmarking.\n\n## Python\n\n'+table(py,32.)+'\n\n## Native Webots\n\n'+table(nat,35.)+'\n\nProgress is measured movement divided by configured cruise distance. Target reacquisition and nominal headway settling are different: full spacing and stop/censoring data remain in every raw episode and summary. Neighbor observations provide exit evidence only; normal following still requires fresh local radar or V2V state.\n'
    (output/'tables.md').write_text(text)
    (output/'summary.json').write_text(json.dumps(data,indent=2)+'\n')


if __name__=='__main__':main()
