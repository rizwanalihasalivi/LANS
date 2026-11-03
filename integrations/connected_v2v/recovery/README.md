# Independent range fallback and V2V recovery v2

Subsequent separate stage: [formation recovery v3](../formation/RESULTS.md).
The v2 controller, protocol and evidence remain unchanged.

[Executed results](RESULTS.md) · [Predeclared protocol](PROTOCOL.md) · [Figure](evidence/recovery-v2.png)

This version adds independent local range/range-rate evidence to bridge V2V
blackouts. It preserves the original law and supervisor, original observation
timestamps, per-source replay checks and physical limits. Radar-ACC is a matched
local-sensing baseline. With both sources unavailable, stale ego or disagreeing
fresh sources, the vehicle brakes. No knowledge is fabricated from a scoring state.

`controller.py` supplies immutable `RangeObservation` and `FusionFollower`.
`v2v_only` masks local range data, `radar_acc` masks radio control inputs, and
`fusion` selects validated knowledge with original timestamps. Source switching
does not clear either source's replay watermark. Straight-road reconstruction
and ideal target association are explicit limitations, not hidden sensor access.

`retarget()` is a trusted explicit platoon membership command. It preserves
actuator command continuity and real-source replay caches; it is never inferred
from packet silence. The common cut-in/out scenario supplies this same event to
all methods. It is not autonomous neighbor identification. Original V2V registries
keep their historical contacts; the scoped following controller evaluates its
explicit current predecessor, not arbitrary multi-lane traffic.

## Reproduce in the existing checkout

Use `/workspace/LANS`, Python 3.10 and the prepared LANS environment. No worktree,
new training, paid service or secret is needed. All output roots must be NEW.
Changing a frozen input blocks reuse; preserve old evidence rather than reset it.

```bash
source /workspace/lans-setup/env.sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m pytest -q integrations/connected_v2v/recovery
python -m integrations.connected_v2v.recovery.campaign prepare --output results/my-recovery-v2
python -m integrations.connected_v2v.recovery.campaign development --output results/my-recovery-v2
# Only after all development gates pass; this launcher proves serial/parallel
# deterministic equivalence, then runs the fixed confirmation grid with 3 workers.
python -m integrations.connected_v2v.recovery.execution.parallel --study results/my-recovery-v2
# Optional full read-only receiver/control/physics and gate recheck:
python -m integrations.connected_v2v.recovery.campaign verify --output results/my-recovery-v2 --stage development
python -m integrations.connected_v2v.recovery.campaign verify --output results/my-recovery-v2 --stage confirmation
# Native stage checks BOTH Python gates. It never opens main-PPO reserved data.
bash integrations/webots/install-private.sh
python -m integrations.connected_v2v.recovery.native.run --study results/my-recovery-v2 --output results/my-native-recovery-v2
```

The serial `campaign confirmation` command is also supported. Do not run serial
and parallel writers into the same confirmation root. Episodes are independent
logical-time trials with local seeded RNGs, not asynchronous timing benchmarks.
Completed verified cases can be cached by the serial runner; partial folders
are not silently overwritten or claimed as exact interrupted-run continuation.

Native transfer uses an independently generated project/controller without
editing the old v1 project. It reads native Radar/GPS/IMU/gyro/speed data and
Emitter/Receiver bytes, not other robots' Supervisor truth. The same frozen
FusionFollower class handles all three ablations. See [native protocol](native/PROTOCOL.md)
for geometry, nearest-target assumptions, actuator adapter and sample cadence.

The [evidence archive](evidence/recovery-v2.zip) contains raw/native data, the
full source freeze, verification and generation scripts; it does not vendor
runtime binaries. Reproduce exact archived episodes using their source/config
snapshots. Do not mutate or retune held-out confirmation data.

For a standard-library-only independent scoring check, use:
```bash
python -m integrations.connected_v2v.recovery.reporting.independent_metrics results/my-recovery-v2
```
It imports no controller/model/report helper and verifies spacing, progress,
collision/freshness/bounds and command jerk against all raw episodes. Executed
speed-derived jerk is an additional descriptive metric, not a changed gate.
