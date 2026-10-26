# LANS Windows CPU/IPC timing kit — Python 3.10 supported

Uses actual exported causal-student weights and NumPy. No training, Torch or Webots installation is required. The kit never sends actuator commands.

For your existing **Python3.10 64-bit**, extract the new ZIP into a fresh folder and double-click **RUN_PYTHON310.cmd**. It selects Python3.10 and creates a separate `.venv310`; NumPy2.2.6 matches the supplied baseline run. There is no Python upgrade requirement. `RUN_WINDOWS.cmd` supports installed64-bit Python3.10+ more generally.

The first run needs internet for a prebuilt NumPy wheel. Then the five10-second cases take about one minute, plus worker startup. Keep the charger connected, close unnecessary applications, and return the newly generated `summary.json` and CSVs. Keep the old run and the first new result, including any failures.

## What changed

On Windows, `--timer auto` (default) uses the native `CreateWaitableTimerExW` high-resolution flag and one-shot relative waits. This works independently of the Python3.10 `time.sleep` implementation on supported Windows10/11 systems. Both the monitor and injected worker delays use separate process-local timer handles; actual model inference is timed separately. No busy spin, administrator privilege, system-wide timer-resolution change, deadline rebasing or missed-tick removal is used. Unsupported timer APIs fail explicitly instead of silently falling back.

The original10ms schedule, recorded observations, model weights and monitor accounting are unchanged. Summary metadata records the actual monitor/worker timer backend. Timing improvement is not guaranteed and must be measured on the laptop. A timer does not turn Windows into a hard-real-time operating system.

To deliberately reproduce the coarse-sleep baseline, use `--timer legacy` in a separate fresh output directory. This uses `time.sleep`, and is labelled `legacy_time_sleep`; do not mix it with the native-timer run.

```bat
.venv310\Scripts\python.exe laptop_benchmark.py --output results-py310-native --timer auto
.venv310\Scripts\python.exe laptop_benchmark.py --output results-py310-legacy --timer legacy
```

You can also use `python laptop_benchmark.py` with your existing Python3.10 and NumPy installation. The new folder must contain `precision_wait.py` alongside the script and model files. Golden parity and bundle hashes are checked before timing; a mismatch aborts the run.

## Scope and verification

Exports were verified against the trained Torch model on all archived DEV observations, and512 golden rows per model are checked on the laptop. The Windows API wrapper has mocked resource/error/rounding tests and a Linux multiprocessing smoke. Actual Python3.10 Windows execution of the new timer remains pending; no improved Windows result is claimed.

These are recorded inputs. No observer, LQR, predictive gate, plant, vehicle sensor, CAN or actuator executes here. Monitor deadlines are not full-controller deadlines, and the kit cannot certify vehicle readiness. No hostname, device/product IDs or network identifiers are collected.
