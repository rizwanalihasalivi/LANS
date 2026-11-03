# Fresh-data formation recovery v3

[Results](RESULTS.md) · [Pre-outcome protocol](PROTOCOL.md) · [Figure](evidence/formation-v3.png)

This is a separate version of the v2 fusion controller. One analytically chosen
nominal response (kp=0.64, kv=0.832) replaces the slow nominal v2 poles. Source
arbitration, timestamps, replay checks, gap/headway and emergency braking remain
unchanged. Both variants use the same follower speed envelope cruise+8 m/s.
This is finite validation of a simple feedback design, not a new stability theorem.

`adapter.configured()` scopes in-memory class/configuration substitution to one
experiment process and restores v2 globals in `finally`. Original files are never
patched. The original simulator/replayer generates sensing, faults, plant and
metrics; `metrics.py` independently measures first-20 error, progress, censoring,
settling, blind braking and envelopes. The post-hoc stdlib checker imports no
controller/model/metric helpers and rejects altered aggregate evidence.

From the existing `/workspace/LANS` checkout; no worktree or new training is needed:

```bash
source /workspace/lans-setup/env.sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m pytest -q integrations/connected_v2v/formation
# Use NEW output roots. Do not tune on existing confirmation.
python -m integrations.connected_v2v.formation.campaign prepare --output results/my-formation-v3
python -m integrations.connected_v2v.formation.campaign development --output results/my-formation-v3
# Conditional on ALL development gates passing:
python -m integrations.connected_v2v.formation.campaign confirmation --output results/my-formation-v3
python -m integrations.connected_v2v.formation.reporting.independent results/my-formation-v3
# Conditional on BOTH Python gates; requires the checksum-verified private runtime:
bash integrations/webots/install-private.sh
python -m integrations.connected_v2v.formation.native.run --study results/my-formation-v3 --output results/my-formation-native-v3
```

The fixed grids use three independent workers and local per-case RNGs. Two
identical full raw-hash/metric repetitions are required before development.
Partial evidence is not silently overwritten. The serial v2 data-generation
and replay functions remain unchanged, with declared variant settings recorded
in every case. All methods and seeds are retained.

The native factorial separates feedback changes from the speed adapter:
`legacy` clips all cars to 8 m/s; `recovery` keeps the leader at 8 and permits
follower catch-up up to a 16 m/s setpoint. The same frozen controller class,
sensing, faults and requested acceleration limits serve both. Actual speed-servo
acceleration can differ from its request; measured ranges are retained.

The new world uses a 2,000 m road, not the old 200 m short fixture. The auditor
requires valid height, tilt, forward heading, corridor and map bounds for all
samples. Initial short-road 30 s trials are preserved as INVALID fixture data;
do not quote their old proxy-pass metrics as on-road performance.

The [Python/source archive](evidence/formation-python-v3.zip) and
[native archive](evidence/formation-native-v3.zip) include raw evidence, protocols,
source freezes, invalid-fixture diagnostics and SHA-256 manifests. Source code
and runtime dependencies are separate from the processes created for each native
run; no server needs to remain running.

Blind-phase information loss, scripted predecessor association, native cut-in
transfer and string stability are still open limitations. This experiment does
not modify or promote the other main PPO/controller track.
