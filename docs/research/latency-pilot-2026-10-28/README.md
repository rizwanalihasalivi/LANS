# Small latency pilot — 2026-10-28

Development diagnostic, not promotion or literature reproduction. Frozen existing v12 prior PPO pair 0 and student pair 0; no training. 24 episodes: one sine120 path, both mirrors, 20 m/s, one fresh paired noise seed, four controllers and three service-delay profiles. All episodes survived.

| Response-delay profile | Raw PPO gain vs LQR | Compensated PPO gain | Student gain |
|---|---:|---:|---:|
| 10 ms | 0.480% | 0.489% | 0.664% |
| repeating 10/40/20/100 ms, each held 2 s | 0.229% | 0.229% | 0.381% |
| 20 ms with requests at 3–4 s delayed 1 s | 0.213% | 0.193% | 0.239% |

Gains use mean episode lateral RMSE. Actual steering-rate RMS changes for compensated PPO are +0.827%, +0.245%, +0.204%, respectively. Student is better in all three aggregate profiles. No consistent compensation advantage or 20% PPO benefit demonstrated. Single model pair and one path do not support statistical/generalization claims.

Delay is simulated response availability with one request in flight; no actual CPU sleep/stall, shared-CPU contention, command-queue actuation delay, sensor delay or wall-clock deadline claim. Existing actuator dynamics remain unchanged. LQR receives current estimates. Neither new application-time command-queue compensation nor a published robust controller is implemented in this pilot. The proposed broad mechanism remains to be specified and evaluated. Reserved tests untouched.

Raw NPZ traces, per-episode metrics and hashes are saved. Run `python docs/research/latency-pilot-2026-10-28/run.py` using the existing Python 3.10 environment; completed episode hashes are checked on resume. Existing source files were not modified.
