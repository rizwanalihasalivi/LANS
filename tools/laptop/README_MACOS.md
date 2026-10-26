# LANS macOS timing kit — 4 GB RAM

Small NumPy-only CPU/IPC benchmark using the actual exported causal student. No training, Torch, Webots or vehicle connection is needed. Supports Intel and Apple Silicon with compatible Python/NumPy wheels. Actual execution on your Mac is still required; cloud Linux checks are not macOS timing results.

1. Download the ZIP and double-click it to extract. Work from the extracted folder.
2. Install Python3.11 or newer using the **macOS universal2 installer** from https://www.python.org/downloads/macos/ if necessary. Older macOS versions may need an older compatible Python3.11 installer. The launcher will explain if Python is missing.
3. Plug in the charger and close unnecessary applications on the4GB Mac.
4. Double-click **RUN_MACOS.command**. It creates `.venv` in this folder and downloads a prebuilt NumPy wheel. It will not compile NumPy from source.
5. After about one minute plus first-time installation, return **summary.json** from the new `mac-results-...` folder. Keep all CSVs and failed runs.

If Finder cannot open the launcher or it lacks executable permission, open **Terminal**, type `bash ` (including the space), drag `RUN_MACOS.command` from Finder into Terminal, then press Return. Use your extracted copy after checking its source. No administrator password or system-wide Python package installation is needed.

The data/model payload is small, and numerical libraries use one thread. CPU-stress testing starts only one extra small process. Available memory depends on macOS and other applications; this is not a measured4GB memory guarantee. No device/product IDs, hostname or network identifiers are collected.

The kit checks512 golden observations on all three exported models before timing. A model-parity or hash failure stops the test. Default timing uses seed701 and five10-second cases: nominal, injected20/100ms worker unavailability, one CPU contender and worker termination. Sleep is reported separately from actual inference time.

These are recorded observations, not live sensors. The monitor loop does not execute the observer, LQR, predictive gate, plant, CAN or actuator. This cannot certify full-controller100Hz execution or vehicle readiness. Do not compare one favourable Mac run with a differently loaded cloud run as proof of controller superiority.
