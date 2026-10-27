"""Preserve the finite recovery/expiry comparison, including failed targets."""
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
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();out=a.run
    load=lambda n:json.loads((out/n).read_text())
    decision=load('decision.json');summary=load('summary.json');timing=load('timing/summary.json');tv=load('timing/verification.json');smoke=load('kit-smoke/summary.json');dynamic=load('dynamic-recovery/summary.json')
    assert decision['source_model_hashes_verified'] and tv['source_model_hashes_verified']
    assert (out/'dynamic-recovery/verification.json').exists()
    rows=list(csv.DictReader((out/'episodes.csv').open()));base=summary['lqr'];gains={arm:100*(1-summary[arm]['rmse_m']/summary[student]['rmse_m']) for arm,student in [('ppo_raw','student_raw'),('ppo_comp','student_comp')]}
    missed=[]
    for f in (out/'timing').glob('*/seed-*/*-ticks.csv'):
        for r in csv.DictReader(f.open()):
            if r['deadline_miss']=='True':missed.append(dict(trace=str(f.relative_to(out)),tick=int(r['tick']),release_lateness_ms=int(r['release_lateness_ns'])/1e6,
                processing_ms=int(r['control_ns'])/1e6,thread_cpu_ms=int(r['control_cpu_ns'])/1e6,sensing_lqr_ms=int(r['sensing_lqr_ns'])/1e6,feature_ms=int(r['feature_ns'])/1e6,budget_skipped=r['decision_skipped']=='True'))
    (out/'deadline-attribution.json').write_text(json.dumps(missed,indent=2)+'\n')
    activity={}
    for scenario in ('nominal','tire','delay20','delay40','delay100'):
        activity[scenario]={source:sum(int(r['active_ticks']) for r in rows if r['source']==source and r['scenario']==scenario) for source in summary}
    (out/'activity-by-scenario.json').write_text(json.dumps(activity,indent=2)+'\n')
    lines=['# LANS bounded recovery, packet-expiry prediction and deadline guard','',
        '27 October 2026 (Asia/Shanghai). Verified experimental revision; failed scientific and timing criteria remain failures.','',
        '## Implemented corrections','',
        'The previous40ms case could not finish three control-tick recovery checks before its packet became stale. The revised supervisor requires three DISTINCT valid, fresh and predictively beneficial proposal sequences. Reusing one held packet cannot manufacture three recovery confirmations. Internal filter/evidence memory may survive a short stale gap only within50ms of the last distinct qualifying decision. Every stale tick immediately has ZERO learned authority. Missing/invalid inputs, cost rejection, evidence expiry and local budget failure reset recovery. The original50ms stale cutoff is unchanged.',
        'The50ms liveness limit bounds each gap between distinct qualifying decisions, not the total span of all three responses. Preserved filter state is internal controller history, not an active stale command. A fresh qualifying packet and current-state predictive check remain necessary for nonzero weight; no old observation is retimestamped or resubmitted as fresh.',
        'The nominal predictor now applies assistance only over the CURRENT packet’s remaining eligible control ticks, then follows LQR continuation. It no longer forecasts that assistance persists for the full1second without another valid packet. Baseline and candidate use the same current state, actuator dynamics, path preview,100-step horizon, cost weights and margin. Full100step and zero-assistance numerical limits match the previous kernel. Recovery and expiry-continuation were revised jointly; this study does not isolate their individual performance effects.',
        r'$$n_t=\max\!\left(0,\left\lceil\frac{a_{\max}-a_t}{h}\right\rceil\right),\qquad a_{\max}=0.05\ \mathrm{s},\quad h=0.01\ \mathrm{s}.$$',
        'The experimental v7 policy-input forecast is unchanged: completed-response history only, no future completion/service information,40ms horizon cap, latest-state admission and original timestamps. Residual filtering, cap0.25, ramp0.05, steering limits and physical reward are unchanged. No new training or hyperparameter search occurred. Frozen policies were not trained for this revised gate; input/controller distribution shift is a remaining limitation.',
        'A separate optional deadline guard suppresses new forecast/query work near the original deadline and skips predictive admission when less than1ms remains. It uses prepared LQR fallback and resets learned recovery. The reserve is a predeclared heuristic, not WCET proof; mandatory sensing/LQR still runs, and original deadlines never shift. A cycle already late remains a miss.','',
        '## Fresh full development matrix','',
        f'Eight mechanism contracts pass. NumPy student exports match Torch classes on2,000 test vectors per actor, and PPO exports retain the original weight hashes. The seven methods share the revised supervisor, sensing, noise, actuator, delay and available-information rules. Raw/compensated PPO are compared with matching raw/compensated students and both fixed corrections. The frozen grid covers15/25m/s, two known paths, mirrored directions, three actor/noise groups and nominal/tire/20ms/40ms/100ms cases.',
        f'All **{decision["episodes"]} episodes survived**. Exact replay checked **{decision["transitions"]:,} transitions**, **{decision["submitted_actor_decisions"]:,} actor decisions**, all raw/forecast inputs, history, physical trajectories, gate decisions, rewards and metrics. All **{decision["exact_100ms_lqr_pairs"]}** severe-delay/LQR trajectory pairs match exactly. Typed NumPy traces preserve values and avoid lossy CSV parsing.','',
        '| Controller | Tracking gain vs LQR | Heading change | Rate RMS change | Survival |','|---|---:|---:|---:|---:|']
    for source,m in summary.items():lines.append(f'| {source} | {m["gain_vs_lqr_pct"]:+.3f}% | {100*(m["heading_rmse_rad"]/base["heading_rmse_rad"]-1):+.3f}% | {100*(m["rate_rms_rad_s"]/base["rate_rms_rad_s"]-1):+.3f}% | {m["survived"]}/{m["episodes"]} |')
    lines+=['',f'PPO student-relative gains: raw **{gains["ppo_raw"]:+.3f}%**, compensated **{gains["ppo_comp"]:+.3f}%**. Neither meets the unchanged1% requirement; the compensated arm also misses1% over LQR and has a negative paired group. Selected controller: **{decision["selected"]}**. All exact failed criteria are retained in decision.json.',
        f'At40ms, raw PPO has **{activity["delay40"]["ppo_raw"]}** active ticks and compensated PPO **{activity["delay40"]["ppo_comp"]}**. The structural recovery blockage is removed, while every stale tick remains baseline-only. Actual admission still requires predicted benefit; the favorable-cost unit test alone is not a performance claim.',
        'These are new controller rules and a fresh expanded development grid. Do not interpret their aggregate difference from older2–3% campaigns as a paired causal effect of one change. The earlier measured trajectories remain preserved; no prior failure or success is overwritten. The current result does not establish PPO superiority and does not justify further unplanned tuning until a score passes.','',
        '## Original10ms timing and environment','',
        '| Guard | Controller ticks | Original deadline misses | Functional fallback | Strict observed timing |','|---|---:|---:|---|---|']
    for guard,m in timing['profiles'].items():lines.append(f'| {guard} | {m["ticks"]} | {m["misses"]} | {m["functional_pass"]} | {m["observed_timing_pass"]} |')
    lines+=['',f'Native C heartbeat: **{sum(r["deadline_misses"] for r in timing["heartbeat"])}/{sum(r["ticks"] for r in timing["heartbeat"])} misses**. The randomized per-seed guard order, full warmup, pinned control/helper CPUs and lower helper priority were fixed before outcomes. Timing ran after offline research jobs exited. Replay verified{tv["controller_ticks"]} controller ticks,{tv["heartbeat_ticks"]} heartbeat ticks and{tv["query_vectors_verified"]} recorded query vectors;{tv["budget_decisions_skipped"]} predictive decisions were skipped by the guard. Raw queries that never returned lack an independently recorded sent vector; this limitation is stated rather than hidden.',
        'The guard-on miss occurred after roughly9.425ms release lateness followed by roughly9.329ms mandatory sensing/LQR work. Optional work was skipped, but the lost budget could not be recovered. This demonstrates the remaining sensing/scheduling requirement. Original timestamps and stale/late authority rejection pass; strict10ms execution still fails.',
        'Two versus one misses is a finite A/B observation, not statistically established superiority or a hard-real-time guarantee. Earlier657/7,500 and164/1,500 campaigns used different revisions/windows/environments. Their apparent difference cannot be attributed solely to this guard. The current cgroup reports zero throttling during the recorded interval; post-campaign platform metadata is preserved and is not backfilled into historical runs. LQR, observer and supervisor still share the local process; software commit timestamps are not actuator timestamps.',
        f'A separate fixed dynamic-recovery diagnostic exercised actual one-second PPO-worker waits for requests observed in [2,3)seconds, followed by healthy responses. All three seeds had nonzero assistance before and after the stall, actual delayed packets were rejected, and fallback checks passed: functional recovery **{dynamic["functional_recovery_pass"]}**, **{dynamic["deadline_misses"]}/{dynamic["ticks"]} misses** in this separate8second-per-seed run. This does not erase the guard-A/B miss. The dynamic audit verifies packet timing, actor outputs and physical trajectories; complete query/gate-memory replay is recorded separately for the15,000tick A/B campaign.',
        f'The clean Python3.10 kit smoke recorded{smoke["ticks"]} ticks,{smoke["deadline_misses"]} misses and functional fallback {smoke["functional_fallback_pass"]}. It is a packaging diagnostic, not actual laptop, Webots or physical validation. The kit runs all three actors across five13second cases, verifies raw outputs automatically and creates laptop-results/Results.zip.','',
        '## What remains and why','',
        '- Scientific selection remains FAILED. A new matched policy/objective study would require a justified finite protocol and evidence of additional headroom; another training run cannot be promised to beat a strong student.',
        '- Strict10ms response remains FAILED. Target-specific bounded sensing/control execution and scheduling validation are needed. The user laptop has not been remotely executed; run the extracted RUN_WINDOWS.cmd or `bash RUN_MAC.command` and return laptop-results/Results.zip.',
        '- Reserved/unseen-path and corresponding-controller native Webots confirmation remain UNOPENED because the promotion gates fail. Older native interface checks are not confirmation of this revision.',
        '- Full matched robust VEHICLE-controller reproduction remains incomplete. The previously verified scalar Algorithm2 contract does not provide the nonlinear vehicle confidence/error set, terminal safe set, noisy-state certificate or original-author numerical reproduction. The existing nominal vehicle specialization remains explicitly limited.',
        '- All32 original references have a structural audit and five uploaded primary sources are version-verified. Remaining primary metadata/claim verification and broader novelty justification are open. GitHub primary-code search returned Forbidden in this environment; no unavailable source was invented.',
        '- Physical sensor, communication and actuator validation requires connected hardware if vehicle readiness is claimed. Current scope is software-in-the-loop; no physical readiness, global stability, energy advantage, universal neuro-symbolic novelty or49-fold speedup is asserted.',
        '- Evidence reports and reviewer-status records are reviewable drafts, not a submission-ready superiority/safety paper. No V2V mechanism was introduced into Paper1.','',
        'Resume verified software stages with `python tools/controller_review/run_recovery_work.py --publish`. This command preserves partial/failed runs, original deadlines and frozen criteria; it cannot manufacture laptop or vehicle measurements.']
    import re
    text='\n\n'.join(lines).replace('|\n\n|','|\n|');parts=re.split(r'(`[^`]*`|\$\$.*?\$\$)',text,flags=re.S)
    for i,s in enumerate(parts):
        if s.startswith(('`','$$')):continue
        s=re.sub(r'(?<=[A-UW-Za-uw-z])(?=\d)',' ',s);parts[i]=re.sub(r'(?<=\d)(?=[A-UW-Za-uw-z])',' ',s)
    (out/'README.md').write_text(''.join(parts).rstrip()+'\n')
    status=dict(episodes=decision['episodes'],transitions=decision['transitions'],survivors=sum(m['survived'] for m in summary.values()),selected=decision['selected'],student_gain_pct=gains,
        structural_40ms_recovery_fixed=True,current_packet_expiry_modelled=True,full_selection_pass=decision['selected'] is not None,
        timing_guard_off=timing['profiles']['off'],timing_guard_on=timing['profiles']['on'],reserved_unopened=True,
        dynamic_recovery_pass=dynamic['functional_recovery_pass'],dynamic_ticks=dynamic['ticks'],dynamic_deadline_misses=dynamic['deadline_misses'],
        actual_laptop_validation=False,native_selected_confirmation=False,matched_robust_vehicle_reproduction=False,all_primary_references_verified=False,physical_validation=False,submission_ready=False,new_training_steps=0)
    (out/'completion-status.json').write_text(json.dumps(status,indent=2)+'\n')
    os.environ.setdefault('XDG_CACHE_HOME','/tmp/lans-v8-font-cache');Path(os.environ['XDG_CACHE_HOME']).mkdir(exist_ok=True)
    for suffix in ('docx','pdf'):
        cmd=['pandoc',str(out/'README.md'),'-o',str(out/f'recovery-update.{suffix}')]
        if suffix=='pdf':cmd+=['--pdf-engine=xelatex','-V','mainfont=DejaVu Serif','-V','geometry:margin=22mm','-V','fontsize=10pt']
        subprocess.run(cmd,check=True)
    with zipfile.ZipFile(out/'LANS_Recovery_Reports.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ('README.md','recovery-update.docx','recovery-update.pdf','summary.json','decision.json','completion-status.json','manifest.json','evidence-hashes.json','tests.log','activity-by-scenario.json','deadline-attribution.json','timing/protocol.json','timing/summary.json','timing/verification.json','timing/environment-after-campaign.json','dynamic-recovery/summary.json','dynamic-recovery/verification.json'):z.write(out/name,name)
    checks={}
    for f in out.glob('*.zip'):
        with zipfile.ZipFile(f) as z:assert z.testzip() is None
        checks[f.name]=hashlib.sha256(f.read_bytes()).hexdigest()
    (out/'artifact-quality.json').write_text(json.dumps(dict(archive_crc_pass=True,sha256=checks),indent=2)+'\n');print(json.dumps(status,indent=2))

if __name__=='__main__':main()
