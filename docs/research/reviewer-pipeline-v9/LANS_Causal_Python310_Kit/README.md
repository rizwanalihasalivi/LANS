# LANS causal-history laptop kit — Python 3.10

Extract the ZIP first. Windows: double-click RUN_WINDOWS.cmd. macOS: run `bash RUN_MAC.command` with Python 3.10 installed. First dependency installation needs internet. No Torch, GPU or Webots is required. Use mains power and close unrelated programs. Do not run simultaneous benchmarks.

The command runs three frozen actors, each on five 13-second software-plant cases (195 measured seconds plus warmup/replay): nominal, 20ms and 1000ms post-inference worker waits, CPU contention and crash. Computation, IPC, service wait and proposal age are separately recorded. The unmodified original 10ms target remains the deadline; the 1ms guard skips optional work, never shifts the target. Misses are failures even when fallback works. Output must be a NEW folder; failed/partial data are retained.

Before execution every bundled source/model file is checked against bundle-manifest.json. Every original target, returned actor output, all issued input vectors, past-only timing history, recovery/expiry decision and software-plant transition are independently replayed. Return laptop-results/Results.zip, including failures. Source hashes provide reproducibility, not attestation of physical hardware.

The separately versioned 20-channel causal_recovery_history_v9 profile includes filtered residual, past completed-response EWMA and age of the previous qualifying proposal. It never includes the current request's future completion time. This profile must not be substituted into old model manifests. LQR continues using current estimated state. Learned authority expires at 50ms regardless of a favorable prediction. The compensation forecast is capped at 40ms; this does not compensate for arbitrary LQR feedback or physical sensor delay.

RESEARCH_STATUS.json distinguishes a selected controller from a diagnostic actor. A cloud smoke test cannot substitute for your laptop result. Software-plant survival does not establish continuous-time stability, physical sensing/communication/actuator performance or real-vehicle readiness. Strict observed timing and nominal learned assistance are separate results; no hard real-time guarantee is claimed.
