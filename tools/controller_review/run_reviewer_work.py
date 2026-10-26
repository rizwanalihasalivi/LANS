"""Single entry point: frozen campaign, independent audits, portable kit and reports."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'docs/research/reviewer-causal-v1')
    p.add_argument('--publish',action='store_true')
    args=p.parse_args();run=args.output.resolve()
    run.mkdir(parents=True,exist_ok=True)
    update_template=ROOT/'tools/controller_review/templates/opening-report-research-update.md'
    if not (run/'opening-report-research-update.md').exists():
        shutil.copy2(update_template,run/'opening-report-research-update.md')
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
        MPLCONFIGDIR='/tmp/lans-campaign-mpl',NUMBA_CACHE_DIR='/tmp/lans-campaign-numba')
    def call(command,log=None):
        if log:
            with log.open('w') as handle:subprocess.run(command,cwd=ROOT,env=env,stdout=handle,stderr=subprocess.STDOUT,check=True)
        else:subprocess.run(command,cwd=ROOT,env=env,check=True)
    def publish(label):
        if not args.publish:return
        paths=[str(run.relative_to(ROOT)),'README.md','docs/opening-report/README.md','tools/reviewer_campaign/README.md',
            'tools/laptop/export_bundle.py','tools/laptop/verify_export.py']
        paths += [str(Path(__file__).relative_to(ROOT))]
        paths += ['tools/controller_review/templates']
        paths += [f'tools/controller_review/{name}.py' for name in (
            'summarize_campaign_uncertainty','audit_campaign_linearization',
            'benchmark_campaign_actors','replay_campaign_proposals','realtime_campaign_partition')]
        call(['git','add','-f',*paths]);call(['git','diff','--cached','--check'])
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:
            call(['git','commit','-m',label])
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
        call(['git','-c',"credential.helper=!gh auth git-credential",'push','origin',branch])
    command=[sys.executable,str(ROOT/'tools/reviewer_campaign/run.py'),'--output',str(run)]
    if args.publish:command.append('--publish')
    call(command)
    post_sources=[Path(__file__),ROOT/'tools/laptop/export_bundle.py',ROOT/'tools/laptop/verify_export.py']
    post_sources += [ROOT/f'tools/controller_review/{name}.py' for name in (
        'summarize_campaign_uncertainty','audit_campaign_linearization','benchmark_campaign_actors',
        'replay_campaign_proposals','realtime_campaign_partition')]
    post_sources += list((ROOT/'tools/controller_review/templates').glob('*.md'))
    post_hashes={}
    for file in post_sources:
        relative=file.relative_to(ROOT);target=run/'postprocessing-source'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
        post_hashes[str(relative)]=hashlib.sha256(file.read_bytes()).hexdigest()
    (run/'postprocessing-manifest.json').write_text(json.dumps(post_hashes,indent=2)+'\n')
    publish('research: freeze resource-partition timing diagnosis and independent audits')
    if not (run/'partition-timing/summary.json').exists():
        call([sys.executable,str(ROOT/'tools/controller_review/realtime_campaign_partition.py'),
              '--models',str(run/'export'),'--output',str(run/'partition-timing')],run/'partition-timing.log')
        call([sys.executable,str(ROOT/'tools/controller_review/verify_realtime_optimized.py'),
              '--run',str(run/'partition-timing'),'--model-root',str(run/'export')],run/'partition-timing-verification.log')
    publish('research: diagnose local controller timing with test-generated CPU load partitioned')
    call([sys.executable,str(ROOT/'tools/controller_review/summarize_campaign_uncertainty.py'),
          '--grid',str(run/'development')],run/'uncertainty.log')
    if not (run/'development/proposal-reward-replay.json').exists():
        call([sys.executable,str(ROOT/'tools/controller_review/replay_campaign_proposals.py'),
              '--run',str(run)],run/'proposal-reward-replay.log')
    call([sys.executable,str(ROOT/'tools/controller_review/audit_campaign_linearization.py'),
          '--output',str(run/'nominal-linearization.json')],run/'linearization.log')
    publish('research: independently replay causal PPO proposals rewards and seed-block metrics')
    # Timing is deliberately after all native/stress jobs, with no competing
    # campaign jobs; compare exported actors through the same CPU wrapper.
    if not (run/'matched-actor-timing/summary.json').exists():
        call([sys.executable,str(ROOT/'tools/controller_review/benchmark_campaign_actors.py'),
              '--run',str(run)],run/'matched-actor-timing.log')
    kit=run/'laptop-kit'
    if not (kit/'manifest.json').exists():
        call([sys.executable,str(ROOT/'tools/laptop/export_bundle.py'),
              '--model-root',str(run/'export'),'--output',str(kit)],run/'laptop-kit-export.log')
    call([sys.executable,str(ROOT/'tools/laptop/verify_export.py'),'--model-root',str(run/'export'),
          '--kit',str(kit),'--output',str(run/'laptop-export-verification.json')],run/'laptop-export-verification.log')
    shutil.copy2(ROOT/'tools/laptop/RUN_MACOS.command',kit/'RUN_MACOS.command')
    (kit/'README.md').write_text('''# Causal PPO actor laptop timing kit

These are exact exports of the new25k PPO actors, not the earlier supervised-only
student. Seed labels701/802/903 map to PPO seeds2701/2802/2903.

Windows64-bit Python3.10: double-click RUN_PYTHON310.cmd. The launcher uses a local
venv, NumPy2.2.6 and native high-resolution Windows timers.

macOS: use RUN_MACOS.command (Python3.11+). If Finder blocks execution, run
`bash RUN_MACOS.command` from Terminal in this folder.4GB RAM is sufficient for the
small NumPy-only model; actual Mac execution is not verified here.

This kit measures actor computation, Pipe IPC and monitor timing on recorded
observations. It does NOT run the observer, LQR, new supervisor, vehicle plant,
Webots, sensors or actuator. Monitor misses are not full-controller deadlines.
Return summary.json and all packet/tick CSVs. Target Windows/macOS results remain
pending until the user runs the kit. No device/product IDs are collected.
''')
    manifest=json.loads((kit/'manifest.json').read_text())
    manifest['policy_origin']='Exact25k causal PPO actor; not supervised-only student'
    manifest['sha256']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in kit.iterdir()
                        if f.is_file() and f.name!='manifest.json'}
    (kit/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    archive=run/'LANS_Causal_PPO_Laptop_Kit.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for file in sorted(kit.iterdir()):
            if file.is_file():z.write(file,'LANS_Causal_PPO_Laptop_Kit/'+file.name)
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    (run/'laptop-kit-download.json').write_text(json.dumps(dict(bytes=archive.stat().st_size,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),actual_windows_mac_execution_verified=False),indent=2)+'\n')
    summary=json.loads((run/'development/summary.json').read_text())
    decision=json.loads((run/'development/decision.json').read_text())
    worker=json.loads((run/'real-worker/summary.json').read_text())
    native=json.loads((run/'native/verification.json').read_text())
    partition=json.loads((run/'partition-timing/summary.json').read_text())
    import csv
    import gzip
    import statistics
    categories={'already_late_at_release':0,'processing_ge10ms_after_timely_release':0,
                'combined_release_and_processing':0}
    for file in (run/'real-worker').glob('*-ticks.csv.gz'):
        with gzip.open(file,'rt') as handle:
            for row in csv.DictReader(handle):
                deadline=int(row['target_ns'])+10_000_000
                release=int(row['release_ns']);apply=int(row['apply_ns'])
                if apply<=deadline:continue
                if release>=deadline:categories['already_late_at_release']+=1
                elif apply-release>=10_000_000:categories['processing_ge10ms_after_timely_release']+=1
                else:categories['combined_release_and_processing']+=1
    assert sum(categories.values())==sum(e['deadline_misses'] for e in worker['episodes'])
    pacing=[]
    for file in (run/'native').glob('*/telemetry.csv'):
        with file.open() as handle:telemetry=list(csv.DictReader(handle))
        compute=[float(r['control_wall_ms']) for r in telemetry]
        intervals=[(int(b['wall_release_ns'])-int(a['wall_release_ns']))/1e6
                   for a,b in zip(telemetry,telemetry[1:])]
        pacing.append(dict(case=file.parent.name,median_control_wall_ms=statistics.median(compute),
            median_release_interval_ms=statistics.median(intervals),
            deadline_misses=sum(int(r['deadline_miss']) for r in telemetry),ticks=len(telemetry)))
    (run/'deadline-diagnosis.json').write_text(json.dumps(dict(real_worker_miss_categories=categories,
        native_compute_and_pacing=pacing,limitations='Descriptive timing decomposition, not causal attribution of OS versus prior-loop work. Native stepping/actuation IPC is outside control-compute duration but affects release pacing.'),indent=2)+'\n')
    status=json.loads((run/'status.json').read_text())
    status['resource_partition_diagnosis']=dict(functional_pass=partition['functional_pass'],
        observed_timing_pass=partition['timing_pass'],original_contested_core_failures_retained=True,
        guaranteed_realtime=False)
    status['external']['laptop_rerun']='New causal PPO Windows3.10/macOS actor kit available; actual target runs pending'
    (run/'status.json').write_text(json.dumps(status,indent=2)+'\n')
    matrix=['# Completion and outcome matrix','',
        'Completed execution is different from passing a research hypothesis. This campaign does not close the entire thesis.','',
        '| Work | Status | Evidence / remaining limitation |','|---|---|---|',
        '| Causal interface and residual supervisor | Implemented/tested |7contracts; no pending-result/forecast inputs |',
        '| Bounded PPO training | Completed |6x25k additional steps; pretraining extra |',
        '|864-episode mirrored development | Completed; improvement screen FAILED |See development/decision.json; no promotion |',
        '| Reserved held-out confirmation | Unopened after failed screen |No test-set tuning |',
        '| Actual worker/1s delay/crash/contention | Functional pass; strict timing FAILED |Original contested-core misses retained; zero learned authority in original real-worker grid |',
        f'| Resource partition diagnosis | Functional:{partition["functional_pass"]}; observed timing:{partition["timing_pass"]} |Generated load moved off local core; no OS/WCET guarantee |',
        f'| Native Webots PPO interface | Interface:{native["native_interface_verification_pass"]}; wall timing:{native["strict_native_wall_timing_pass"]} |One PPO seed; six interface cases; no vehicle claim |',
        '| Actor/reward replay and seed-block statistics | Completed if verification records pass |No ticks/mirrors counted as independent seeds |',
        '| Fair actor timing | Measured through identical CPU wrapper |Actor-only; not full LANS timing or GPU comparison |',
        '| Portable Windows/macOS kit | Export/parity verified on Linux |Actual laptop execution pending |',
        '| Published-method reproduction / systematic literature | Incomplete |Five supplied primary texts reviewed; external access blocked |',
        '| Full original reward/freshness ablation | Incomplete |New controlled comparators do not reproduce every original claim |',
        '| Physical validation / global safety | Not established |Requires hardware and additional analysis |',
        '| Paper/opening report/reviewer response | Evidence drafts exported |Not submission-ready; bibliography and scientific gaps remain |']
    (run/'completion-matrix.md').write_text('\n'.join(matrix)+'\n')
    table=['| Method | Lateral RMSE (m) | Gain versus LQR | Heading RMSE (rad) | Steering-rate RMS (rad/s) | Survival |',
           '|---|---:|---:|---:|---:|---:|']
    for name,m in summary.items():
        table.append(f'| {name} | {m["rmse_m"]:.6f} | {m["gain_vs_lqr_pct"]:.3f}% | {m["heading_rmse_rad"]:.6f} | {m["steering_rate_rms_rad_s"]:.6f} | {m["survived"]}/{m["episodes"]} |')
    ticks=sum(e['ticks'] for e in worker['episodes']);misses=sum(e['deadline_misses'] for e in worker['episodes'])
    results='\n'.join(table)+'\n\n'
    results+=f'Development eligibility: **{decision["eligible"]}**. '+ '; '.join(decision['reasons'])+'.\n\n'
    results+=f'Actual-worker campaign: {ticks} ticks, {misses} deadline misses ({100*misses/ticks:.3f}%), functional pass:{worker["functional_pass"]}. '
    results+=f'Learned authority was active on {sum(e["active_ticks"] for e in worker["episodes"])} ticks; this provides no real-worker learning-benefit evidence.\n\n'
    results+=f'Native interface verification:{native["native_interface_verification_pass"]}; observed native wall timing:{native["strict_native_wall_timing_pass"]}. '
    results+=f'Resource-partition diagnostic functional pass:{partition["functional_pass"]}; observed timing pass:{partition["timing_pass"]}. '
    results+='Partitioned generated load does not exclude host OS activity, replace original failures or establish WCET.\n\n'
    results+='See the frozen protocol, raw traces, independent audits and completion-matrix.md. Reserved confirmation remains unopened when development fails.\n'
    gain=summary['latency_gain'];base=summary['lqr']
    gain_text=(f'The manuscript-inspired latency-gain comparator reduces lateral RMSE by {gain["gain_vs_lqr_pct"]:.3f}%, '
        f'but increases heading RMSE by {100*(gain["heading_rmse_rad"]/base["heading_rmse_rad"]-1):.3f}% '
        f'and steering-rate RMS by {100*(gain["steering_rate_rms_rad_s"]/base["steering_rate_rms_rad_s"]-1):.3f}%. '
        'This exceeds the predefined5% smoothness tradeoff limit. Fixed authority loses one episode under20ms service. '
        'The simple gain is a promising descriptive tracking result, not a selected balanced winner. '
        'Same-gain student/constant controls and separate native/timing validation would be needed to attribute its benefit to additional PPO learning. '
        'The proposed predictive supervisor did not retain that tracking gain; no post-result gate tuning or reserved-test opening was performed.\n')
    results+='\n'+gain_text
    core=(ROOT/'tools/controller_review/templates/opening-report-revised-core.md').read_text()
    (run/'opening-report-revised-draft.md').write_text(core.replace('{{CURRENT_RESULTS}}',results))
    (run/'interpretation.md').write_text('# Campaign interpretation\n\n'+results+'\nSee deadline-diagnosis.json for observed scheduling/processing decomposition; no causal OS/WCET guarantee is inferred.\n')
    draft=run/'revised-manuscript-draft.md'
    text=draft.read_text().partition('\n## Additional interpretation')[0]
    draft.write_text(text+'\n## Additional interpretation\n\n'+gain_text)
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        with (run/'development/episodes.csv').open() as handle:episode_rows=list(csv.DictReader(handle))
        names=list(summary)
        metrics=[('penalized_lateral_rmse_m','Lateral RMSE (m)'),
                 ('heading_rmse_rad','Heading RMSE (rad)'),
                 ('steering_rate_rms_rad_s','Steering-rate RMS (rad/s)')]
        fig,axes=plt.subplots(1,3,figsize=(15,5.5))
        for axis,(field,label) in zip(axes,metrics):
            means=[];errors=[]
            for name in names:
                blocks=[statistics.mean(float(r[field]) for r in episode_rows
                        if r['method']==name and int(r['pair'])==pair) for pair in range(3)]
                means.append(statistics.mean(blocks));errors.append(statistics.stdev(blocks))
            axis.bar(range(len(names)),means,yerr=errors,capsize=3,color=['#555555' if n=='lqr' else '#3976a8' for n in names])
            axis.set_xticks(range(len(names)));axis.set_xticklabels(names,rotation=65,ha='right',fontsize=8)
            axis.set_ylabel(label);axis.grid(axis='y',alpha=.2)
        fig.suptitle('Causal residual development: mean and SD across three seed blocks; lower is better')
        fig.tight_layout();fig.savefig(run/'development-comparison.png',dpi=180)
        fig.savefig(run/'development-comparison.pdf');plt.close(fig)
        draft=run/'revised-manuscript-draft.md'
        text=draft.read_text().partition('\n## Development figure')[0]
        draft.write_text(text+'\n## Development figure\n\n![Development metrics; error bars are seed-block SD, not independent-tick uncertainty.](development-comparison.png)\n')
    except ImportError:
        (run/'plot-unavailable.txt').write_text('Matplotlib missing; raw tables preserved.\n')
    update=run/'opening-report-research-update.md'
    if update.exists():
        text=update.read_text().partition('\n## Current campaign outcome')[0]
        text+='\n## Current campaign outcome\n\n'
        text+=f'Development:864 episodes; eligible design:{decision["eligible"]}. '
        text+=f'Fine-tuned PPO reduction versus LQR:{summary["finetune"]["gain_vs_lqr_pct"]:.4f}%. '
        text+=f'Actual-worker functional pass:{worker["functional_pass"]}; observed timing pass:{worker["timing_pass"]}. '
        text+=f'Native interface pass:{native["native_interface_verification_pass"]}; native observed wall timing pass:{native["strict_native_wall_timing_pass"]}.\n\n'
        text+='These outcomes do not validate original manuscript speed/energy/safety claims. '
        text+='See development/README.md, reviewer-response.md and status.json for tradeoffs and remaining work.\n'
        update.write_text(text)
    for source in ('revised-manuscript-draft.md','opening-report-revised-draft.md','opening-report-research-update.md','reviewer-response.md'):
        file=run/source
        if not file.exists():continue
        if shutil.which('pandoc'):
            call(['pandoc',str(file),'--from=markdown+tex_math_single_backslash','--resource-path',str(run),'-o',str(file.with_suffix('.docx'))])
            if shutil.which('xelatex'):
                call(['pandoc',str(file),'--from=markdown+tex_math_single_backslash','--resource-path',str(run),'--pdf-engine=xelatex','-V','mainfont=DejaVu Serif',
                      '-V','geometry:margin=22mm','-V','fontsize=10pt','-o',str(file.with_suffix('.pdf'))],
                     run/(file.stem+'-pdf.log'))
    if (run/'docx-unavailable.txt').exists():
        (run/'docx-unavailable.txt').write_text('Initial python-docx unavailable; formatted DOCX/PDF subsequently exported with Pandoc/XeLaTeX.\n')
    report_zip=run/'LANS_Reviewer_Reports.zip'
    with zipfile.ZipFile(report_zip,'w',zipfile.ZIP_DEFLATED) as z:
        for stem in ('revised-manuscript-draft','opening-report-revised-draft','opening-report-research-update','reviewer-response'):
            for extension in ('.md','.docx','.pdf'):
                file=run/(stem+extension)
                if file.exists():z.write(file,file.name)
        for file in (run/'status.json',run/'completion-matrix.md',run/'interpretation.md',run/'development/README.md',run/'matched-actor-timing/summary.json'):
            if file.exists():z.write(file,str(file.relative_to(run)))
    publish('research: publish matched actor timing portable PPO kit and corrected report drafts')
    print('Completed reproducible software campaign and report package; unresolved external/theoretical items remain in status.json.',flush=True)


if __name__=='__main__':main()
