# Webots vehicle adapter validation

Date: 24 October 2026 (Asia/Shanghai). Scope: secondary simulator interface validation only, following `specification-v0.1.md`; no claim of research-controller transfer, vehicle calibration or safety validation. Work is isolated on branch `webots/vehicle-validation`, worktree `/workspace/LANS-webots`, based on `de7b4a2`. Only `integrations/webots/` and this document are changed. The primary model, `experiments/phase1/`, PPO training and specification are untouched.

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
