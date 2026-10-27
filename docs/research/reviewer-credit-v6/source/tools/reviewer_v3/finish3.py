import argparse
import csv
import gzip
import json
from pathlib import Path
import subprocess
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args();out=args.run
    decision=json.loads((out/'decision.json').read_text());metrics=json.loads((out/'summary.json').read_text())
    lines=[(out/'README.md').read_text(),'','## Observed timing and scheduling diagnosis','',
        'Timing is deliberately run after training/development have finished. It uses the old fixed age_filtered diagnostic and old25k PPO actors, not the new controller. Thus it isolates scheduling choices; a positive outcome cannot certify the new controller. Both profiles use the two highest available CPUs, nice19 workers/stress and original10ms deadlines. The dedicated-spin profile burns one CPU and is not the laptop default.','',
        '| Profile | Missed deadlines | Functional/raw replay | Actual nonzero correction ticks |', '|---|---:|---|---:|']
    timing={};diagnostics=[]
    for name in ('absolute_100us','dedicated_spin'):
        folder=out/'timing'/name;s=json.loads((folder/'summary.json').read_text());v=json.loads((folder/'verification.json').read_text())
        assert v['raw_timestamp_and_model_replay_checks_pass'];timing[name]=s
        lines.append(f'| {name} | {s["deadline_misses"]}/{s["ticks"]} | {s["functional_pass"]} | {sum(e["nonzero_correction_ticks"] for e in s["episodes"])} |')
    for parent,names in ((ROOT/'docs/research/reviewer-followup-v2/timing',('sleep','absolute')),(out/'timing',('absolute_100us','dedicated_spin'))):
        for name in names:
            folder=parent/name;rows=[]
            for f in folder.glob('*-ticks.csv.gz'):
                with gzip.open(f,'rt') as h:rows+=list(csv.DictReader(h))
            missed=[r for r in rows if r['deadline_miss']=='True']
            quant=lambda key:dict(p99=float(np.quantile([float(r[key]) for r in rows],.99)),maximum=max(float(r[key]) for r in rows))
            diagnostics.append(dict(study=parent.parent.name,profile=name,ticks=len(rows),misses=len(missed),
                already_late_at_release=sum(float(r['release_lateness_ms'])>=10 for r in missed),
                wall_control_over10ms=sum(float(r['control_ms'])>=10 for r in missed),
                thread_cpu_control_over10ms=sum(float(r['control_cpu_ms'])>=10 for r in missed),
                release_lateness_ms=quant('release_lateness_ms'),wall_control_ms=quant('control_ms'),thread_cpu_control_ms=quant('control_cpu_ms')))
    (out/'timing-diagnosis.json').write_text(json.dumps(diagnostics,indent=2)+'\n')
    lines+=['','| Study/profile | Misses | Already >=10ms late at release | Wall control >=10ms | Thread CPU control >=10ms |', '|---|---:|---:|---:|---:|']
    for d in diagnostics:lines.append(f'| {d["study"]}/{d["profile"]} | {d["misses"]} | {d["already_late_at_release"]} | {d["wall_control_over10ms"]} | {d["thread_cpu_control_over10ms"]} |')
    lines+=['',
        'Categories overlap. Elapsed control time minus thread CPU time includes descheduling, blocking, IPC and measurement-boundary differences; it is not an exact OS-only attribution. Cgroup quota, host tasks and preemption remain uncontrolled. Any miss fails strict observed timing. Finite zero misses would still not establish WCET, PREEMPT_RT behaviour, physical end-to-end latency or guaranteed100Hz.','',
        '## Work completed and outstanding','',
        '- Completed: one prespecified execution-aligned controller/reward study, all pilot/futility endpoints, matched same-supervisor controls, independent raw reward/filter/fusion/model replay, and isolated-from-training scheduling experiment. Failed outcomes remain published.',
        f'- New learned candidate development eligibility: **{decision["eligible"]}**. See decision.json for every criterion.',
        '- Reserved/unseen tests remain unopened unless eligibility and a separately frozen corresponding-controller timing requirement both pass. Native selected-winner confirmation follows that gate; historical native interface tests are not new-controller validation.',
        '- The existing Python3.10 full-controller kit remains a verified old-controller development diagnostic. No new-controller laptop deployment is claimed. Actual Windows/macOS execution requires the user laptop; physical sensors/communication/actuators require connected hardware.',
        '- The prior nominal Eq5/Algorithm1 safety-filter specialization remains the scoped published comparator. Reproduction of the full robust algorithm/authors code and complete publisher metadata remain unverified; no literature-superiority claim.',
        '- Original reviewer corrections remain: no exogenous latency reward, real queued worker unavailability, fresh LQR distinct from delayed PPO, no49x speedup, no fabricated ablation frequency, no global stability proof, no energy/blind-distance advantage, full disclosure of negative results and limited generalization.',
        '- This is an evidence report, not an accepted-performance or submission-ready declaration. Additional variants require a new frozen study; thresholds are never changed to relabel a failure.','',
        'Reproduce/resume: `python tools/reviewer_v3/run3.py --publish`. Protocol, frozen sources/model hashes, training progress, complete raw traces and decision files accompany this report.']
    text='\n'.join(lines)+'\n';(out/'final-update.md').write_text(text)
    status=dict(development_eligible=decision['eligible'],diagnostic_timing_pass={n:s['timing_pass'] for n,s in timing.items()},
        corresponding_new_controller_timing_validated=False,reserved='unopened',actual_laptop_validation=False,
        physical_validation=False,complete_robust_published_reproduction=False,submission_ready=False)
    (out/'completion-status.json').write_text(json.dumps(status,indent=2)+'\n')
    for suffix in ('docx','pdf'):
        cmd=['pandoc',str(out/'final-update.md'),'-o',str(out/f'final-update.{suffix}')]
        if suffix=='pdf':cmd+=['--pdf-engine=xelatex','-V','mainfont=DejaVu Serif','-V','geometry:margin=22mm']
        subprocess.run(cmd,check=True)
    with zipfile.ZipFile(out/'LANS_Aligned_Reports.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ('final-update.md','final-update.docx','final-update.pdf','completion-status.json','summary.json','decision.json','timing-diagnosis.json','episodes.csv'):
            z.write(out/name,name)
    print(json.dumps(status,indent=2))


if __name__=='__main__':main()
