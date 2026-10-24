# Webots vehicle adapter validation

Initial milestone (commit `5811dc3`), 24 October 2026. Scope: secondary simulator interface validation only, following `specification-v0.1.md`; no claim of research-controller transfer, vehicle calibration or safety validation. Work is isolated on branch `webots/vehicle-validation`, worktree `/workspace/LANS-webots`, based on `de7b4a2`. Only `integrations/webots/` and this document are changed. The primary model, `experiments/phase1/`, legacy PPO training and specification are untouched. The separately authorized five-seed extension is documented below.

## Reproduce

From the worktree root:

```bash
cd /workspace/LANS-webots
bash integrations/webots/install-private.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s integrations/webots -p test_adapter.py -v
bash integrations/webots/run-tests.sh
```

An optional first argument selects a **new** output directory. The default is `integrations/webots/results/run-<UTC timestamp>`. Existing directories are rejected, preserving evidence. To analyze committed evidence against the exact corresponding implementation:

```bash
python3 integrations/webots/analyze.py integrations/webots/results/baseline
python3 integrations/webots/analyze.py integrations/webots/results/repeat
```

The actual recorded suite commands were:

```bash
bash integrations/webots/run-tests.sh "$PWD/integrations/webots/results/baseline"
bash integrations/webots/run-tests.sh "$PWD/integrations/webots/results/repeat"
```

Each case launches:

```bash
LANS_WEBOTS_CASE=straight LANS_WEBOTS_OUTPUT=/absolute/path/to/output \
  timeout 120 bash integrations/webots/run-webots.sh \
  --stdout --stderr --batch --mode=fast --no-rendering \
  "$PWD/integrations/webots/worlds/vehicle_validation.wbt"
```

Use the suite for acceptance checking and provenance; the single-case form is for diagnostics. `left` and `right` are the other valid case names.

## Runtime and reproducibility

The documented `/workspace/webots-setup` installation was absent in this instance. A **private** R2025a installation was created under the integration's ignored `.runtime/` directory. No shared Webots installation or system library was modified. The installer derives its path from its own location and extracts signed-index Debian packages locally. It was run twice successfully. The wrapper starts and cleans up its own Xvfb, uses Mesa software rendering, private writable XDG directories and a null audio backend. No GPU is required or claimed. Python 3.12.14 executed the final suite; only Python standard-library modules and Webots' own controller/vehicle bindings are used.

Pinned Webots source tag R2025a resolves to commit `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`. Five unmodified upstream PROTOs are downloaded into the private runtime. SHA-256 values are recorded in `runtime-sha256.txt`, including the Linux release archive. Hashes were recorded from verified-HTTPS downloads, not obtained from a publisher-signed checksum manifest; an attempted GitHub release-metadata API read returned HTTP 403. TLS verification was never disabled. Apt signature verification remains enabled. Debian package versions resolve from the specified trixie/bookworm repositories, so this is not a fully locked OS image.

Each run saves the configuration, platform/interpreter details, UTC start time and hashes of adapter, controller, world, analyzer and runner inputs in `provenance.json`. Its base HEAD is the pre-implementation commit; content hashes identify the actual code that ran. The analyzer verifies those hashes, rather than accepting old result files after a code change. Live processes are not needed to reproduce results.

## Adapter and coordinates

`integrations/webots/adapter.py` accepts an **independent complete front road-wheel steering command**, in radians, and a forward speed in m/s. No residual scaling or trained policy is involved.

| Quantity | Adapter / CSV convention | Webots mapping |
|---|---|---|
| Steering | positive left, radians, clipped to ±0.50 | `Driver.setSteeringAngle(-delta)`; Driver positive is right |
| Speed command | m/s, nonnegative | `setCruisingSpeed(v * 3.6)` accepts km/h |
| Wheel-derived speed | m/s | `getCurrentSpeed() / 3.6`; derived from driven wheel rotation, potentially affected by slip |
| Position | world ENU, metres | Supervisor ground truth at robot origin, nominal rear-axle centre; **not CG position** |
| Heading | CCW positive about world +z, radians | `atan2(R[3], R[0])` from row-major body-to-world rotation; body +x is forward |
| True speed | signed body-longitudinal m/s | world linear velocity projected onto heading |
| Yaw rate | rad/s, positive left | Supervisor world angular z velocity |
| Wheel angles | native Webots sensor sign, radians | `left_steer_sensor` and `right_steer_sensor`, separately logged |

Nonfinite steering/speed and negative speed raise errors before driver commands are sent. The harness aborts on an invalid command or nonfinite sample. This is an interface guard, **not** a production fault-response controller. It does not implement asynchronous information-age handling, fallback, LQR, PPO or fusion.

Webots uses Ackermann geometry, not identical left/right angles. With native Driver angle `d`, wheelbase `L` and front track `T`:

```
right = atan(tan(d) / (1 - T*tan(d)/(2*L)))
left  = atan(tan(d) / (1 + T*tan(d)/(2*L)))
```

For adapter +0.03 rad (`d = -0.03`), expected native left/right angles are −0.03027942 / −0.02972569 rad. The negative command swaps their magnitudes/signs. Actual wheel sensors, heading and lateral displacement confirm the conversion. R2025a `driver.c` implements `getSteeringAngle()` as the mean of the two measured steering sensors; the `steering_driver_readback_rad` column is that native-sign mean, **not** the requested virtual-centre angle. We retain requested/applied/API commands and both wheel measurements separately.

## Vehicle parameters: what was verified

The world uses a generic, explicitly configured `Car`, not a Tesla model or independently identified real vehicle. At startup the controller reads runtime PROTO/Physics fields and wheel positions and checks them against `config.json`. Audits are saved for **each** case. The world/config hashes are attached to each audit. No parameter is inferred from a model name.

| Parameter | Configured and inspected in Webots | Relation to specification baseline |
|---|---|---|
| Wheelbase | 2.6 m, front axle x=2.6 and rear x=0 | matches 1.2 + 1.4 m |
| Front/rear track | 1.6 / 1.6 m; wheels y=±0.8 | additional integration assumption |
| Chassis mass | 1,610 kg | excludes articulated wheels |
| Each wheel mass | 10 kg, four wheels | total modeled mass = 1,650 kg |
| Chassis CG | (1.4, 0, 0.2) m relative to robot origin | chassis distances front/rear = 1.2 / 1.4 m |
| Whole-system nominal CG | x≈1.397576 m by static mass weighting | **not exactly** chassis CG; front/rear ≈1.202424 / 1.397576 m; suspension alters vertical geometry |
| Chassis inertia diagonal | (1000, 3500, 4224) kg·m², off-diagonals zero | yaw value is chassis-only; total articulated vehicle inertia is **not 4224** |
| Wheel radius/width | 0.32 / 0.20 m | generic assumptions; wheel inertias generated by Webots from geometry/mass |
| Tire/road friction | Coulomb coefficient 0.9 | numeric candidate matches, but tire law does not |
| Suspension springs | 100,000 N/m front and rear joint settings | additional assumption |
| Suspension damping | 4,000 N·s/m front and rear joint settings | additional assumption |
| Wheel joint damping | 5 in Webots `wheelsDampingConstant` | simulator assumption |
| Steering motor limits | ±0.6 rad at individual wheels | distinct from adapter virtual-centre limit ±0.5 rad; large-angle calibration untested |
| Body collision box | 3.8 × 1.5 × 0.5 m, centred at (1.3, 0, 0.35) | generic shape, not measured vehicle body |

The chassis yaw inertia plus wheel offsets alone already exceeds the specified whole-vehicle yaw inertia. We **did not** silently label this surrogate dynamically equivalent to the manuscript bicycle. Webots contact/suspension and velocity-controlled wheel motors are used. No Fiala tires or calibrated per-axle 80,000 N/rad cornering stiffness are implemented or verified. The speed-mode drivetrain is suitable for this interface test, not an identified engine/traction model. This is a recorded parameter mismatch, not a primary-model change.

## World, schedule, logging and acceptance criteria

Flat static 200 × 100 m surface, ENU axes, random seed 42; a fresh process reloads the same world for each case. Webots physics/basic step and controller period are both **10 ms**. This differs from the primary specification's candidate **1 ms plant integration**; convergence and high-speed equivalence are untested.

Two stationary initialization steps (20 ms) establish valid wheel-speed sensor history. Test time starts at absolute simulation t=0.02 s. During test seconds 0–2 the speed target is zero; from second 2 it is 5 m/s. Steering is zero until test second 6, then 0 / +0.03 / −0.03 rad for straight / left / right. Each run contains 1,200 logged control intervals over 12 test seconds. State samples run from simulation t=0.03 to 12.02 s.

A command logged at `t_command_s` is applied before stepping; its resulting state is logged at `t_state_s = t_command_s + 0.01`. `t_test_s` is the command's time relative to the post-warmup origin. All are **simulation-clock seconds**, not wall time or inference timestamps. There is no inference worker here. CSV columns also include step index, requested and saturated steering, native API steering command, target speed, both speed measurements, xyz position, heading, yaw rate, native Driver steering readback and both wheel-angle sensors. The Driver wheel-speed estimate is the exception to post-step sampling: its implementation updates before the physics step, from wheel samples over `[t_command_s - 0.01, t_command_s]`. Thus `speed_driver_m_s` has one-step older provenance than the post-step true speed; it must not be treated as a simultaneous ground-truth sensor. State is noiseless Supervisor ground truth for interface validation; no claim of deployable sensing is made.

Acceptance thresholds are development smoke-test criteria defined in `config.json`, not scientific stability/safety bounds:

- Exact row count, sequential indices, all-finite values, 10 ms command-to-state and state-to-state intervals, and the configured command schedule.
- More than 30 m forward travel; steady (test t≥8 s) true-speed error below 0.3 m/s.
- Straight maximum lateral displacement <0.1 m and absolute heading <0.01 rad.
- Turn heading >0.15 rad and lateral displacement >1 m in the commanded direction.
- Steady individual wheel-angle error against Ackermann geometry <0.003 rad.
- Steady signed yaw-rate/true-speed curvature within 0.5–1.5 times `tan(delta)/wheelbase`. This loose low-speed check detects units/sign/scale mistakes; it does not identify tire dynamics.

These thresholds were set before the first successful three-case evaluation and were not relaxed to make the runs pass. Steering is a step through the Webots steering motors; the specification's 0.05 s actuator lag and 0.35 rad/s rate limit are **not implemented** in this interface milestone. Only adapter magnitude saturation is present. Raw wheel sensors expose the simulator's actual response.

## Actual results

All three physics cases passed, with **1,200 samples each**. The complete suite passed again in fresh simulator processes; all three repeated CSV files were byte-identical to their baseline counterparts, and their computed summaries matched exactly. This demonstrates repeatability in this instance, not across platforms. The analyzer also rejected deliberately corrupted timestamps and a truncated copy of a run. Four adapter boundary tests passed (SI/sign conversion, both saturation directions, nonfinite/reverse rejection and invalid-limit rejection). CSVs, console logs, configuration, runtime audits and computed summaries are committed under `integrations/webots/results/baseline/` and `results/repeat/`.

| Case | Adapter steering (rad) | Final x (m) | Final y (m) | Final heading (rad) | Final true speed (m/s) | Steady curvature (1/m) |
|---|---:|---:|---:|---:|---:|---:|
| Straight | 0 | 45.484897 | −0.00005969 | 0.00000002068 | 4.998280 | 2.2871e−10 |
| Left | +0.03 | 44.934836 | +4.902508 | +0.33554840 | 4.998313 | +0.01136243 |
| Right | −0.03 | 44.934823 | −4.902627 | −0.33554838 | 4.998313 | −0.01136243 |

Expected low-speed turn curvature magnitude was 0.01154192 1/m; measured/expected ratio was 0.9844485 in both turns. Maximum steady wheel-angle discrepancy was approximately 0.00048837 rad, below 0.003 rad. The straight maximum lateral drift was 0.00005969 m. Wheel-derived speed averaged about 4.98936 m/s while true speed averaged about 4.99831 m/s; they are deliberately not treated as identical measurements.

During initial development the first raw speed sample was nonfinite because Driver differentiates wheel-sensor history. The harness originally rejected it; the explicit two-step stationary sensor initialization resolved this without inventing a zero measurement. A wheel visual-geometry field conflict was corrected in the local world (`rimBeamThickness=0.12`), and auditing was corrected to read the Solid inside the wheel Slot. Those failed preliminary launches are not counted as passing tests. The final console logs have no such errors.

## Limits and next work

This establishes command/state/clock plumbing and low-speed steering direction/scale in a generic simulator vehicle. It does **not** establish tracking accuracy, closed-loop stability, latency robustness, collision avoidance, road compliance or real Tesla parameters. Tests cover 5 m/s and ±0.03 rad only; 15/20/25 m/s, larger angles, braking/reverse, noisy/delayed sensors, actuator parity, tire/CG/inertia calibration, convergence and modified-course feasibility remain unvalidated. No primary experiment, policy training or specification change was made. Shared Webots installation was untouched. No publication, merge or push is implied by this local commit.

Before research transfer, explicitly reconcile the articulated mass/CG/inertia and tire model, add and validate the common actuator/sensing interface, then extend the predefined tests to the intended speed/path envelope. The current results must not be substituted for those later checks.

## Upstream references

- [R2025a Driver library documentation](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/docs/automobile/driver-library.md): steering radians/right-positive and speed km/h.
- [Driver implementation](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/projects/default/libraries/vehicle/c/driver/src/driver.c): steering sensor mean, wheel-speed estimate, stepping order.
- [Car](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/projects/vehicles/protos/abstract/Car.proto), [AckermannVehicle](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/projects/vehicles/protos/abstract/AckermannVehicle.proto), and [VehicleWheel](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/projects/vehicles/protos/abstract/VehicleWheel.proto): geometry, joint axes, physical fields and wheel Slot structure.


## Extended five-seed campaign (24 October 2026 UTC)

The authorized extension is complete in the same isolated worktree. It adds its own Fiala surrogate, LQR, full-command PPO, residual PPO and supervised fusion under `integrations/webots/research/`; the primary model, phase-1 experiments, existing training pipeline and specification remain unchanged. The private Webots installation is reused without altering shared installations.

The [reproduction guide](../../integrations/webots/research/README.md) gives installation, training and simulator commands. The [generated results report](../../integrations/webots/results/research-core/report.md) contains measured tables; [campaign verification](../../integrations/webots/results/research-core/campaign-verification.json) verifies checkpoint step counts, seeds, hashes, complete evaluation coverage and physical evidence.

Actual final commands (from this worktree, with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` and private writable Numba/Matplotlib cache directories):

```bash
bash integrations/webots/install-research.sh
# Actual campaign interpreter: /workspace/lans-setup/venv/bin/python (Python 3.10.22).
# The separately tested reproducible installation provides the same pinned core packages:
export LANS_PYTHON="$PWD/integrations/webots/.runtime/research-venv/bin/python"
bash integrations/webots/research/run-final-training.sh
"$LANS_PYTHON" integrations/webots/research/evaluate.py --wait-for-training --training "$PWD/integrations/webots/results/research-training" --output "$PWD/integrations/webots/results/research-evaluation"
"$LANS_PYTHON" integrations/webots/research/run-physical.py --suite development --output "$PWD/integrations/webots/results/physical-validated"
"$LANS_PYTHON" integrations/webots/research/run-physical.py --suite tracking --output "$PWD/integrations/webots/results/physical-tracking-final"
"$LANS_PYTHON" integrations/webots/research/run-physical.py --suite transfer --output "$PWD/integrations/webots/results/physical-transfer-final"
"$LANS_PYTHON" integrations/webots/research/analyze-physical.py
"$LANS_PYTHON" integrations/webots/research/verify-campaign.py
"$LANS_PYTHON" integrations/webots/research/report.py
```

These result directories already contain evidence; use new output paths when rerunning evaluation or Webots. Training retains verified completed checkpoints; provide a fresh first argument for retraining. See the guide for explicit evaluation paths. The development suite preceded the analytical tracking correction; only its nine open-loop and three convergence cases enter the final physical audit. Its older LQR cases are retained as history; the nine corrected cases in `physical-tracking-final` supply the final table.

Ten final policies (two roles, seeds 0–4) each completed 1,000,000 steps: **10 million final training steps**. The 810 paired surrogate episodes cover six methods, five seeds, three speeds, three known paths and three service delays. Survival counts out of 135 are LQR 135, PPO 87, residual 135, fusion 134, no-supervisor 134 and fixed-weight 89. Mean failure-penalized RMSE is respectively 0.0640, 0.8652, 0.0749, 0.0924, 0.0935 and 0.8198 m. LQR is strongest on this comparison; completing training does not establish PPO convergence or superiority.

All 45 native Webots policy-transfer cases survived: 15 full PPO, 15 asynchronous fusion with zero added delay and 15 fusion with 100 ms added minimum delay. Their mean RMSEs are 0.0897, 0.0853 and 0.0769 m. At 100 ms, fusion spends 100% of the run in LQR fallback; this validates rejection of stale output, not useful delayed PPO control. All nine corrected LQR cases survived, including noisy and 10 ms delayed sensor cases at 15/20/25 m/s. Nine straight/small-steering cases and three timestep convergence cases passed the physical audit. Four original adapter tests, five research contract tests, original baseline/repeat analyses, numerical checks and the real-process worker contract passed.

### Parameter, actuator and sensor validation

The research world has composite mass 1,650 kg, wheelbase 2.6 m, CG 1.4 m ahead of the rear axle, nominal yaw inertia 4,224 kg·m² and wheel radius 0.32 m. These are audited from the generated world including wheel contributions. Steering remains positive-left radians with the native Driver sign negated. Research position is transformed to nominal CG, unlike the original rear-origin logs. CSVs include commanded and actual steering, speed, CG position, heading, state/control/observation/availability simulation times and separate worker wall timestamps.

Explicit steering dynamics use ±0.5 rad, 0.35 rad/s and a 0.05 s first-order lag, with 1 ms physics and 10 ms control. Native motor PID is configured in each private test world/controller to avoid adding an unintended second slow actuator. Separate step evidence is retained in `results/actuator-parity`; measured wheel/actuator differences were below 1e-5 rad. Sensor noise enters before a common Kalman estimate, with delayed measurement queues tested for true-state leakage. Encoder/map previews are not delayed or noised by the four-channel sensor stress.

Native force-dependent contact slip is speed-conditioned and separately calibrated front/rear. At 15/20/25 m/s measured effective front stiffness is 83.2/84.4/85.1 kN/rad and rear is 75.9/75.4/75.1 kN/rad, within the declared 15% tolerance around 80 kN/rad. This does not make Webots contact physics equivalent to Fiala tires. The tested quintic 125 m course fails the 0.8 μg acceleration margin; the explicitly different 220 m development course passes at all three speeds. Neither is presented as ISO certification.

### Development history and limits

Development exposed noisy finite-difference feedback, overly aggressive R=4 feedback, overly stiff native contact, extra native servo lag and an Xvfb reset race. A common Kalman estimator, development-selected R=100, calibrated contact materials, explicit actuator parity and an Xvfb readiness/no-reset wrapper addressed these before the final runs. The original negative reward encouraged early termination; the final profile restarts both roles with a bounded positive survival reward and initial log standard deviation −2.

An analytical curvature-equilibrium correction subsequently removed the LQR baseline's erroneous zero lateral-velocity/yaw reference. Full-command training never uses LQR in its action or reward and was unaffected; all final residual policies were retrained with the corrected reference. Four concurrently produced preliminary evaluation rows were excluded and final evaluation used fresh noise seeds starting at 20000. Four full-policy metadata writers had failed after successful model saves; recovery verified each saved model's million-step count, seed and hashes without changing weights. Their wall-time metadata explicitly ends at the last rollout. Source snapshots and protocol hashes preserve these distinctions; partial development models are not final evidence.

Known path geometries are reused; only noise realizations are held out. PPO has curvature previews while LQR uses local curvature. Training is synchronous, with frozen asynchronous deployment; it does not implement every tentative latency-training provision of the specification. Surrogate service delays are simulated scheduling, whereas Webots fusion runs a real separate inference process. CPU-contended wall timing is not a real-time guarantee. Corridor checks use a sampled vehicle footprint in a vertical strip, not continuous swept-volume or ISO geometry. Nonlinear tire equivalence, unseen-path generalization, real-vehicle safety and formal stability remain unvalidated.

## Revision 2: LQR-default performance-aware gating

A separately authorized development revision replaces default PPO authority with an earned contribution. It lives under `integrations/webots/research/revision2/` on branch `webots/performance-gated-revision`. All original campaign evidence and policy checkpoints are unchanged. The specification is also unchanged: this is an intentional experimental architecture deviation, not a silent rewrite of its proposed PPO-dominant requirement.

The [revision guide](../../integrations/webots/research/revision2/README.md) gives exact cost, actuator prediction, gate logic, development/test splits and commands. The gate predicts the **actual fused/ramp-limited command** against LQR, from the common estimated state. It starts at zero weight, rejects stale/invalid/out-of-envelope output, requires three qualifying ticks and restores weight gradually. Residual candidates have an explicit ±0.08 rad correction bound before complete-command saturation. Predicted improvement is necessary for activation but does not guarantee realized benefit under model mismatch.

The three predeclared horizon/margin candidates were tested in 96 development episodes. The development selection rule chose a 200 ms horizon and 1% relative cost margin; all three candidates met development survival/nominal constraints. Source, policy and configuration hashes were frozen in commit `c966bb26a190be288c38efffc0498ac2c11f63ac` **before** running the reserved split. Five existing training seeds are reused without retraining; new noise seeds use base 910000, disjoint from development base 310000 and the original campaign. Path geometries are known, so this is not unseen-path generalization.

The reserved grid contains five methods × five policy seeds × three speeds × two paths × six regions = 900 episodes. Regions are nominal, tire stiffness ×0.65, friction 0.6, doubled sensor noise with 10 ms measurement delay, 20 ms service delay and 100 ms service delay. All methods share each condition's random stream and actuator physics. The primary comparison is gated residual versus LQR; gated full-command, old fusion and ungated residual are reported as secondary comparisons. Region advantage was defined before testing as ≥5% mean penalized RMSE reduction, all five paired seed-mean differences negative and no survival loss. Nominal preservation permits ≤2% increase with no survival loss. All regions are reported, including failures and negative findings; confidence intervals are descriptive and not multiplicity-adjusted.

Six gate/plant contract tests passed, including exact nominal parity with the previous nonlinear plant. The new controller is evaluated in the isolated surrogate only. Native Webots transfer of this new revision remains unvalidated; the previous section's 45 native runs apply only to the previous controller. No new shared installation or primary model changes were made.

### Revision 2 reserved results

The [complete results and verification](../../integrations/webots/results/revision2-test/report.md) cover **900/900 completed episodes**, all survived (180 per method). Gated residual versus paired LQR produced:

| Region | LQR RMSE (m) | Gated residual RMSE (m) | Relative change | Better seed means / 5 |
|---|---:|---:|---:|---:|
| Nominal | 0.062320 | 0.060475 | −2.96% | 5 |
| Tire stiffness ×0.65 | 0.175013 | 0.172810 | −1.26% | 5 |
| Friction 0.6 | 0.080833 | 0.079308 | −1.89% | 5 |
| Doubled noise + 10 ms sensor delay | 0.061571 | 0.060332 | −2.01% | 5 |
| 20 ms service delay | 0.062804 | 0.061098 | −2.72% | 5 |
| 100 ms service delay | 0.063067 | 0.063067 | 0.00% | 0 (exact equality) |

Since every trajectory survived, failure-penalized and ordinary RMSE coincide here. Nominal preservation passed. **No region met the predeclared ≥5% clear-advantage criterion.** Improvements of roughly 1–3% are consistent across five paired seed means in the first five regions, but their absolute scale is only about 1–2 mm in aggregate RMSE; do not describe them as a large practical advantage. At 100 ms the gate's learned contribution was zero, with exact paired LQR trajectories verified.

Nominal learned authority was active for 12.34% of ticks with mean weight 0.0354, compared with the old fusion's 99.23% activity and mean weight 0.6815. This demonstrates the intended selective-authority behavior. The gated full-command secondary comparator was slightly better than gated residual in the first five region means, so these results do **not** establish residual gating as the superior architecture. All secondary methods and descriptive paired confidence intervals remain visible in the report.

The gate and weights were not retuned after the reserved results. The present result supports nominal accuracy preservation and modest selective improvement, not the stronger publication claim requested. Any further disturbance-aware policy training or predictor revision needs a new development protocol and another untouched test split; native transfer validation is also outstanding for this revision.

## Frozen revision-2 native Webots transfer

The user authorized transfer of the unchanged performance-aware gate after reviewing commit `14ab389`, explicitly prohibiting retuning. Branch `webots/frozen-gate-transfer` adds a separate native controller and harness. It directly imports the existing gate and verifies the original development freeze, source and policy hashes. Neither the original 810-episode campaign, revision-2 900-episode surrogate campaign, trained weights, gate implementation nor specification is changed.

The [native protocol and reproduction guide](../../integrations/webots/research/revision2/native/README.md) document all commands and interfaces. Three separate-seed smoke cases passed before the native protocol/interface freeze commit `65099e1b73385e68b347f42b20ba92dacc902a83`. The reserved grid is 270 native process launches: five policy seeds × three speeds × six conditions × three methods. Gated residual is primary; gated full-command is a predeclared secondary comparator. New native noise streams use base 1910000, paired across methods. No new PPO training is performed.

Native conditions are nominal, contact softening, lower friction, doubled sensor noise plus 10 ms delay, and 20/100 ms minimum worker-output delays. The native mismatch maps to increased force-dependent slip; it is **not** a verified exact 35% tire-stiffness reduction. Native testing uses the known DLC220 course only. Both learned roles use the existing real separate inference process with one job in flight and dropped busy submissions. LQR has no worker. Two Webots instances share cloud CPU capacity, each with private display/configuration directories; actual command ages and wall timing are retained and no real-time guarantee is claimed.

The unchanged 200 ms/1% gate predicts from the common noisy estimate, measured wheel-angle proxy and local curvature, without access to hidden contact parameters. The existing native explicit 1 ms actuator implementation, mass/CG/inertia audit, steering sign, speed conversion and 10 s physical warmup are retained. Native dynamics, actuator integration and initial lateral offset differ from the surrogate; transfer checks those differences rather than claiming equivalent plants.

The analyzer reads all raw CSVs, recomputes scores, checks clocks, angle/rate limits, cost-improvement activation, frozen hashes and complete case coverage. Severe-delay checks separately verify zero learned authority, local LQR command equality and exact full paired physical/control trajectories. Any nonzero field differences remain visible. Statistical reporting keeps all regions and both learned modes, aggregates paired differences at seed level, and retains the original 2% nominal-preservation and 5% clear-advantage criteria without post-test adjustment.

### Native reserved results

The [native results report](../../integrations/webots/results/revision2-native-test/report.md) and [raw-data verification](../../integrations/webots/results/revision2-native-test/verification.json) confirm **270/270 survived**, or 90/90 for each method. Gate/policy/source hashes, vehicle audit, command/rate limits, cost-acceptance rules and complete unique case coverage passed. All 30 severe-delay gated runs have zero learned authority and **exactly equal paired LQR physical/control trajectories** across all checked fields, not merely equal aggregate RMSE.

| Native region | Gated residual RMSE change vs LQR | Better residual seed means / 5 | Gated full-command RMSE change vs LQR | Better full seed means / 5 |
|---|---:|---:|---:|---:|
| nominal | -1.29% | 5 | -0.59% | 4 |
| contact_softening | -0.21% | 5 | +0.20% | 2 |
| low_friction | -1.31% | 5 | -1.29% | 4 |
| sensor_stress | -0.97% | 5 | +0.34% | 3 |
| latency20 | -0.91% | 5 | -0.61% | 4 |
| latency100 | +0.00% | 0 | +0.00% | 0 |

Negative change favors the hybrid. Gated residual improves all five paired seed means in the first five regions, while severe delay is exact LQR fallback. Nominal preservation passes. **No native region reaches the frozen ≥5% clear-advantage criterion.** Absolute primary mean RMSE reductions are approximately 0.35–1.15 mm; these are small effects and should not be described as a large practical advantage. Descriptive paired confidence intervals remain visible in the report; multiple-comparison significance is not claimed.

Full-command gating is mixed in native transfer, with slight average regressions under contact softening (+0.20%) and sensor stress (+0.34%). Its stronger surrogate means therefore do not establish native architecture superiority. Both modes retain their distinct frozen candidate/action bounds, and actual worker schedules vary under CPU contention; this is not an isolated architecture-only ablation.

The supported native claim is: “On the tested native Webots DLC220 grid, the unchanged performance-gated residual controller reduced mean tracking RMSE relative to paired LQR across nominal, contact-softening, low-friction, sensor-stress and moderate-delay conditions for all five seed means, and reproduced LQR exactly under the severe-delay test.” This is conditional confirmation of modest transfer, not broad controller superiority, unseen-path performance or real-vehicle safety.

The 100 ms condition is an added minimum availability delay; held-output ages have a mean per-run p99 of 190 ms while the next inference is in flight. Zero-added-delay gated runs also show nonzero ages. Simulation age and measured inference duration are separate quantities. No gate or policy changes were made after observing these native results. The original surrogate and native evidence remains unchanged.

## Revision 3: pilot-selected, range-matched residual training

The user identified that the earlier residual training action is normalized output ×0.50 rad, whereas the frozen gate clips candidate residuals to ±0.08 rad. Revision 3 aligns the candidate range in training and deployment at normalized output ×0.08 rad. It reuses the original environment through an explicit action adapter, preserving old training code, checkpoints, gate and all earlier results. This does **not** eliminate the remaining deployment mismatch: training applies the residual directly, while the gate can reject/weight/delay it.

The user then requested short training comparisons before choosing a full-training configuration. The initial direct full runs were stopped at their last recorded 530k-step progress points for four seeds; no completed policy checkpoint or reserved evaluation episode existed. Partial logs/snapshots are preserved locally and the interruption is recorded in `research/revision3/interrupted-run.json`. These incomplete runs are not used for model selection or represented as final training.

The pilot protocol was frozen at `bbb010cfcef75a91e535c408c5b5ad4e76c13841`: four configurations × two distinct training seeds ×100k steps =800k pilot steps. Candidate range and gate stayed fixed while comparing the baseline, lower initial exploration, sharper tracking reward and a larger network. Each configuration received 72 paired development episodes covering three speeds, two paths and six regions; an additional 72 LQR episodes supplied the common reference. Training reward was not the selection metric.

| Pilot candidate | Survived / 72 | Mean penalized development RMSE (m) | Eligible |
|---|---:|---:|---|
| Baseline [64,64], log std −2 | 72 | 0.083973 | Yes |
| Low exploration, log std −3 | 72 | 0.084256 | Yes |
| Sharper tracking reward | 72 | 0.084322 | Yes |
| Larger network [128,128] | 72 | 0.084234 | Yes |

All candidates satisfied the predeclared survival and ≤2% nominal-degradation constraints. The **baseline** had the lowest mean development RMSE and was selected mechanically. The differences are small; two short-run seeds do not establish a statistically superior or globally optimal configuration. The complete [pilot ranking and selection manifest](../../integrations/webots/results/revision3-pilots/report.md) are retained. That preliminary selection was committed at `85ed49dc14aa8ce69d6c9e7d47d6b83ecdce4d87`. The user subsequently required an extended top-two comparison because the gap was only0.31%; the restarted full jobs were stopped before any completed checkpoint or reserved result. The extended checkpoint below supersedes that preliminary selection.

Planned, unrun final testing uses fresh noise base4910000, disjoint from pilot development. It compares LQR, historical gated residual, historical policy merely rescaled to ±0.08, selected retrained gated residual, and retrained ungated residual with the existing age decay. All900 cells are predeclared. This separates retraining from a simple decoder change. The gate is not retuned using these results.

The [revision guide](../../integrations/webots/research/revision3/README.md) provides exact commands, sources, budget and decoding requirements. Four contract tests passed for range endpoints/nonfinite rejection, inherited dynamics/reward parity, matching evaluator/worker units, and gate fallback/range behavior. Native inference uses a new adapter around the unchanged worker/controller, verifying model metadata and converting its historical ×0.5 encoded output exactly once to ×0.08. Five native interface/range checks are prepared but have not run; they would not replace a paired native performance campaign for the new policies.

### 300k extended-pilot checkpoint (awaiting user decision)

The close top two were continued from their **same saved100k checkpoints**, for200k additional steps each, reaching300k at seeds101/202. All four Adam optimizer counters advanced from5000 to15000, and reward-normalization sample counts advanced from100000.0001 to300000.0001. The [continuation and raw-grid audit](../../integrations/webots/results/revision3-extended/continuation-audit.json) verifies this provenance and all360 paired development episodes. All360 survived; each candidate survived72/72.

| Region | Baseline [64,64] RMSE (m) | Larger [128,128] RMSE (m) |
|---|---:|---:|
| nominal | 0.062542 | 0.062403 |
| tire_mismatch | 0.174915 | 0.175226 |
| low_friction | 0.081674 | 0.081830 |
| sensor_stress | 0.061249 | 0.061250 |
| latency20 | 0.062124 | 0.062321 |
| latency100 | 0.062871 | 0.062871 |

Overall mean RMSE: baseline **0.084229 m**, larger network **0.084317 m**. The baseline advantage is only **0.104%**, approximately0.088mm in aggregate RMSE. Seed101 favors the larger network (0.084526 vs0.084565m); seed202 favors baseline (0.083894 vs0.084108m). Neither meets the frozen clear-winner rule. Both preserve nominal performance and survival. Baseline is slightly better in four active regions; larger is slightly better nominally. Baseline sensor-stress RMSE is still about0.37% worse than LQR, so it does not dominate LQR in every region.

The old gated model reference averages0.082919m, old merely rescaled gated model0.084201m, and LQR0.084428m. The300k new baseline is approximately tied with the old-rescaled reference, so a distinct retraining benefit has **not** been demonstrated at this checkpoint. Old reference models have1M steps and different training seeds; these anchors cannot establish equal-budget superiority or failure.

The user’s latest tie-break favors the simpler baseline when differences remain below1%, while explicitly reserving the full-training decision for their review. Accordingly the recommendation is **baseline for simplicity, not a proven performance winner**. Full training remains paused, no new1M model completed, no final reserved episode ran, and no new-policy native run was executed. No further configuration search is performed after this checkpoint. The complete [extended results](../../integrations/webots/results/revision3-extended/report.md) retain all regional references and criteria.

Continuation caveat: the source intended a fresh constructor seed offset, but SB3 `PPO.load` seeds the vector environment from `model.seed+i`, overriding that default. The audit records this discrepancy. Policy, optimizer and normalization continue; environments restart with the same treatment for both candidates. These are not uninterrupted300k trajectories. Frozen source/protocol snapshots remain unedited; the report includes the observed seeding correction.
