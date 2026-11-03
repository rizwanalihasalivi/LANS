# Executed development results — 3 November 2026

The first observation-driven target-selection version is implemented and tested
locally on `experiments/python-validation-v2`, starting at
`106f1ea8625ccf696379fa47613558350201bea5`. These are development checks of the
new module, not a final comparison, confirmation campaign or thesis benchmark.
No new Git commit or push is represented by this report.

## Final-source checks

| Check | Executed result |
| --- | --- |
| Complete connected-V2V pytest suite | **122 passed** |
| Python development grid | **40/40 passed**, 16,000 ego control ticks |
| Native Webots grid | **12/12 passed**, 21,600 vehicle samples |
| Controller/input/physics replay | Passed for every applicable final episode |
| Independent stdlib scoring and sender-wire audit | Passed for both final grids |
| Negative audit checks | Altered Python aggregate and native wire state rejected |
| Pinned Python dependency consistency | Passed |
| Repeat installation | Passed; archive/PROTO checksums and signed apt indexes retained |

The final Python output is `results/autonomy-dev-v3`; the final native output is
`results/autonomy-native-v5`. In both grids, sampled oriented-box overlap counts,
requested command-bound violations, stale selected-source use and failure to
brake while selection was uncertain were **zero**. All episodes demonstrated
observation-driven intervening-vehicle acquisition and later return to the leader.
These sampled model checks do not establish physical collision-free safety.

Python also had zero route-corridor violations. Native verification checked all
three cars' pose, height, tilt and map envelopes, replayed every follower command
and speed setpoint, and required movement. Actual native acceleration from the
speed servo is not asserted to equal the requested bounded acceleration.

| Python development case | Seeds | Passed |
| --- | --- | --- |
| Connected cut-in/out | 101, 203, 307, 409, 503 | 5/5 |
| Non-connected cut-in/out | same five | 5/5 |
| Curved route, radius 500 m | same five | 5/5 |
| Dense two-lane traffic | same five | 5/5 |
| V2V blackout | same five | 5/5 |
| Dual blackout | same five | 5/5 |
| Packet loss/jitter/duplicates | same five | 5/5 |
| Delayed radar, 150 ms | same five | 5/5 |

| Native two-lane maneuver case | Seeds | Passed |
| --- | --- | --- |
| Connected cut-in/out | 42, 73, 109 | 3/3 |
| Non-connected cut-in/out | same three | 3/3 |
| V2V blackout during following | same three | 3/3 |
| Dual blackout during following | same three | 3/3 |

Python episodes last 20 s; native episodes last 30 s. The follower receives no
target labels or switch schedule in either platform. NPC maneuvers and sensor
generation/scoring fixtures remain scripted. Native input is real Webots
Radar/GPS/IMU/Gyro and Emitter/Receiver data, without reading other robots through
Supervisor truth. Non-connected native intruders emit no V2V messages.

## Retained failures and corrections

- `autonomy-dev-v1`: 40 trials, **6 failed** (four non-connected and two loss/jitter
  seeds had sampled box overlap). Catch-up consumed braking distance before the
  adjacent vehicle's lateral intent was observable. An analytical stopping-distance
  guard over all nearby forward observations fixed this failure in development.
  Original failed raw data and source are preserved.
- `autonomy-dev-v2`: all 40 passed after that guard. Final review added a stricter
  unknown-target ordering rule: a newer peer being nearer than the old **historical**
  gap cannot release an unseen old target. A regression test covers it; the full
  final-source grid was rerun as v3.
- `autonomy-native-v1`: launch blocked by sandbox X11 sockets; no native behavior
  claimed. The supported execution permission resolved the environment issue.
- `autonomy-native-v2`: initial Radar speed was non-finite; the first adapter raised
  instead of marking the scan incomplete. This attempt is invalid/incomplete.
- `autonomy-native-v3`: full trace exposed mirrored bearing conversion and missing
  lateral-velocity sensing; pose validation rejected it. It is invalid evidence,
  preserved with its generated controller and source freeze.
- `autonomy-native-v4`: all 12 passed after the native adapter corrections. After
  the final unknown-target ordering safeguard, all 12 were rerun as v5.

Development seeds were reused for diagnosis and regression, so they are **not**
held-out confirmation evidence. No frozen prior confirmation data was used.

## Evidence and reproduction

The [Python/source archive](evidence/autonomy-python-final.zip),
[native archive](evidence/autonomy-native-final.zip), and
[development history](evidence/autonomy-development-history.zip) retain raw inputs,
trajectories, per-run verification, source freezes and invalid attempts.
[SHA-256 checksums](evidence/SHA256SUMS) cover the archives. The Python archive also
includes the final reviewable module, installed-package versions, setup recipe,
independent-audit results and this report. Runtime binaries are installed separately
from the repository-pinned Webots release; they are not vendored into evidence.

Fresh-directory commands and model/perception limits are in [README.md](README.md).
The stdlib auditor can also run directly from the archived source without importing
the controller or NumPy. The final evidence archives were extracted and audited
again to verify their contents are usable.

Remaining work: native curved/dense traffic, wider maneuver/speed distributions,
realistic perception and occlusion, larger independent validation and confirmation
campaigns. **Final comparison and thesis benchmarking remain on hold.**

The cloud configuration draft contains the tested installation script, startup
instructions and exact baseline checkout. Saving the draft did not publish it;
fresh-task restoration has not been independently tested.
