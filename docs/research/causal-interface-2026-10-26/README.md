# Causal student input correction and deadline investigation

## Outcome

The causal query-time input mismatch is corrected in an isolated experimental profile and three newly trained checkpoints. TRAIN-only normalization, DEV-only epoch selection and logged worker inputs are verified. Functional validation: **True**. Strict 10 ms timing validation: **False**. There are 1,358/23,400 response deadline misses (5.803%). No missed tick is discarded.

Existing retained models and the earlier negative timing campaign are preserved. This does not promote the new policy to native Webots or a real vehicle, and is not the final reserved controller comparison.

## Causal feature correction

The archived label collector only queries its teacher when its simulated worker is available. At such a query, any ready packet can be delivered observably. The projection makes that delivery explicit: its known result/age become the held packet. A pending packet whose completion is still in the future is rejected by the projection. Pending proposal, pending completion forecast, pending age/busy, and configured service channels (14/15/16/17/19) are zeroed in both training and runtime. At actual inference queries the real worker is idle; held packet, gate history, actuator, measured state/speed and map preview remain available. Removed channels cannot enter the new predict interface with nonzero values.

Architecture remains 20→64→64→5 with tanh. Removed inputs are constant zero rather than changing checkpoint dimensions. Three models receive exactly 20 supervised epochs each, initialized independently; no PPO, new teacher search or fresh-validation-based selection. Existing TRAIN/DEV teacher labels are reused; their deterministic service model still differs from real scheduler timing, which remains a coverage limitation rather than a hidden-feature dependency. No unseen-domain performance gain is claimed.

Verified 216 training and 108 development episode groups. Ready-packet contexts projected: 9,648 TRAIN, 4,824 DEV. Normalization is refitted on projected TRAIN only; fresh validation noise never enters fitting or epoch selection.

## Deadline investigation and changes

Historical raw logs contained 1,743 misses: 1,642 already had ≥10 ms release lateness, while 139 spent ≥10 ms in control processing; counts overlap. Historical logs alone cannot identify the unique cause. They also contain up to 4.138 s scheduling lateness and catch-up bursts; their 7.45% rate is not a clean measurement of neural inference cost.

The new finite control window is fully warmed before pacing; cyclic garbage collection is collected before and disabled during the bounded window, then restored. Reference-count cleanup remains active. This removes one avoidable source of unpredictable work but does not prove that GC caused historical misses. Pre/post Numba signatures are recorded to detect any new JIT signatures.

Per-stage wall and thread CPU times, context-switch counts and cgroup CPU counters are recorded. A late software control decision resets learned authority to LQR immediately before application. The deadline is still the original scheduled tick+10 ms; it is never rebased and delayed ticks are never removed. Age rejection at ≥50 ms, the predictive Gate, physical bounds and worker lifecycle otherwise remain unchanged.

Fresh misses already ≥10 ms late at release: 1,192; control wall time ≥10 ms: 161; control thread CPU ≥10 ms: 111. Overlap of late release and slow control: 63. Overall control p99: 7.791 ms wall, 3.990 ms thread CPU. Episodes with additional JIT signatures after warmup: 0.

Thread CPU versus wall time helps distinguish CPU work from off-CPU time but does not uniquely diagnose hypervisor/OS contention. Cgroup counters are shared and span the episode plus cleanup; correlation is not proof. Old/new campaigns differ in noise, policy, GC configuration and cloud conditions, so any miss-rate difference is descriptive, not a causal speedup claim.

## Fresh real-worker development validation

| Seed | Case | Deadline misses | Late release ticks | Wall control p99 ms | CPU control p99 ms | Active ticks | RMSE m | Paired LQR RMSE m |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 701 | nominal | 41 | 41 | 3.576 | 3.190 | 235 | 0.041827 | 0.046038 |
| 701 | delay20 | 67 | 64 | 6.347 | 6.350 | 12 | 0.046038 | 0.046038 |
| 701 | delay60 | 20 | 20 | 2.382 | 2.382 | 0 | 0.046038 | 0.046038 |
| 701 | delay100 | 129 | 123 | 12.204 | 12.209 | 0 | 0.046038 | 0.046038 |
| 701 | cpu_stress | 52 | 17 | 11.631 | 3.683 | 209 | 0.041906 | 0.046038 |
| 701 | worker_crash | 68 | 58 | 13.496 | 9.372 | 37 | 0.043973 | 0.046038 |
| 802 | nominal | 7 | 7 | 2.528 | 2.529 | 206 | 0.042629 | 0.047153 |
| 802 | delay20 | 251 | 246 | 8.100 | 8.450 | 6 | 0.047163 | 0.047153 |
| 802 | delay60 | 3 | 1 | 1.577 | 1.577 | 0 | 0.047153 | 0.047153 |
| 802 | delay100 | 65 | 61 | 2.667 | 2.672 | 0 | 0.047153 | 0.047153 |
| 802 | cpu_stress | 100 | 67 | 10.571 | 3.514 | 182 | 0.043208 | 0.047153 |
| 802 | worker_crash | 59 | 51 | 4.453 | 4.454 | 50 | 0.044819 | 0.047153 |
| 903 | nominal | 293 | 288 | 8.893 | 8.895 | 166 | 0.043647 | 0.047520 |
| 903 | delay20 | 11 | 11 | 2.458 | 2.459 | 13 | 0.047504 | 0.047520 |
| 903 | delay60 | 79 | 72 | 4.003 | 4.004 | 0 | 0.047520 | 0.047520 |
| 903 | delay100 | 8 | 5 | 2.039 | 2.040 | 0 | 0.047520 | 0.047520 |
| 903 | cpu_stress | 59 | 23 | 10.101 | 3.589 | 210 | 0.042890 | 0.047520 |
| 903 | worker_crash | 46 | 37 | 8.111 | 8.063 | 48 | 0.044750 | 0.047520 |

Survived: 18/18. Stale-authority violations: 0. Late-authority violations: 0. Fallback violations: 0.

Independent verifier checked 10,629 logged inference outputs and 23,400 control ticks; it replayed plant/observer/LQR, checked packet timing/order, removed input channels, all stale/late fallbacks, full grids, model/source hashes and RMSE. Four targeted contract tests pass, including rejection of unknown future packets and deadline revocation.

## Remaining constraints and next decision

The cloud software experiment is complete for this fixed revision. If timing_pass is false, strict 100 Hz execution remains unproven and the final reserved controller comparison is not opened. Fixing inputs and rejecting late corrections do not make an overloaded OS meet deadlines. Scheduler/resource isolation must be validated on a suitable host before timing promotion.

The software plant advances fixed 10 ms simulated steps under wall pacing; it does not evolve continuously while the host stalls. Logged software command application is not physical actuator acknowledgement. One known road, 20 m/s and three seeds do not establish broad tracking superiority. Native Webots integration, causal-service coverage studies, target CPU/OS I/O timing and real-vehicle readiness are separate remaining validations. No target vehicle hardware is attached to this environment.

## Reproduce

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /workspace/lans-venv/bin/python tools/controller_review/causal_student.py --seed 701 --output /tmp/causal-models/701
# Repeat for 802 and 903, each in a fresh output directory.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/lans-timing-numba \
  /workspace/lans-venv/bin/python tools/controller_review/realtime_causal.py --model-root /tmp/causal-models --output /tmp/causal-validation --seconds 13
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/lans-timing-numba \
  /workspace/lans-venv/bin/python tools/controller_review/verify_realtime_causal.py --run /tmp/causal-validation --model-root /tmp/causal-models
```

Protocol, source snapshots, weights, normalization, training logs, all epochs, smoke evidence, per-case raw ticks/packets, fresh validation and verification records are retained. Do not rerun until a favourable timing result appears.
