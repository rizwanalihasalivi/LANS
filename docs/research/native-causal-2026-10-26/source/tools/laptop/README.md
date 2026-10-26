# LANS Windows laptop timing kit

For Windows x64, Intel Core i5-1235U and 8 GB RAM. Uses actual exported causal-student weights and NumPy only; no training, Torch installation or vehicle connection is required. The kit does not collect device/product IDs or hostname.

1. Download the ZIP from GitHub, then **Extract All** into a writable folder.
2. Install 64-bit Python 3.11 or newer from https://www.python.org/downloads/windows/ if necessary.
3. Connect laptop power, close unnecessary programs, and double-click **RUN_WINDOWS.cmd**. It creates a local `.venv` and installs NumPy from the Python package index.
4. Wait approximately one minute, plus first-time installation. The cases include normal inference, actual injected20/100ms worker unavailability, a CPU contender and deliberate inference-worker termination.
5. Return **summary.json** from the newly created `laptop-results-...` folder. Keep the accompanying CSVs.

The model export has been checked against the original Torch model on every archived DEV observation. The script additionally verifies hashes and512 golden observations for all three models on your machine before measuring. A parity error aborts the measurement. Seed701 is the default timing model; use `--seed 802` or `--seed 903` to test another.

This measures actual laptop inference and observation-to-worker-receipt time using recorded inputs. It also counts10ms monitor-loop deadline misses. It does **not** run the observer, LQR, predictive gate, vehicle dynamics, sensors, CAN or actuator, and cannot certify full-controller100Hz timing or real-vehicle readiness. Windows benchmark results remain pending until the kit runs on the laptop.

For a manual run:

```bat
.venv\Scripts\python.exe laptop_benchmark.py --output my-new-results --seconds 10 --seed 701
```

A fresh output directory is required. Do not rerun until only a favourable result remains; retain all runs. The script never sends steering commands.
