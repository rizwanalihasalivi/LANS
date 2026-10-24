# Five-seed vehicle-control campaign

This is an isolated integration research workflow. It does not import or modify the repository's primary model, `experiments/phase1/`, legacy PPO training scripts, or specification. A separate nonlinear Fiala bicycle **training/evaluation surrogate** and a native Webots vehicle are deliberately distinguished. Results are not a validation of the untouched primary experiment pipeline.

## Reproduce in the documented Linux cloud image

Prerequisites: Bash, Git, uv, curl, tar, Debian apt/dpkg and archive keyring, `xdpyinfo`, CPU and sufficient workspace disk. The tested environment has a four-CPU quota and 32 GiB RAM. No GPU, credentials, or shared Webots installation is required. Both installers write to this integration's ignored `.runtime/` directory. Debian packages are distribution-resolved; this is not a fully locked OS image.

From the checkout root:

```bash
bash integrations/webots/install-private.sh
bash integrations/webots/install-research.sh
export LANS_PYTHON="$PWD/integrations/webots/.runtime/research-venv/bin/python"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export NUMBA_CACHE_DIR="$PWD/integrations/webots/.runtime/numba"
export MPLCONFIGDIR="$PWD/integrations/webots/.runtime/mpl"

"$LANS_PYTHON" integrations/webots/research/test-research.py -v
"$LANS_PYTHON" integrations/webots/research/validate-core.py
"$LANS_PYTHON" integrations/webots/research/test-worker.py
```

The worker test uses the committed final seed-0 policy. The original adapter tests remain available:

```bash
python3 -m unittest discover -s integrations/webots -p test_adapter.py -v
```

To retrain, use a fresh output directory; ten policies are trained, two roles × five seeds × 1,000,000 steps. No best-seed or best-checkpoint selection is performed. Four training processes run at most, each with one Torch/BLAS thread. The default output location contains the committed final models; verified completed seeds are retained rather than overwritten.

```bash
bash integrations/webots/research/run-final-training.sh
# Fresh comparison using the committed final models; choose a new output directory:
"$LANS_PYTHON" integrations/webots/research/evaluate.py \
  --training "$PWD/integrations/webots/results/research-training" \
  --output "$PWD/integrations/webots/results/evaluation-local"

# Fresh Webots open-loop, convergence and LQR tests:
"$LANS_PYTHON" integrations/webots/research/run-physical.py \
  --suite development --output "$PWD/integrations/webots/results/physical-local"
# Fresh real-process asynchronous PPO/fusion transfer:
"$LANS_PYTHON" integrations/webots/research/run-physical.py \
  --suite transfer --output "$PWD/integrations/webots/results/transfer-local"
```

A fresh training output can be passed as the first argument to `run-final-training.sh`; the surrogate evaluator accepts that path with `--training`. The Webots transfer runner deliberately uses `results/research-training` so it cannot silently pick a different set of policies. It verifies each policy hash and 1M-step completion metadata before loading it. All result-producing commands reject existing output directories, except training's explicit verified-completion reuse. Partial runs require inspection and preservation; they are not silently overwritten.

`run-training.sh`, `run-residual-training.sh`, `train.py`, and `train-residual.py` retain development provenance and are **not** the final campaign entry points. `train.py` also supplies the progress callback used by the final trainer. `finalize-checkpoint.py` is a narrowly scoped metadata-recovery utility: four full-policy checkpoints had already saved successfully when a metadata-key bug occurred. Recovery verified the saved model's step count/seed and hashes without changing weights. Their metadata explicitly limits the recorded wall time to the final rollout.

## Protocol and model interfaces

- `protocol.json`: fixed vehicle, actuator, sensor, architecture, optimizer and base scenario choices.
- `comparison-protocol.json`: development-selected common Q/R and initial contact calibration assumptions.
- `final-training-protocol.json`: supersedes the earlier reward/exploration profile; both roles start from scratch with bounded positive survival reward and initial policy log standard deviation −2.
- `tracking-protocol.json`: analytically corrected curvature-equilibrium reference for every LQR-bearing method and the final residual training. Standalone full-command training never applies LQR to its action/reward, so its existing final models are unaffected.
- `evaluation-revision.json`: final reserved noise seed base 20000. Four partial earlier evaluation rows were discarded when the analytical baseline correction was made. No final policy is selected using evaluation results.
- `corridor-protocol.json`: explicitly non-ISO, sampled vehicle-footprint corridor check.
- `calibration.json`: nominal composite Webots parameters and final separate front/rear contact-slip multipliers; supersedes the initial single-material contact approximation for native Webots only.

PPO observations are fixed-scaled estimates: lateral error, heading error, lateral-error derivative from a Kalman state estimate, yaw rate, speed, steering state and three map-curvature previews. Position/heading/yaw/speed noise is injected before estimation. No true lateral velocity is supplied to the controller. The actuator encoder/internal state and map previews are not noised. The 10 ms sensor stress delays the position/heading/yaw/speed measurements, not the map/actuator channels.

The model action is a normalized scalar, multiplied by 0.5 to obtain radians. The **full** role applies the complete command; the **residual** role adds its output to the corrected LQR command before identical saturation and actuator physics. Observation normalization is fixed in code; `VecNormalize` only normalizes training rewards. The saved normalization object is retained for provenance/resume and is not needed for deterministic policy inference.

The surrogate has static axle loads, per-axle 80,000 N/rad small-slip stiffness, Fiala saturation, constant prescribed longitudinal speed, RK4 at 1 ms, 10 ms control, ±0.5 rad magnitude, 0.35 rad/s rate and 0.05 s first-order steering lag. It omits longitudinal powertrain dynamics and load transfer. The speed-conditioned Kalman/LQR models are linear approximations; common Q/R are used at all three speeds. Tracking feedback is relative to the nonzero steady-turn lateral velocity, heading error and yaw rate, not to an incorrect zero-turn state.

Training is **standalone synchronous PPO** with no stale-action reward attribution. Asynchronous deployment is evaluated with frozen policies. This is not the tentative latency-training curriculum from the specification. Known path geometries are reused; only the final noise realizations are held out. Do not describe these results as unseen-path generalization.

## Timing and worker behavior

The surrogate evaluator uses a deterministic one-in-flight service-time schedule with no backlog; control advances on the simulation clock while outputs become available after 0/20/100 ms. Its model computation is synchronous wall-clock work for efficient simulation, so those experiments do not prove concurrent execution or real-time deadlines. Measured wall inference durations and simulated information ages are separate metrics.

Webots fusion uses `worker.py`, a real separate CPU process. Startup waits for model readiness before the test; during control, polling/submission never waits for inference. Requests while busy are dropped, at most one job is in flight, and the configured delay is a minimum **simulation-clock** availability delay. CSVs record observation/availability/control/state times, wall inference start/end, age, dropped requests and supervisor reason. Missing outputs have an explicit availability flag. Absolute inference start/end and availability fields are populated for asynchronous fusion; zero placeholders in non-worker modes must not be interpreted as measured events. These are accelerated simulations on a CPU-contended cloud machine, not a hard real-time or WCET benchmark.

All numerical guards remain in ablations. The fusion supervisor rejects nonfinite, stale, future/out-of-order and out-of-envelope PPO packets, selects LQR explicitly, and restores weight after tighter-state persistence with a ramp. Gate settings are development assumptions, not a proven safe region of attraction. Nominal PPO weight is 0.7. The no-supervisor ablation retains age weighting but removes state gates/recovery; fixed-weight uses 0.7 when a finite output exists. The residual comparator uses age-decayed residual weighting and is not a bit-for-bit reproduction of the legacy paper implementation.

## Evidence and limitations

The final campaign contains ten 1M-step checkpoints, 810 paired surrogate episodes (six methods × five seeds × three speeds × three paths × three service delays), and 45 native Webots policy-transfer cases. Open-loop and convergence cases are in `results/physical-validated`; corrected-LQR cases are in `results/physical-tracking-final`. Raw CSVs, source/config snapshots, hashes, model artifacts and summaries distinguish current results from historical development attempts.

Run `analyze-physical.py`, `verify-campaign.py` and `report.py` to validate and summarize the committed final evidence. These scripts intentionally fail on missing/incomplete data. See [the validation document](../../../docs/research/webots-validation.md) and generated [results report](../results/research-core/report.md).

Native Webots uses calibrated force-dependent contact slip plus Coulomb friction, **not Fiala tires**. Nominal mass/CG/yaw inertia and small-slip stiffness are checked; nonlinear tire behavior, dynamic load transfer and large-angle equivalence remain different. The original 125 m candidate with the tested quintic smoothing fails the chosen acceleration margin; an explicitly different 220 m development course is used. Its sampled 3.5 m vertical-strip corridor is not ISO geometry or exact continuous swept-volume collision detection.

PPO has three curvature-preview inputs, whereas the analytical LQR uses local curvature; these are end-to-end controller comparisons, not an isolated learning-benefit ablation with identical preview use. Training sine ranges include a worst-case 25 m/s acceleration slightly above the chosen 0.8 μg screening margin, though below μg; no claim that the entire training distribution satisfies that engineering margin is made. No stability, real-vehicle safety, journal-readiness, broad superiority or convergence guarantee follows from completing the budget.
