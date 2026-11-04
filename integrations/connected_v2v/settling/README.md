# Formation settling, 150 m recovery and continuous 2-D trace verification

This stage completes the previously identified simulation research items within
the [operating envelope](OPERATING_ENVELOPE.md). Previous controllers and evidence
are preserved. Final comparative benchmarking remains on hold.

## Controller changes

`SettlingFollower` keeps the existing message TTL/replay checks and positive
departure rule. Normal approach retains conservative adjacent-traffic guarding.
Observed positive departure enables lane-aware catch-up; measured2 s spacing/
relative-speed settling ends it. A measured cut-in restores normal mode. Lateral
prediction can brake immediately but does not declare target membership. Anonymous
near-boundary membership needs distinct confirmations, preventing one noisy
adjacent return from becoming a permanently missing predecessor.

Fresh uniquely matched cooperative observations can anchor subsequent peer
association after the old local track expires. The chain is association/exit-only:
every contributing observation keeps its original timestamp and0.2 s lifetime.
It never becomes fresh local radar or nominal following state. All unobservable
selected-target cases still brake. The approach/recovery transition uses observed
events, not maneuver times or fixture target IDs.

The head paces from its own state and RECEIVED member beacons. Beyond60 m reserve
gap, it reduces the goal by at most4 m/s. Routing prioritizes configured head/member
roles2:1 under one original-byte forward/100 ms and0.25 s original age. This group
configuration does not script ego's selected predecessor. Direct radio remains150 m.
Frenet steering removes the short Cartesian graph restriction on circular roads.

## What is verified

- 70 s frozen Python and native Webots cohorts with independent new seeds.
- Continuous2 s correct fresh return; confirmed settling onset by60 s; final5 s
  spacing/speed/identity gates; head cruise restored; meaningful progress.
- Original source/freshness/duplicate semantics, original-byte forwarding budget,
  causal member-beacon pacing and actual native sensor sourcing.
- [Continuous2-D trace certificates](THEORY2D.md), independent of selected target
  labels, under declared body/pose/acceleration/yaw bounds. Native10 ms motion logs
  qualify sampled dynamics without assuming requested acceleration is actual.
- Deliberately unreachable150 m diagnostics retain FAILED ordinary recovery and
  demonstrate expected braking. A safe stop is not a recovery success.

The2-D proof is **a posteriori finite trajectory certification**, not prospective
invariance of every future action of the whole controller. The earlier1-D
inductive reference proof stays separate. Hardware, authenticated identities,
hard deadlines, comfort, string stability and arbitrary hidden intrusions are not
established. Read the model/claim boundaries before using result numbers.

## Reproduce without changing evidence

Use the existing isolated `/workspace/LANS`; no worktree or hardware is required.
The prepared environment contains Python3.10.22, scientific dependencies and
z3-solver4.13.3.0. Use NEW output roots; never overwrite/resume partial campaigns.

```bash
cd /workspace/LANS
source /workspace/lans-setup/env.sh
export MPLCONFIGDIR=/workspace/LANS/.matplotlib-cache
python -m pytest -q integrations/connected_v2v
python -m integrations.connected_v2v.settling.study --output results/new-settling --stage development
python -m integrations.connected_v2v.settling.native --python results/new-settling --output results/new-settling-native --stage development
python -m integrations.connected_v2v.settling.audit results/new-settling --stage development
python -m integrations.connected_v2v.settling.audit results/new-settling-native --native --stage development
python -m integrations.connected_v2v.settling.verify_inputs results/new-settling --stage development
# Open validation only after both development grids and checks pass.
python -m integrations.connected_v2v.settling.study --output results/new-settling --stage validation
python -m integrations.connected_v2v.settling.native --python results/new-settling --output results/new-settling-native --stage validation
python -m integrations.connected_v2v.settling.audit results/new-settling
python -m integrations.connected_v2v.settling.audit results/new-settling-native --native
python -m integrations.connected_v2v.settling.certify results/new-settling --output results/new-python-certificates
python -m integrations.connected_v2v.settling.certify results/new-settling-native --native --output results/new-native-certificates
python -m integrations.connected_v2v.settling.negative_checks --python results/new-settling --native results/new-settling-native
python -m integrations.connected_v2v.settling.report --python results/new-settling --native results/new-settling-native --output results/new-settling-report
```

Native commands start/check/stop Webots/Xvfb per experiment and need supported
execution permission for X11 sockets when sandboxed. Preserve proxy/TLS and pinned
runtime/PROTO checksums. No persistent server or secret is required.

Published seeds are for reproduction only. Runtime changes after validation opens
require new development roots and genuinely fresh validation seeds. The complete
failed development grid and exploratory probe histories are retained; exploratory
probes were not claimed as source-frozen confirmation. See [PROTOCOL.md](PROTOCOL.md).

Initial broad approach guarding is retained. After an observed cut-in, three
distinct fresh unblocked source observations establish following before allowing
the lane-aware guard; repeated ticks on one stamp do not count. New target
selection resets that confirmation. This prevents adjacent traffic from causing
unnecessary prolonged stops after the actual predecessor has been admitted.
Missing target knowledge still brakes. All amendments/failures are in PROTOCOL.md.

The final ordinary profile grid uses new scenario/stream combinations at the
9001-series seeds;9001 also names a separate deliberately unreachable diagnostic
with different geometry and RNG domains. That diagnostic was never used to tune
the ordinary profile behavior. Each native confirmation cohort opened only after its own development gates.
The failed8009- and12007-series inputs are exposed history; the replacement
uses16001-series seeds. Exact plans and source hashes delimit each
cohort; a seed integer alone does not identify an experiment.

The final native campaign follows [NATIVE_PROTOCOL_V4.md](NATIVE_PROTOCOL_V4.md):
48 development trials at both8/12m/s, then80 entirely new16001-series trials.
Recovery setpoints are capped at16m/s; actual planar speed must remain at most
16.5m/s in the10ms motion records. The exposed12037 steering failure is now
development data, and its original failed confirmation remains preserved.
The wrapper plans against the surrogate's actual slower braking, records nominal
commands/native overrides/API readback separately, and excludes source-confirmed
Radar aperture clipping from center measurements. All rejected prototypes and
the aborted42-run native cohort and full79/80 native-v3 cohort remain preserved. These native-only refinements
do not change the frozen common Python source or its240 fresh inputs.
