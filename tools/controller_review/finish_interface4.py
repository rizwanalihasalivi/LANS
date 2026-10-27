"""Evidence report for fixed-delivery, scalar-predictor and recovery diagnosis."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile
ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args();out=args.run
    decision=json.loads((out/'decision.json').read_text());metrics=json.loads((out/'summary.json').read_text())
    timing=json.loads((out/'timing/summary.json').read_text());recovery=json.loads((out/'recovery/summary.json').read_text())
    assert (out/'timing/verification.json').exists() and (out/'recovery/verification.json').exists()
    analysis=json.loads((out/'deep-analysis.json').read_text());episodes=list(csv.DictReader((out/'episodes.csv').open()))
    os.environ.setdefault('MPLCONFIGDIR','/tmp/lans-v4-mpl');os.environ.setdefault('XDG_CACHE_HOME','/tmp/lans-v4-cache')
    Path(os.environ['XDG_CACHE_HOME']).mkdir(exist_ok=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    names=['lqr','negative','positive','student','oldage_ppo','ppo','planner']
    labels=['LQR','Fixed −0.04','Fixed +0.04','Student','Legacy PPO','Fresh PPO','Planner'];base=metrics['lqr'];c=metrics['ppo']
    fig,axes=plt.subplots(1,2,figsize=(11,4.3));fig.subplots_adjust(bottom=.25,wspace=.34)
    colors=['#a7a7a7']*7;colors[5]='#2878ae'
    for ax,key,title in zip(axes,['rmse_m','rate_rms_rad_s'],['Tracking improvement vs LQR (%)','Actuator-rate RMS change vs LQR (%)']):
        values=[100*(1-metrics[n][key]/base[key]) if key=='rmse_m' else 100*(metrics[n][key]/base[key]-1) for n in names]
        ax.bar(range(7),values,color=colors)
        for pair in range(3):
            group=[r for r in episodes if int(r['pair'])==pair]
            bm=np.mean([float(r[key]) for r in group if r['source']=='lqr'])
            dots=[np.mean([float(r[key]) for r in group if r['source']==n]) for n in names]
            dots=[100*(1-v/bm) if key=='rmse_m' else 100*(v/bm-1) for v in dots]
            ax.scatter(np.arange(7)+(pair-1)*.1,dots,s=12,color='black',zorder=3)
        ax.set_xticks(range(7),labels,rotation=35,ha='right');ax.set_title(title,fontsize=10);ax.axhline(0,color='black',lw=.5)
        ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
        if key=='rate_rms_rad_s':ax.axhline(5,color='#ad3b3b',ls='--',label='+5% limit');ax.legend(fontsize=8)
    for suffix in ('png','pdf','svg'):fig.savefig(out/f'development-comparison.{suffix}',dpi=200,bbox_inches='tight')
    plt.close(fig)
    student_gain=100*(1-c['rmse_m']/metrics['student']['rmse_m']);heart=sum(r['deadline_misses'] for r in timing['heartbeat'])
    kernel=timing['kernel'];ratio=kernel['reference']['median_ns']/kernel['scalar']['median_ns']
    status=dict(development_eligible=decision['eligible'],ppo_tracking_gain_vs_lqr_pct=c['gain_vs_lqr_pct'],
        ppo_gain_vs_student_pct=student_gain,planner_headroom_screen_pass=decision['planner_headroom_screen_pass'],
        recovery_functional_pass=recovery['functional_recovery_pass'],recovery_timing_pass=recovery['timing_pass'],
        strict_timing_pass=timing['profiles']['fresh_v4']['observed_timing_pass'],
        reserved='unopened',native_selected_winner_confirmation=False,actual_laptop_validation=False,physical_vehicle_validation=False,
        full_robust_published_reproduction=False,submission_ready=False,new_training_steps=0,
        balanced_vs_lqr_development_pass=c['rmse_m']<=.99*base['rmse_m'] and c['heading_rmse_rad']<=1.05*base['heading_rmse_rad'] and c['rate_rms_rad_s']<=1.05*base['rate_rms_rad_s'])
    lines=['# LANS interface and computation correction report','', '27 October 2026 (Asia/Shanghai). Research evidence update; original campaigns are unchanged.','',
        '## Findings and implemented corrections','',
        'The old actor inference duration, packet age and monitor deadline were different quantities but the legacy authority function penalized packet age steeply. At10ms age, the0.25 cap shrank to0.00458, even if neural inference finished quickly. The old offline nominal case could return a proposal in the same tick, unlike a periodically polled worker. The fixed comparison now enforces at least one10ms delivery interval.',
        'One predefined controller variant separates freshness eligibility from authority: a valid packet younger than50ms may receive up to0.25 authority, with the existing0.05/tick ramp,0.3s residual filter, three-good-control-tick recovery,1s nominal predictor and0.1% predicted-cost improvement test. Invalid/stale packets immediately revoke assistance. This is an empirical performance supervisor, not a formal safety certificate.',
        'The predictor array/BLAS work inside its100-step recurrence was replaced by scalar equations, without fastmath or changed costs. Contracts checked2,000 randomized cost pairs and1,000 closed-loop command/state transitions against the frozen v3 implementation. The old controller remains separately available through scalar_aligned; the new authority variant is fresh_v4.',
        'Fault injection was moved out of the monitor process. Stress helpers signal readiness before measured windows. Timing now records polling, sensing/LQR, feature construction, submission, supervision and software commit separately, and rechecks freshness/deadlines after fallback handling.',
        'The existing20-channel policy also omits the internal residual-filter state. The diagnostic constructed identical policy observations with different valid internal filter states and different next commands. Reachability of that exact pair is not proved: this shows a state-alias risk, not proof that it caused the measured learning gap. Adding a causal history feature requires a new versioned model/normalizer and matched training; old oracle fields were not silently repurposed.','',
        '## Fresh matched development comparison','',
        'Three paired model/noise groups,15/25m/s, two paths, exact left/right mirrors and four service/mismatch conditions. All672 episodes survived. Models are the unchanged original students and frozen v3 PPO endpoints; there are no new PPO training steps. Legacy and fresh PPO use the same actor weights. The planner uses current estimates, actuator, road preview and causal controller history; it never reads true friction, future noise or actual future completion. It is a finite nominal reference, not a global performance bound.','',
        '| Source | Tracking gain vs LQR | Heading change | Rate RMS change | Survival |','|---|---:|---:|---:|---:|']
    for n,label in zip(names,labels):
        m=metrics[n];lines.append(f'| {label} | {m["gain_vs_lqr_pct"]:+.3f}% | {100*(m["heading_rmse_rad"]/base["heading_rmse_rad"]-1):+.2f}% | {100*(m["rate_rms_rad_s"]/base["rate_rms_rad_s"]-1):+.2f}% | {m["survived"]}/{m["episodes"]} |')
    lines+=['','![Matched development results. Dots are three paired groups, not confidence intervals.](development-comparison.png)','',
        f'PPO improves on the same-supervisor student by **{student_gain:.3f}%**, below the frozen1% margin. Every group gain is positive, but the complete screen remains **{decision["eligible"]}**. Failed criteria: '+('; '.join(decision['reasons']) or 'none')+'.',
        'The finite planner also fails the1% student-margin screen. PPO already has better mean lateral RMSE than this particular planner, so distilling it or merely extending training is not justified by this diagnostic. This is not a proof that better learning or planning is impossible. Thresholds, seeds and operating regions were not altered after results; reserved evaluation stays unopened.',
        f'Independent audit replayed all **{decision["transitions"]:,}** executed transitions, rewards, observer/plant states, filter/fusion decisions, policy queries and planner decisions. **{decision["severe_exact_pairs"]}** 100ms/LQR trajectory pairs matched exactly.','',
        '## Timing: faster computation does not establish a deadline guarantee','',
        f'On6,000 identical-input randomized-order cost pairs after warmup, median predictor time changed from{kernel["reference"]["median_ns"]/1000:.3f}µs to{kernel["scalar"]["median_ns"]/1000:.3f}µs, approximately{ratio:.2f}× for this kernel. This is not an overall LANS/PPO inference speedup. All raw samples, including outliers, are retained.',
        f'An independent preallocated native C heartbeat, with no PPO or controller, missed **{heart}/3,000** deadlines on this unisolated host. It is scheduling context with a different workload, not a matched replacement for the controller. Some full-controller misses also contain computational/blocking time; no OS-only attribution is claimed.','',
        '| Controller | Missed original10ms deadlines | Functional checks | Nonzero correction ticks |','|---|---:|---|---:|']
    for name,label in (('scalar_aligned','Equivalent optimized v3'),('fresh_v4','Freshness variant')):
        m=timing['profiles'][name];lines.append(f'| {label} | {m["deadline_misses"]}/{m["ticks"]} | {m["functional_pass"]} | {m["nonzero_correction_ticks"]} |')
    lines+=['','Any miss fails strict observed timing. No targets were rebased, ticks dropped or misses forgiven. A finite zero-miss result would still not prove WCET or guaranteed100Hz. This cloud platform has no demonstrated real-time scheduling/isolation contract. Further timer tuning cannot establish a hardware guarantee.','',
        '## Actual worker stall and recovery','',
        'A separate prespecified test makes the actual worker wait1s for requests observed between2and3s, then restores healthy responses. Original observation times remain unchanged, late packets are rejected, and fresh local LQR continues in the fixed-step plant. Assistance must be exercised both before the stall and after healthy return; it is not forced on when prediction rejects a proposal.','',
        '| Actor seed | Assisted ticks before / after | Delayed packets | Deadline misses | Functional recovery |','|---|---:|---:|---:|---|']
    for e in recovery['episodes']:lines.append(f'| {e["seed"]} | {e["assisted_before"]}/{e["assisted_after"]} | {e["delayed_packets"]} | {e["deadline_misses"]}/{e["ticks"]} | {e["functional_recovery_pass"]} |')
    lines+=['',f'Overall recovery function: **{recovery["functional_recovery_pass"]}**. Recovery timing: **{recovery["timing_pass"]}**. These are separate outcomes.','',
        '## What remains','',
        '- Scientific: at least1% PPO advantage over the same-supervisor student, with all other criteria preserved. The next justified research issue is causal filter-history/decision-time state and credit assignment, not blind training extensions. No new-model success is assumed.',
        '- Execution: demonstrate the unchanged10ms deadline on a defined target system. Run the supplied Python3.10 kit on the actual Windows/macOS laptop; cloud results cannot substitute for that run. Hard timing claims need a suitable execution/OS isolation design and worst-case evidence.',
        '- Confirmation: reserved/unseen paths and selected-controller native Webots confirmation remain conditional on full selection and corresponding-controller timing pass. Historical native interface tests are not validation of this variant.',
        '- Published comparison: the previous Wabersich–Zeilinger Eq5/Algorithm1 nominal specialization is retained. The supplied paper Algorithm2 additionally needs validated model-error/confidence bounds and a terminal safe set/controller under its assumptions. These are not established for this noisy nonlinear plant; relabeling the nominal comparator as a full robust reproduction would be incorrect. The five supplied-source reference entries are verified; broader bibliography/prior-art verification remains incomplete.',
        '- Physical: actual sensors, communication and actuator response require connected hardware. Software-plant state advances by10ms per iteration; survival does not establish continuous physical safety during host stalls.',
        '- Publication: the evidence draft is updated, but full novelty, formal safety and submission readiness remain unestablished. No49× speedup, energy, blind-distance or global stability claim is restored.','',
        'The downloadable kit is a software-plant research diagnostic with actual frozen PPO actors, not vehicle deployment approval. Source/model hashes, protocols, raw traces and verifiers accompany the report. Existing failed studies remain unchanged.']
    # Narrative formatting only; do not alter identifiers or mathematics in code spans.
    import re
    doc='\n'.join(lines)+'\n';doc=re.sub(r'(?<=[A-UW-Za-uw-z])(?=\d)',' ',doc);doc=re.sub(r'(?<=\d)(?=[A-UW-Za-uw-zµ])',' ',doc)
    (out/'final-update.md').write_text(doc);(out/'completion-status.json').write_text(json.dumps(status,indent=2)+'\n')
    for suffix in ('docx','pdf'):
        cmd=['pandoc',str(out/'final-update.md'),'--resource-path='+str(out),'-o',str(out/f'final-update.{suffix}')]
        if suffix=='pdf':cmd+=['--pdf-engine=xelatex','-V','mainfont=DejaVu Serif','-V','geometry:margin=22mm','-V','fontsize=10pt','-V','papersize=a4']
        subprocess.run(cmd,check=True,env=os.environ)
    with zipfile.ZipFile(out/'LANS_Interface_Reports.zip','w',zipfile.ZIP_DEFLATED) as z:
        for n in ('final-update.md','final-update.docx','final-update.pdf','development-comparison.png','development-comparison.svg','development-comparison.pdf','completion-status.json','summary.json','decision.json','deep-analysis.json','episodes.csv'):
            z.write(out/n,n)
    qa={}
    for f in out.glob('*.zip'):
        with zipfile.ZipFile(f) as z:assert z.testzip() is None
        qa[f.name]=hashlib.sha256(f.read_bytes()).hexdigest()
    (out/'artifact-quality.json').write_text(json.dumps(dict(archive_crc_pass=True,sha256=qa,actual_laptop_execution=False),indent=2)+'\n')
    print(json.dumps(status,indent=2))


if __name__=='__main__':main()
