# Causal PPO actor laptop timing kit

These are exact exports of the new25k PPO actors, not the earlier supervised-only
student. Seed labels701/802/903 map to PPO seeds2701/2802/2903.

Windows64-bit Python3.10: double-click RUN_PYTHON310.cmd. The launcher uses a local
venv, NumPy2.2.6 and native high-resolution Windows timers.

macOS: use RUN_MACOS.command (Python3.11+). If Finder blocks execution, run
`bash RUN_MACOS.command` from Terminal in this folder.4GB RAM is sufficient for the
small NumPy-only model; actual Mac execution is not verified here.

This kit measures actor computation, Pipe IPC and monitor timing on recorded
observations. It does NOT run the observer, LQR, new supervisor, vehicle plant,
Webots, sensors or actuator. Monitor misses are not full-controller deadlines.
Return summary.json and all packet/tick CSVs. Target Windows/macOS results remain
pending until the user runs the kit. No device/product IDs are collected.
