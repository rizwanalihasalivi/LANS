"""Report causal feature correction and honest deadline diagnostics."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import numpy as np


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    summary=json.loads((a.run/'validation/summary.json').read_text())
    verified=json.loads((a.run/'validation/verification.json').read_text())
    models=json.loads((a.run/'models/verification.json').read_text())
    episodes=summary['episodes']
    rows=[r for f in (a.run/'validation').glob('*-ticks.csv.gz') for r in csv.DictReader(gzip.open(f,'rt'))]
    misses=[r for r in rows if r['deadline_miss']=='True']
    breakdown=dict(ticks=len(rows),deadline_misses=len(misses),
        late_release_ticks=sum(float(r['release_lateness_ms'])>=10 for r in misses),
        control_over_10ms_ticks=sum(float(r['control_ms'])>=10 for r in misses),
        control_cpu_over_10ms_ticks=sum(float(r['control_cpu_ms'])>=10 for r in misses),
        overlap_late_and_slow=sum(float(r['release_lateness_ms'])>=10 and float(r['control_ms'])>=10 for r in misses),
        thread_cpu_p99_ms=float(np.quantile([float(r['control_cpu_ms']) for r in rows],.99)),
        wall_control_p99_ms=float(np.quantile([float(r['control_ms']) for r in rows],.99)),
        max_release_lateness_ms=max(float(r['release_lateness_ms']) for r in rows),
        post_warmup_signature_changes=sum(e['signatures_before']!=e['signatures_after'] for e in episodes))
    (a.run/'deadline-analysis.json').write_text(json.dumps(breakdown,indent=2)+'\n')
    lines=['# Causal student input correction and deadline investigation','',
        '## Outcome','',
        f"The causal query-time input mismatch is corrected in an isolated experimental profile and three newly trained checkpoints. TRAIN-only normalization, DEV-only epoch selection and logged worker inputs are verified. Functional validation: **{summary['functional_pass']}**. Strict 10 ms timing validation: **{summary['timing_pass']}**. There are {len(misses):,}/{len(rows):,} response deadline misses ({100*len(misses)/len(rows):.3f}%). No missed tick is discarded.",'',
        'Existing retained models and the earlier negative timing campaign are preserved. This does not promote the new policy to native Webots or a real vehicle, and is not the final reserved controller comparison.','',
        '## Causal feature correction','',
        'The archived label collector only queries its teacher when its simulated worker is available. At such a query, any ready packet can be delivered observably. The projection makes that delivery explicit: its known result/age become the held packet. A pending packet whose completion is still in the future is rejected by the projection. Pending proposal, pending completion forecast, pending age/busy, and configured service channels (14/15/16/17/19) are zeroed in both training and runtime. At actual inference queries the real worker is idle; held packet, gate history, actuator, measured state/speed and map preview remain available. Removed channels cannot enter the new predict interface with nonzero values.','',
        'Architecture remains 20→64→64→5 with tanh. Removed inputs are constant zero rather than changing checkpoint dimensions. Three models receive exactly 20 supervised epochs each, initialized independently; no PPO, new teacher search or fresh-validation-based selection. Existing TRAIN/DEV teacher labels are reused; their deterministic service model still differs from real scheduler timing, which remains a coverage limitation rather than a hidden-feature dependency. No unseen-domain performance gain is claimed.','',
        f"Verified {models['train_groups']} training and {models['dev_groups']} development episode groups. Ready-packet contexts projected: {models['train_ready_packet_rows']:,} TRAIN, {models['dev_ready_packet_rows']:,} DEV. Normalization is refitted on projected TRAIN only; fresh validation noise never enters fitting or epoch selection.",'',
        '## Deadline investigation and changes','',
        'Historical raw logs contained 1,743 misses: 1,642 already had ≥10 ms release lateness, while 139 spent ≥10 ms in control processing; counts overlap. Historical logs alone cannot identify the unique cause. They also contain up to 4.138 s scheduling lateness and catch-up bursts; their 7.45% rate is not a clean measurement of neural inference cost.','',
        'The new finite control window is fully warmed before pacing; cyclic garbage collection is collected before and disabled during the bounded window, then restored. Reference-count cleanup remains active. This removes one avoidable source of unpredictable work but does not prove that GC caused historical misses. Pre/post Numba signatures are recorded to detect any new JIT signatures.','',
        'Per-stage wall and thread CPU times, context-switch counts and cgroup CPU counters are recorded. A late software control decision resets learned authority to LQR immediately before application. The deadline is still the original scheduled tick+10 ms; it is never rebased and delayed ticks are never removed. Age rejection at ≥50 ms, the predictive Gate, physical bounds and worker lifecycle otherwise remain unchanged.','',
        f"Fresh misses already ≥10 ms late at release: {breakdown['late_release_ticks']:,}; control wall time ≥10 ms: {breakdown['control_over_10ms_ticks']:,}; control thread CPU ≥10 ms: {breakdown['control_cpu_over_10ms_ticks']:,}. Overlap of late release and slow control: {breakdown['overlap_late_and_slow']:,}. Overall control p99: {breakdown['wall_control_p99_ms']:.3f} ms wall, {breakdown['thread_cpu_p99_ms']:.3f} ms thread CPU. Episodes with additional JIT signatures after warmup: {breakdown['post_warmup_signature_changes']}.",'',
        'Thread CPU versus wall time helps distinguish CPU work from off-CPU time but does not uniquely diagnose hypervisor/OS contention. Cgroup counters are shared and span the episode plus cleanup; correlation is not proof. Old/new campaigns differ in noise, policy, GC configuration and cloud conditions, so any miss-rate difference is descriptive, not a causal speedup claim.','',
        '## Fresh real-worker development validation','',
        '| Seed | Case | Deadline misses | Late release ticks | Wall control p99 ms | CPU control p99 ms | Active ticks | RMSE m | Paired LQR RMSE m |',
        '|---:|---|---:|---:|---:|---:|---:|---:|---:|']
    for e in episodes:
        lines.append(f"| {e['seed']} | {e['case']} | {e['deadline_misses']} | {e['late_release_ticks']} | {e['control']['p99_ms']:.3f} | {e['control_cpu']['p99_ms']:.3f} | {e['active_ticks']} | {e['rmse']:.6f} | {e['paired_lqr_rmse']:.6f} |")
    lines+=['',f"Survived: {sum(e['survived'] for e in episodes)}/{len(episodes)}. Stale-authority violations: {sum(e['stale_authority_violations'] for e in episodes)}. Late-authority violations: {sum(e['late_authority_violations'] for e in episodes)}. Fallback violations: {sum(e['fallback_violations'] for e in episodes)}.",'',
        f"Independent verifier checked {verified['packets']:,} logged inference outputs and {verified['ticks']:,} control ticks; it replayed plant/observer/LQR, checked packet timing/order, removed input channels, all stale/late fallbacks, full grids, model/source hashes and RMSE. Four targeted contract tests pass, including rejection of unknown future packets and deadline revocation.",'',
        '## Remaining constraints and next decision','',
        'The cloud software experiment is complete for this fixed revision. If timing_pass is false, strict 100 Hz execution remains unproven and the final reserved controller comparison is not opened. Fixing inputs and rejecting late corrections do not make an overloaded OS meet deadlines. Scheduler/resource isolation must be validated on a suitable host before timing promotion.','',
        'The software plant advances fixed 10 ms simulated steps under wall pacing; it does not evolve continuously while the host stalls. Logged software command application is not physical actuator acknowledgement. One known road, 20 m/s and three seeds do not establish broad tracking superiority. Native Webots integration, causal-service coverage studies, target CPU/OS I/O timing and real-vehicle readiness are separate remaining validations. No target vehicle hardware is attached to this environment.','',
        '## Reproduce','', '```bash',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /workspace/lans-venv/bin/python tools/controller_review/causal_student.py --seed 701 --output /tmp/causal-models/701',
        '# Repeat for 802 and 903, each in a fresh output directory.',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/lans-timing-numba \\',
        '  /workspace/lans-venv/bin/python tools/controller_review/realtime_causal.py --model-root /tmp/causal-models --output /tmp/causal-validation --seconds 13',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/lans-timing-numba \\',
        '  /workspace/lans-venv/bin/python tools/controller_review/verify_realtime_causal.py --run /tmp/causal-validation --model-root /tmp/causal-models',
        '```','',
        'Protocol, source snapshots, weights, normalization, training logs, all epochs, smoke evidence, per-case raw ticks/packets, fresh validation and verification records are retained. Do not rerun until a favourable timing result appears.','']
    (a.run/'README.md').write_text('\n'.join(lines))

if __name__=='__main__':main()
