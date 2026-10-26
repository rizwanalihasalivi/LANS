# LANS retained student: real-worker end-to-end validation

## Outcome

Completed 18 wall-paced software-in-the-loop episodes and 23,400 control ticks with actual retained checkpoints. Functional acceptance: **PASS**. Strict 10 ms software-response timing acceptance: **FAIL** (1,743/23,400 misses, 7.449%). All outcomes remain included.

This completes the declared cloud software validation campaign. It does not establish native Webots execution, physical actuator acknowledgement, target-vehicle timing, formal safety, hard-real-time guarantees or a deployment-ready retained student.

## Fixed campaign and interfaces

Three frozen supervised student seeds (701/802/903), one DLC220 path, 20 m/s, 13 s simulated episodes at 10 ms control period. Each seed sees six cases: no added delay, real 20/60/100 ms worker sleeps after actual inference, two CPU contenders, and deliberate inference-process termination after one third of the episode. Identical deterministic sensor-noise draws pair each case with an independent pure-LQR replay. These are engineering fault tests, not a new reserved research leaderboard.

One real spawned inference process and one in-flight request. A monotonic observation timestamp crosses the IPC boundary unchanged. Control never awaits a response during the episode. Missing/stale/error outputs give local LQR authority. The original predictive Gate is used, with a second age check immediately before software command application. Inference runs on one selected CPU; control runs on another when available. Stress starts one busy process on each selected core.

The old student input assumes a simulated pending proposal and known completion time. The causal adapter cannot know these: pending proposal, time-to-ready and configured service channels use explicit zero placeholders, while busy/elapsed age/held-packet information remains observable. No hidden worker result or future completion enters inference. This changes the input distribution; weights and normalization are unchanged. The original student is therefore not certified as a native policy by these tests. Causal-interface training and a separate performance evaluation are required before promotion.

## Timing, fallback and tracking

| Seed | Case | Delivered packets | Active ticks | 10 ms misses | Response p99 ms | Response max ms | Tracking RMSE m | Paired LQR RMSE m | Survived |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 701 | nominal | 1292 | 187 | 5 | 3.613 | 25.446 | 0.042859 | 0.046585 | True |
| 701 | delay20 | 433 | 1 | 0 | 1.460 | 6.729 | 0.046586 | 0.046585 | True |
| 701 | delay60 | 175 | 0 | 75 | 526.233 | 608.181 | 0.046585 | 0.046585 | True |
| 701 | delay100 | 106 | 0 | 173 | 370.266 | 489.097 | 0.046585 | 0.046585 | True |
| 701 | cpu_stress | 1215 | 175 | 82 | 277.862 | 401.649 | 0.042891 | 0.046585 | True |
| 701 | worker_crash | 428 | 38 | 17 | 14.496 | 66.874 | 0.044998 | 0.046585 | True |
| 802 | nominal | 653 | 127 | 763 | 4061.655 | 4148.043 | 0.044464 | 0.047672 | True |
| 802 | delay20 | 425 | 3 | 22 | 34.673 | 102.883 | 0.047673 | 0.047672 | True |
| 802 | delay60 | 184 | 0 | 6 | 3.181 | 34.212 | 0.047672 | 0.047672 | True |
| 802 | delay100 | 118 | 0 | 0 | 1.193 | 3.210 | 0.047672 | 0.047672 | True |
| 802 | cpu_stress | 1272 | 243 | 31 | 19.920 | 41.181 | 0.043073 | 0.047672 | True |
| 802 | worker_crash | 424 | 47 | 26 | 25.606 | 57.318 | 0.045106 | 0.047672 | True |
| 903 | nominal | 1251 | 203 | 55 | 242.159 | 364.746 | 0.042732 | 0.046336 | True |
| 903 | delay20 | 433 | 0 | 0 | 1.649 | 5.509 | 0.046336 | 0.046336 | True |
| 903 | delay60 | 183 | 0 | 22 | 34.622 | 117.615 | 0.046336 | 0.046336 | True |
| 903 | delay100 | 91 | 0 | 419 | 361.106 | 422.090 | 0.046336 | 0.046336 | True |
| 903 | cpu_stress | 1278 | 215 | 28 | 12.038 | 34.652 | 0.042436 | 0.046336 | True |
| 903 | worker_crash | 424 | 31 | 19 | 18.408 | 64.973 | 0.044776 | 0.046336 | True |

Survival: 18/18. Stale held-packet ticks: 9,672; stale-authority violations: 0. Fallback violations: 0.

The 60/100 ms cases must have zero learned authority and exact paired-LQR commands. This is fallback evidence, not learned delay compensation. A packet can be held across many control ticks, so stale-tick counts are not independent packets. Crash cases check continued control after detected worker death; initial pre-crash corrections can make the full trajectory differ from pure LQR.

## Measurement boundaries

- `response`: software apply timestamp minus scheduled release; includes release lateness, polling, observer, features, LQR, request IPC and gate. A response ≥ the next period deadline is counted using exact nanoseconds.
- `control`: apply timestamp minus actual release; excludes scheduler wakeup lateness.
- `inference`: actual model call, excluding injected worker sleep.
- `request_to_delivery`: original observation to parent receipt; includes observer/feature work, request IPC/queueing, inference, injected delay, response IPC and polling.
- `earned_application_age`: observation-to-application age only on ticks where learned authority is nonzero. The held-packet age distribution is separately reported.
- Model load/startup and JIT warmup occur before pacing. Initial smoke exposed first-call compilation stalls; final warmup explicitly exercises returned-array layouts and observer paths. Smoke logs are retained separately and are not mixed with final statistics.

The plant integrates fixed 10 ms simulated steps, paced by wall time; if the OS stalls, simulated physics does not independently continue on hardware. No unexecuted physics intervals are disguised as continuous physical validation. The software application timestamp precedes the in-process plant call; CAN transport/actuator acknowledgement is not measured.

## Independent verification

Raw CSV verification passes: True. Plant/observer/LQR replay passes: True. Checked 10,385 actual model outputs against their logged observations, timestamp ordering and exact injected-delay lower bounds; recomputed all stale ages, deadlines, tracking errors, RMSE and paired-LQR command differences. Model/source hashes and full case grid are checked. This is a separate verification script, not an external review.

## Interpretation and remaining deployment requirements

Functional fault handling and zero stale authority do not imply that a 100 Hz loop always meets deadlines. The recorded timing failure must remain visible. Shared cloud scheduling is not a real-time operating system; this campaign does not isolate one unique cause of deadline tails. CPU affinity and warmup are documented configuration, not a proof of schedulability.

A deployment claim requires a causal-feature-trained/validated policy, native simulator integration, target CPU/OS execution, measured physical I/O and sensor age, and an independently approved timing envelope. Those resources are outside this cloud software run. No model retraining, gate tuning, production deployment or hardware certification was performed.

## Reproduce

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/lans-timing-numba \
  /workspace/lans-venv/bin/python tools/controller_review/test_realtime_student.py -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/lans-timing-numba \
  /workspace/lans-venv/bin/python tools/controller_review/realtime_student.py --output /tmp/lans-real-worker --seconds 13
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/lans-timing-numba \
  /workspace/lans-venv/bin/python tools/controller_review/verify_realtime_student.py --run /tmp/lans-real-worker
python tools/controller_review/report_realtime_student.py --run /tmp/lans-real-worker
```

Use a fresh output directory. Outcomes vary with wall-clock scheduling; do not rerun until the negative timing result disappears. Protocol and source/model hashes are written before episode execution. Raw packet and tick CSVs, per-case summaries and combined verification accompany this report.
