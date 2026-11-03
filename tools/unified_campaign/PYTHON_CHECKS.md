# Python checks executed before performance evaluation

3 November 2026. **196 unit tests passed**, plus a real spawned-worker functional check.

- Root/integration: 54.
- Campaign reproducibility/gates: 5.
- Active v12 contracts: 9.
- LANS-RISK semantic contracts: 13.
- Simulator adapter (Python only): 4.
- Historical controller/gate/report/lifecycle scripts: 111 unit checks across 24 scripts, plus the worker functional script.

The historical MPC test first stopped because OSQP was absent. Installing the repository pin osqp==0.6.3 resolved it; all three MPC tests then passed. NumPy/SciPy pins were preserved. The test runner initially discovered the imported helper named setup as a fixture; aliasing it resolved the five new test setup errors. All original logs and retry logs are retained separately. No assertion or expected result was relaxed.

No native Webots simulation has run in this phase. The fresh worker smoke JSON was retained outside historical results, and the original fixture was restored byte-for-byte. Full per-script records are in the campaign handover bundle.
