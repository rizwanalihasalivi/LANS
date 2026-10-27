# Experimental LANS recovery and expiry-aware controller

Extract the ZIP first. Windows: RUN_WINDOWS.cmd; macOS: `bash RUN_MAC.command` with Python3.10 installed. Internet is needed for first dependency installation; no Torch/GPU/Webots is required. The Windows script also accepts an available Python3.10 `python` when the `py` launcher is absent and keeps error messages visible.

Three frozen actors each run five13second cases after warmup: nominal,20ms and1000ms post-inference worker waits, CPU contention and worker crash. Total measured windows195seconds, plus startup and independent raw replay. Use power supply and close unrelated apps. Send laptop-results/Results.zip. Output must be new; failed/partial runs are preserved rather than overwritten or retried away.

This version requires three distinct qualifying proposals, retains recovery/filter memory only within a50ms liveness window, and sets authority zero on every stale tick. Prediction uses only the current proposal lifetime, followed by LQR continuation. The launcher enables an optional1ms reserve to skip optional work near the original10ms deadline. This reserve is not WCET certification; any original deadline miss still fails strict observed timing. Future input prediction uses only completed-response history and remains capped40ms.

RESEARCH_STATUS.json records that no new controller is promoted if the development criteria fail. Frozen actors were not retrained for the revised gate. Functional fallback, nominal learned assistance and strict timing are separate fields. Fixed-step plant survival does not validate physical sensor/communication/actuator delays, continuous-time safety or real-vehicle readiness. Actual laptop execution is pending until YOU run this kit.
