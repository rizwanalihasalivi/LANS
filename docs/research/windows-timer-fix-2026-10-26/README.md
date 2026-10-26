# Windows timing review and modern-runtime launcher

Uploaded raw records agree with their summary: 5,000 monitor ticks, 1,717 misses (34.34%). The earlier pasted console numbers differ; they are not mixed into this analysis. Raw uploaded files are retained in the local analysis workspace rather than included in this package.

Nominal model inference median0.0758ms, p990.220392ms, observed maximum0.4313ms. Nominal observation-to-receipt median15.7638ms; send-to-parent-receipt median15.3455ms. All monitor processing durations across all five cases were below10ms, with a2.4126ms maximum.1,623 of1,717 misses were already late at release. This is strong evidence that the monitor timing problem is dominated by release/polling behaviour in this run, not model compute.

The runtime was Python3.10.0 with NumPy2.2.6 on Windows. Release spacings cluster around15ms and are followed by sub-millisecond catch-up intervals. CPython3.11 changed Windows time.sleep to a waitable timer (https://docs.python.org/3/library/time.html#time.sleep). The pattern is consistent with coarse sleep/wakeup timing; a new run is required to test this explanation. An old-runtime timing failure remains a valid observed result, not data to discard.

The old launcher used py -3 and did not enforce its documented3.11+ requirement. The updated RUN_WINDOWS.cmd explicitly selects installed64-bit3.11+ and creates .venv-modern without reusing the old environment. Direct execution on Windows Python<3.11 is rejected unless --allow-legacy-windows is explicitly supplied for a baseline. The model, recorded inputs and10ms schedule are unchanged; no missed deadlines are hidden or rebased.

Download LANS_Windows_Modern_Timer_Kit.zip, extract into a new folder, install64-bit Python3.11+ from python.org if needed, then run RUN_WINDOWS.cmd. Keep the original run and return the new summary.json and CSVs. Record Python/NumPy versions and retain all outcomes. A changed runtime is not a hard-real-time guarantee, and NumPy/OS/background-load differences limit causal attribution from a single comparison.

The package passed model/golden checks and a five-case half-second Linux multiprocessing smoke. Actual Windows modern-runtime execution is pending; no improved Windows miss rate is claimed. This monitor benchmark does not run the LANS observer, LQR, gate, vehicle plant, sensors or actuators. The intentional worker crash's665 continued monitor ticks do not establish LQR control continuity.
