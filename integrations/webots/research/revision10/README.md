# Small longer-preview / sequence diagnostic

**Timestamp correction:** the archived run below re-submitted held proposals between50ms policy queries, incorrectly assigning a fresh observation timestamp. Corrected code submits only newly queried proposals and preserves packet age during holding/delivery; prediction branches use the same schedule. The archived numbers remain historical and must be reassessed using a new output directory. Revision7–9 every-available-tick interfaces keep their original default semantics.

[Results](../../results/revision10-headroom/report.md). Protocol/executable freeze `dcf203c` before execution. New development noise base730000000; two repetitions,25m/s DLC220, six conditions, six methods (72 episodes). The current student, LQR/fixed references,200ms/400ms held teachers and400ms two-stage beam teacher share the actual gate, actuator, sensor and service-delay rules. All methods query new proposals at most every50ms; this differs from original revision8 inference cadence. Comparisons apply to this slice only.

No teacher uses actual future measurement noise. Forecasts are independent zero/antithetic Gaussian branches. Teacher current truth/parameters and exact geometry are privileged, not student inputs. The sequence search keeps two first actions and five second actions, not every possible sequence. Longer-horizon minima are not episode-optimal bounds.

All72 episodes survive, with exact100ms LQR fallback. Mean reductions versus LQR: student0.493%, hold20 0.228%, hold40 0.635%, sequence40 0.634%. No regional mean reaches5%. Hold40 sensor-stress reduction2.501%; tire mismatch is0.708% worse than LQR. Thus neither longer preview nor this sequence search demonstrates enough extra headroom for5%; it would be unjustified to launch expensive student/PPO retraining from this result. There is no claim that5% is impossible with other designs.

Corrected contract checks cover selection against the50ms-submission rollout cost, nonmutation/branch symmetry and severe-delay fallback. `revision7/test_submission.py` additionally checks original-object parity, retained timestamps and between-query delivery. Full grid keys, denominators and severe equality are verified by the report command. Raw episodes, paired per-noise detail, logs and source copies are retained. No settings were adjusted after results, no old evaluation data tuned upon, no training or promotion performed.

From repository root, using the pinned research Python environment:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export NUMBA_CACHE_DIR=/tmp/lans-v10-numba MPLCONFIGDIR=/tmp/lans-mpl
python integrations/webots/research/revision10/test_diagnostic.py -v
python integrations/webots/research/revision10/run.py --output /tmp/lans-preview-dev
python integrations/webots/research/revision10/report.py --run /tmp/lans-preview-dev
```

Output must be a new directory. Tests' severe-delay trajectories use the declared development seed, not final test data. No unseen-road, native timing, safety or broad5% claim follows. Next investigation, if pursued under a new protocol, should attribute tire-mismatch predictor rejection and objective/closed-loop disagreement before any larger training budget.
