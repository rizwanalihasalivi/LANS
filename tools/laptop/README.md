# LANS Windows laptop timing kit

For Windows x64, Intel Core i5-1235U and 8 GB RAM. Uses actual exported causal-student weights and NumPy only; no training, Torch installation or vehicle connection is required. The kit does not collect device/product IDs or hostname.

1. Download the ZIP from GitHub, then **Extract All** into a writable folder.
2. Install 64-bit Python 3.11 or newer from https://www.python.org/downloads/windows/ if necessary.
3. Connect laptop power, close unnecessary programs, and double-click **RUN_WINDOWS.cmd**. It explicitly selects64-bit Python3.11+ and creates a separate local `.venv-modern` and installs NumPy from the Python package index.
4. Wait approximately one minute, plus first-time installation. The cases include normal inference, actual injected20/100ms worker unavailability, a CPU contender and deliberate inference-worker termination.
5. Return **summary.json** from the newly created `laptop-results-...` folder. Keep the accompanying CSVs.

The model export has been checked against the original Torch model on every archived DEV observation. The script additionally verifies hashes and512 golden observations for all three models on your machine before measuring. A parity error aborts the measurement. Seed701 is the default timing model; use `--seed 802` or `--seed 903` to test another.

This measures actual laptop inference and observation-to-worker-receipt time using recorded inputs. It also counts10ms monitor-loop deadline misses. It does **not** run the observer, LQR, predictive gate, vehicle dynamics, sensors, CAN or actuator, and cannot certify full-controller100Hz timing or real-vehicle readiness. Windows benchmark results remain pending until the kit runs on the laptop.

For a manual run:

```bat
.venv-modern\Scripts\python.exe laptop_benchmark.py --output my-new-results --seconds 10 --seed 701
```

A fresh output directory is required. Do not rerun until only a favourable result remains; retain all runs. The script never sends steering commands.

## Python3.10 Windows baseline

The earlier launcher selected the default Python3 runtime, which could be3.10 despite the documented3.11+ requirement. The updated launcher enforces3.11+ and avoids reusing the old environment. Manual benchmark execution also rejects Windows Python<3.11 unless `--allow-legacy-windows` is explicitly supplied for a separate baseline.

CPython3.11 changed Windows `time.sleep` to use a waitable timer; see https://docs.python.org/3/library/time.html#time.sleep . This may reduce wake-up granularity, but does not guarantee deadlines. Preserve the original3.10 run and the first modern-runtime run; compare both without dropping bad outcomes.
