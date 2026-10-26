# Retained LANS student: computational delay pilot

Actual trained checkpoints, single-thread CPU inference; no synthetic policy fallback. No training or controller changes.

CPU: INTEL(R) XEON(R) PLATINUM 8573C. Python 3.10.22; PyTorch 2.0.0+cpu. Three retained seeds, 2,000 measured ticks per case per seed, after 200 warmup ticks.

| Simulated service (ms) | Stage | Samples | Median ms | p95 ms | p99 ms | Observed max ms | ≥10 ms | ≥50 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | observation | 6000 | 0.002597 | 0.004823 | 0.082086 | 0.663024 | 0 | 0 |
| 0 | lqr | 6000 | 0.003205 | 0.005114 | 0.074776 | 0.924300 | 0 | 0 |
| 0 | execution_gate | 6000 | 0.011303 | 0.076109 | 0.272803 | 1.257684 | 0 | 0 |
| 0 | total | 6000 | 0.135279 | 0.602919 | 1.095998 | 43.913128 | 2 | 0 |
| 0 | policy_called | 6000 | 0.110010 | 0.532154 | 1.000657 | 43.872312 | 2 | 0 |
| 20 | observation | 6000 | 0.002217 | 0.004622 | 0.059643 | 0.957821 | 0 | 0 |
| 20 | lqr | 6000 | 0.002734 | 0.005030 | 0.069345 | 1.091383 | 0 | 0 |
| 20 | execution_gate | 6000 | 0.010152 | 0.067291 | 0.245135 | 1.094035 | 0 | 0 |
| 20 | total | 6000 | 0.081214 | 0.479109 | 0.851860 | 2.889642 | 0 | 0 |
| 20 | policy_called | 3000 | 0.139701 | 0.570475 | 0.952778 | 2.756930 | 0 | 0 |
| 100 | observation | 6000 | 0.001511 | 0.003867 | 0.056039 | 0.631429 | 0 | 0 |
| 100 | lqr | 6000 | 0.001913 | 0.004283 | 0.053748 | 0.892128 | 0 | 0 |
| 100 | execution_gate | 6000 | 0.001522 | 0.005351 | 0.065041 | 0.905793 | 0 | 0 |
| 100 | total | 6000 | 0.005807 | 0.240658 | 0.552299 | 3.313445 | 0 | 0 |
| 100 | policy_called | 600 | 0.208817 | 0.629529 | 1.025513 | 1.574482 | 0 | 0 |

Policy timing includes validation, normalization, forward pass, argmax and normalized-to-radian proposal conversion. Execution timing includes worker lifecycle, predictive gate and fusion. Total includes observation construction and LQR, but excludes sensor/observer processing and plant integration. Policy statistics include only ticks with actual calls; totals include no-call ticks. Therefore the 100 ms case having lower total timing is not faster inference: the policy is called less often and stale packets bypass prediction.

The 0 ms workload contains two observed total compute intervals ≥10 ms, with a 43.913 ms maximum. No measured total exceeded 50 ms across 18,000 ticks. These are synchronous compute intervals, not measured asynchronous delivery deadlines. This benchmark does not demonstrate that LQR ran independently during an inference stall.

## Limits

- single deterministic nominal DLC workload at 20 m/s; not a tracking comparison
- excludes sensor/observer, IPC, queueing, scheduler guarantees and physical actuator delay
- simulated service delay does not sleep the CPU and is not measured inference time
- warmup excludes model loading and Numba compilation; max is an observed sample, not WCET
- shared cloud CPU results do not establish native Webots or vehicle hardware deadlines

Cases run sequentially (0/20/100 ms per seed); no causal latency-speed comparison is supported. Nominal deterministic workload alone does not cover all expensive gate branches or prove worst-case timing. Hardware and OS scheduling can change the tails.

## Reproduce

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/lans-timing-numba \
  /workspace/lans-venv/bin/python tools/controller_review/benchmark_student.py \
  --output /tmp/lans-student-timing --ticks 2000
```

Use a fresh output directory. First-call loading/JIT latency is excluded; measure startup separately before native deployment. Next validation should use a real asynchronous worker and measure observation-to-applied-command age, observer time, IPC and scheduler stalls on the target hardware.
