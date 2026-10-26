"""Render the frozen real-worker campaign, including negative timing outcomes."""
import argparse
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    s=json.loads((a.run/'summary.json').read_text());v=json.loads((a.run/'verification.json').read_text())
    rows=s['episodes'];ticks=sum(r['ticks'] for r in rows);misses=sum(r['deadline_misses'] for r in rows)
    lines=['# LANS retained student: real-worker end-to-end validation','',
        '## Outcome','',
        f"Completed {len(rows)} wall-paced software-in-the-loop episodes and {ticks:,} control ticks with actual retained checkpoints. Functional acceptance: **{'PASS' if s['functional_pass'] else 'FAIL'}**. Strict 10 ms software-response timing acceptance: **{'PASS' if s['timing_pass'] else 'FAIL'}** ({misses:,}/{ticks:,} misses, {100*misses/ticks:.3f}%). All outcomes remain included.",'',
        'This completes the declared cloud software validation campaign. It does not establish native Webots execution, physical actuator acknowledgement, target-vehicle timing, formal safety, hard-real-time guarantees or a deployment-ready retained student.','',
        '## Fixed campaign and interfaces','',
        'Three frozen supervised student seeds (701/802/903), one DLC220 path, 20 m/s, 13 s simulated episodes at 10 ms control period. Each seed sees six cases: no added delay, real 20/60/100 ms worker sleeps after actual inference, two CPU contenders, and deliberate inference-process termination after one third of the episode. Identical deterministic sensor-noise draws pair each case with an independent pure-LQR replay. These are engineering fault tests, not a new reserved research leaderboard.','',
        'One real spawned inference process and one in-flight request. A monotonic observation timestamp crosses the IPC boundary unchanged. Control never awaits a response during the episode. Missing/stale/error outputs give local LQR authority. The original predictive Gate is used, with a second age check immediately before software command application. Inference runs on one selected CPU; control runs on another when available. Stress starts one busy process on each selected core.','',
        'The old student input assumes a simulated pending proposal and known completion time. The causal adapter cannot know these: pending proposal, time-to-ready and configured service channels use explicit zero placeholders, while busy/elapsed age/held-packet information remains observable. No hidden worker result or future completion enters inference. This changes the input distribution; weights and normalization are unchanged. The original student is therefore not certified as a native policy by these tests. Causal-interface training and a separate performance evaluation are required before promotion.','',
        '## Timing, fallback and tracking','',
        '| Seed | Case | Delivered packets | Active ticks | 10 ms misses | Response p99 ms | Response max ms | Tracking RMSE m | Paired LQR RMSE m | Survived |',
        '|---:|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in rows:
        lines.append(f"| {r['seed']} | {r['case']} | {r['packets']} | {r['active_ticks']} | {r['deadline_misses']} | {r['response']['p99_ms']:.3f} | {r['response']['max_ms']:.3f} | {r['rmse']:.6f} | {r['paired_lqr_rmse']:.6f} | {r['survived']} |")
    lines+=['',
        f"Survival: {sum(r['survived'] for r in rows)}/{len(rows)}. Stale held-packet ticks: {v['stale_ticks']:,}; stale-authority violations: {sum(r['stale_authority_violations'] for r in rows)}. Fallback violations: {sum(r['fallback_violations'] for r in rows)}.",'',
        'The 60/100 ms cases must have zero learned authority and exact paired-LQR commands. This is fallback evidence, not learned delay compensation. A packet can be held across many control ticks, so stale-tick counts are not independent packets. Crash cases check continued control after detected worker death; initial pre-crash corrections can make the full trajectory differ from pure LQR.','',
        '## Measurement boundaries','',
        '- `response`: software apply timestamp minus scheduled release; includes release lateness, polling, observer, features, LQR, request IPC and gate. A response ≥ the next period deadline is counted using exact nanoseconds.','- `control`: apply timestamp minus actual release; excludes scheduler wakeup lateness.','- `inference`: actual model call, excluding injected worker sleep.','- `request_to_delivery`: original observation to parent receipt; includes observer/feature work, request IPC/queueing, inference, injected delay, response IPC and polling.','- `earned_application_age`: observation-to-application age only on ticks where learned authority is nonzero. The held-packet age distribution is separately reported.','- Model load/startup and JIT warmup occur before pacing. Initial smoke exposed first-call compilation stalls; final warmup explicitly exercises returned-array layouts and observer paths. Smoke logs are retained separately and are not mixed with final statistics.','',
        'The plant integrates fixed 10 ms simulated steps, paced by wall time; if the OS stalls, simulated physics does not independently continue on hardware. No unexecuted physics intervals are disguised as continuous physical validation. The software application timestamp precedes the in-process plant call; CAN transport/actuator acknowledgement is not measured.','',
        '## Independent verification','',
        f"Raw CSV verification passes: {v['raw_timestamp_and_model_replay_checks_pass']}. Plant/observer/LQR replay passes: {v['plant_observer_lqr_replay_pass']}. Checked {v['packets']:,} actual model outputs against their logged observations, timestamp ordering and exact injected-delay lower bounds; recomputed all stale ages, deadlines, tracking errors, RMSE and paired-LQR command differences. Model/source hashes and full case grid are checked. This is a separate verification script, not an external review.",'',
        '## Interpretation and remaining deployment requirements','',
        'Functional fault handling and zero stale authority do not imply that a 100 Hz loop always meets deadlines. The recorded timing failure must remain visible. Shared cloud scheduling is not a real-time operating system; this campaign does not isolate one unique cause of deadline tails. CPU affinity and warmup are documented configuration, not a proof of schedulability.','',
        'A deployment claim requires a causal-feature-trained/validated policy, native simulator integration, target CPU/OS execution, measured physical I/O and sensor age, and an independently approved timing envelope. Those resources are outside this cloud software run. No model retraining, gate tuning, production deployment or hardware certification was performed.','',
        '## Reproduce','', '```bash',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/lans-timing-numba \\',
        '  /workspace/lans-venv/bin/python tools/controller_review/test_realtime_student.py -v',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/lans-timing-numba \\',
        '  /workspace/lans-venv/bin/python tools/controller_review/realtime_student.py --output /tmp/lans-real-worker --seconds 13',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/lans-timing-numba \\',
        '  /workspace/lans-venv/bin/python tools/controller_review/verify_realtime_student.py --run /tmp/lans-real-worker',
        'python tools/controller_review/report_realtime_student.py --run /tmp/lans-real-worker', '```','',
        'Use a fresh output directory. Outcomes vary with wall-clock scheduling; do not rerun until the negative timing result disappears. Protocol and source/model hashes are written before episode execution. Raw packet and tick CSVs, per-case summaries and combined verification accompany this report.','']
    (a.run/'README.md').write_text('\n'.join(lines))

if __name__=='__main__':main()
