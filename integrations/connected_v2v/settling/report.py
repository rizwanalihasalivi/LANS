"""Plots/tables for formation settling; no final baseline or literature ranking."""
import argparse
import json
import math
from pathlib import Path
import statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .audit import project

LABELS={'curved':'Curved','dense_curved':'Dense curved','noisy_nonconnected':'Noisy non-connected',
    'burst_misses':'Burst misses','occlusion_brake':'Occlusion + brake','dual_blackout':'Dual blackout',
    'v2v_blackout':'V2V blackout','combined':'Combined'}


def read(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(l) for l in Path(p).read_text().splitlines()]


def unconditional_head_errors(root,stage,group,native):
    whole=[];post=[];gaps=[]
    for result in group:
        path=root/stage/f"{result['case']}-{result['speed']:g}-{result['seed']}"
        spec=read(path/('config.json' if native else 'case.json'));R=spec['profile']['radius']
        if native:
            data=((a['time_s'],a['state'],b['state']) for a,b in zip(rows(path/'follower.jsonl'),rows(path/'leader.jsonl')))
        else:
            data=((z['time_s'],z['before'],z['traffic_before']['leader']) for z in rows(path/'ticks.jsonl'))
        errors=[];later=[];later_gaps=[]
        for t,ego,head in data:
            gap=project(head,R)[0]-project(ego,R)[0]-4.6
            error=gap-6.-1.2*ego[3];errors.append(error)
            if t>=(23. if native else 22.):later.append(error);later_gaps.append(gap)
        whole.append(math.sqrt(math.fsum(x*x for x in errors)/len(errors)))
        post.append(math.sqrt(math.fsum(x*x for x in later)/len(later)))
        gaps.append(max(later_gaps))
    return dict(whole_window_unconditional_head_rms_max_m=max(whole),
        post_exit_unconditional_head_rms_max_m=max(post),post_exit_max_nominal_head_gap_m=max(gaps))


def trace(root,stage,native):
    plan=read(root/'plan.json');seed=plan[stage+'_seeds'][0]
    speed=max(plan[stage+'_speeds'] if native else plan['speeds'])
    path=root/stage/f'combined-{speed:g}-{seed}'
    if native:
        spec=read(path/'config.json');ego=rows(path/'follower.jsonl');head=rows(path/'leader.jsonl')
        return spec,[(a['time_s'],a['state'],b['state'],a['decision'],b['decision']['npc_speed_m_s']) for a,b in zip(ego,head)],seed,speed
    spec=read(path/'case.json');data=rows(path/'ticks.jsonl')
    return spec,[(a['time_s'],a['before'],a['traffic_before']['leader'],a['decision'],a['leader_pacing']['goal_speed']) for a in data],seed,speed


def run(python,native,output,stage):
    python,native,output=map(Path,(python,native,output));output.mkdir(parents=True,exist_ok=False)
    plt.rcParams.update({'font.size':10,'axes.grid':True,'grid.alpha':.25,'pdf.fonttype':42})
    cohorts={name:read(root/stage/'summary.json')['results'] for name,root in [('Python',python),('Webots',native)]}
    assert all(r['passed'] for group in cohorts.values() for r in group)
    for family,root,is_native in [('Python',python,False),('Webots',native,True)]:
        spec,data,seed,speed=trace(root,stage,is_native);R=spec['profile']['radius']
        t=[z[0] for z in data];errors=[];gaps=[];desired=[];categories=[]
        for now,ego,head,info,goal in data:
            gap=project(head,R)[0]-project(ego,R)[0]-4.6;want=6+1.2*ego[3]
            gaps.append(gap);desired.append(want);errors.append(gap-want)
            target=info['selected_radio_id']
            categories.append(0 if info['sensor_source'] not in ('radar','v2v') else 3 if target=='leader' else 2 if target=='intruder' else 1 if target is None else 4)
        fig,ax=plt.subplots(4,1,figsize=(9,10),sharex=True,constrained_layout=True)
        ax[0].plot(t,gaps,label='Head bumper gap');ax[0].plot(t,desired,ls='--',label='6 + 1.2 v desired gap')
        ax[0].set_ylabel('Gap (m)');ax[0].legend(loc='upper right')
        ax[1].plot(t,errors,label='Headway error');ax[1].axhline(0,color='black',lw=.6)
        ax[1].set_ylabel('Error (m)')
        inset=ax[1].inset_axes([.60,.30,.37,.60]);tail=[i for i,x in enumerate(t) if x>=65]
        inset.plot([t[i] for i in tail],[errors[i] for i in tail],lw=1);inset.set_title('Final 5 s',fontsize=8);inset.tick_params(labelsize=7);inset.grid(alpha=.2)
        ax[2].plot(t,[z[1][3] for z in data],label='Ego speed');ax[2].plot(t,[z[2][3] for z in data],label='Head speed')
        ax[2].plot(t,[z[4] for z in data],ls=':',label='Head pacing goal');ax[2].set_ylabel('Speed (m/s)');ax[2].legend()
        ax[3].step(t,categories,where='post');ax[3].set_yticks([0,1,2,3,4],['Unavailable','Anonymous','Intruder ID','Head ID','Other ID']);ax[3].set_xlabel('Simulated time (s)')
        for a in ax:
            a.axvline(23 if is_native else 22,color='gray',ls='--',lw=.8)
            a.axvspan(65,70,color='green',alpha=.08)
        fig.suptitle(f'{family}: combined profile, configured cruise {speed:g} m/s, first {stage} seed {seed}\n150 m direct radio; head pacing and observation-triggered recovery')
        for suffix in ('png','pdf'):fig.savefig(output/f'{family.lower()}-formation-trace.{suffix}',dpi=180)
        plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True,constrained_layout=True)
    profiles=list(read(python/'plan.json')['cases'])
    for ax,(family,group) in zip(axes,cohorts.items()):
        for i,profile in enumerate(profiles):
            values=[z['tail_spacing_rms_m'] for z in group if z['case']==profile]
            ax.vlines(i,min(values),max(values),color='tab:blue',lw=2)
            ax.scatter([i],[statistics.median(values)],color='tab:blue',s=35)
        ax.set_ylabel(f'{family}\ntail RMS (m)')
        ax.set_ylim(bottom=0)
    axes[-1].set_xticks(range(len(profiles)),[LABELS[p] for p in profiles],rotation=25,ha='right')
    fig.suptitle(f'{stage.title()} final-window spacing: medians and full observed ranges\nDifferent simulator cohorts; no matched baseline attribution')
    for suffix in ('png','pdf'):fig.savefig(output/f'tail-spacing-coverage.{suffix}',dpi=180)
    plt.close(fig)
    lines=['# Formation validation: strict gates and complete ranges','',
        '| Cohort | Profile | Trials | Tail RMS median / max (m) | Tail max error (m) | Settling-onset max delay (s) | Min fresh correct fraction |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for family,group in cohorts.items():
        for profile in profiles:
            g=[z for z in group if z['case']==profile]
            lines.append(f"| {family} | {LABELS[profile]} | {len(g)} | {statistics.median(z['tail_spacing_rms_m'] for z in g):.6f} / {max(z['tail_spacing_rms_m'] for z in g):.6f} | {max(z['tail_spacing_max_abs_m'] for z in g):.6f} | {max(z['settling_delay_2s_s'] for z in g):.2f} | {min(z['tail_correct_fraction'] for z in g):.3f} |")
    lines+=['','Settling delay is the start of a continuous2 s confirmation window after cut-out.',
        'Tail metrics use the final5 s; whole-window correct-target RMS is a different measure.',
        'No causal percentage improvement over earlier32/35 s fixtures is inferred.']
    (output/'validation-tables.md').write_text('\n'.join(lines)+'\n')
    overall={family:dict(episodes=len(g),tail_spacing_rms_max_m=max(z['tail_spacing_rms_m'] for z in g),
        tail_max_abs_error_m=max(z['tail_spacing_max_abs_m'] for z in g),settling_delay_max_s=max(z['settling_delay_2s_s'] for z in g),
        whole_window_conditional_rms_max_m=max(z['spacing_rms_on_correct_target_m'] for z in g),
        maximum_stopped_s=max(z['stopped_ticks']*.05 for z in g),censored_stable_return=sum(z['stable_return_censored'] for z in g)) for family,g in cohorts.items()}
    for family,root,native_flag in [('Python',python,False),('Webots',native,True)]:
        overall[family].update(unconditional_head_errors(root,stage,cohorts[family],native_flag))
    (output/'report.json').write_text(json.dumps(overall,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--python',required=True);p.add_argument('--native',required=True);p.add_argument('--output',required=True)
    p.add_argument('--stage',choices=('development','validation'),default='validation');a=p.parse_args();run(a.python,a.native,a.output,a.stage)
