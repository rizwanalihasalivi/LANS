# Resume the aligned-controller work

From the prepared Linux CPU Python3.10 environment, at repository root:

```bash
python tools/controller_review/run_aligned_work.py --publish
```

`--publish` commits verified milestones and pushes the current branch. Omit it
for local execution. There is no force push, automatic merge or editor contact.
Completed scientific stages are reused. Partial failed stages are preserved for
inspection rather than deleted or silently retried. Frozen input changes require
a separately identified study; the command never changes thresholds to pass.

The frozen v3 stage trains three100,000-step PPO endpoints using the same
predictive supervisor as evaluation and an actual actuator-rate reward, evaluates
576 matched episodes, independently replays raw rewards/filters/actors/fusion and
severe-delay fallback, then runs the predeclared timing diagnostic separately.
The outer command exports the actual actors, verifies24,300 Torch/NumPy action
comparisons per actor, packages the full-controller kit, runs a software-plant
smoke and independent physical-feature/observer/LQR/model/timestamp replay, and
exports Word/PDF reports. No extra training or reserved tests are opened on a
failed development screen.

Prepared research versions: NumPy1.23.5, SciPy1.10.1, Numba0.57.1,
Torch2.0.0+cpu, Stable-Baselines3 2.0.0, Gymnasium0.28.1,
OSQP0.6.3 and qdldl0.1.9.post1. OSQP is inherited by the shared evaluation
loader; optional pins are in `tools/reviewer_followup/requirements.txt`. GCC,
Pandoc, XeLaTeX and DejaVu Serif are required by the Linux timing/report stages.
This is not an installer for an arbitrary computer. Existing cloud setup is
documented in `tools/cloud/README.md`.

For a clean portable smoke environment, use `--smoke-python /path/to/python`
with only the packaged kit requirements installed. The completed clean check
used Python3.10 and five3-second cases, seed701. All three actors undergo golden
parity checks; one-seed smoke is not a three-seed target-hardware validation.

## Actual laptop execution

Download `docs/research/reviewer-aligned-v3/LANS_Aligned_Python310_Kit.zip`,
extract all files into a new writable folder, and run `RUN_WINDOWS.cmd`, or
`bash RUN_MAC.command` on macOS with Python3.10 installed. The launcher selects
the aligned supervisor and actual new PPO endpoint. Internet is needed for
initial dependency installation. There is no Torch/GPU requirement in this kit.
Return `laptop-results/Results.zip` after completion. A second run needs a new
output folder; original raw results should be retained.

The kit uses a fixed-step software plant, not Webots, physical sensors, CAN or a
vehicle actuator. It measures real worker inference/IPC/unavailability and local
controller timing, rejects stale or mismatched responses and falls back to fresh
local LQR. Simulation survival and functional fallback do not imply continuous
physical safety during a host stall or hard real-time guarantees.

Current full selection still fails: the balanced PPO result improves on LQR but
its additional gain over the same-supervisor student is below the frozen1%
margin. The new kit also misses deadlines. The cloud connection became
unavailable during the scheduling diagnostic; those counts must not be treated
as an uninterrupted controlled timer comparison. Physical validation and the
complete robust published-controller reproduction remain external/open work.
