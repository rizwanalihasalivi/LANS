# Three-actor LANS target-laptop rerun

Extract the entire ZIP first. Windows: double-click RUN_WINDOWS.cmd (Python3.10). macOS: run `bash RUN_MAC.command` with Python3.10 installed. First installation requires internet. No Torch, GPU or Webots is needed.

The command runs all three frozen actors, each with nominal,20ms service wait,1000ms service wait,CPU stress and worker-crash cases. Each case lasts13seconds after warmup:195seconds total measured windows, plus startup and independent replay. It does not retry failed timing cases. Keep the laptop plugged in and close unrelated applications. Results remain in a new laptop-results folder; send laptop-results/Results.zip, which includes all raw CSVs and independent replay checks. No device identifiers are collected.

Any original10ms deadline miss fails observed strict timing. Functional fallback, actual nominal learned assistance and timing are reported separately. The software plant pauses during host stalls. This does not validate physical sensors, communications, actuators or continuous-time vehicle safety.

RESEARCH_STATUS.json identifies whether these are a newly development-selected model or the unchanged v5 diagnostic because no new model qualified. Neither status is vehicle deployment approval or a completed confirmation study.

# LANS full-controller laptop SIL kit

Requires CPython3.10 (3.11 also supports these dependencies), internet for first dependency installation, and an extracted writable folder. No Webots, GPU or Torch required. Do not run from inside the ZIP.

Windows: double-click RUN_WINDOWS.cmd. Or in PowerShell: `py -3.10 -m venv .venv`, then `.venv\Scripts\python.exe -m pip install -r requirements.txt`, then `.venv\Scripts\python.exe tools\controller_review\laptop_campaign6.py --profile fresh_history --output laptop-results`.

macOS: in Terminal, run `bash RUN_MAC.command` with Python3.10 installed. Apple Silicon installation of older dependency wheels may require an appropriate Python distribution; do not silently substitute dependency versions.

Five cases run13seconds each, after untimed JIT/model warmup. Close unrelated applications and use power supply. Do not adjust system-wide priorities. Output folder must be new; use `--profile fresh_history --output laptop-results-2` for another run. Send laptop-results/Results.zip after completion. It contains timing/plant CSVs and summary; no device identifiers are requested.

To independently replay raw outputs, run the same virtual-environment Python with `tools/controller_review/verify_full_laptop.py --run laptop-results/seed-701 --models actor`. This verifies original deadlines, actor outputs, fallback and plant/observer/LQR replay; it does not convert timing failures into passes.

Scope: causal noisy observer, scheduled LQR, fixed fresh_history residual supervisor, NumPy PPO actor in a separate process, real IPC and original timestamps, physical steering saturation/rate dynamics in a FIXED-STEP SOFTWARE PLANT. Tests nominal,20ms/1000ms post-inference worker service delays, CPU contention and worker crash. Injected service delays are distinct from measured inference time. This is a development diagnostic, not a selected research winner or native Webots validation.

Any missed original10ms deadline fails observed strict timing; deadline misses revoke assistance, and stale/failed workers use fresh-state LQR. Functional success does not imply timing success. Fixed-step plant survival cannot establish continuous-time safety during host stalls, hard real-time guarantees, sensor/CAN/actuator timing, or real-vehicle readiness. Actual Windows/macOS results must be collected on your laptop; cloud smoke checks cannot replace them.
