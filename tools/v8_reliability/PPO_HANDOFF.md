# Integration boundary for the separately assigned PPO work

This branch changes analytical supervision/execution and evidence tooling. It
does not train, select, reweight or alter the three original PPO policies, their
17-feature contract or their reward. PPO incremental-benefit optimization belongs
to the other agent.

The current experimental owner is
`tools.v8_reliability.traffic_guard.Controller`. The training-selected settings
are R16, horizon2s, quality_factor1.10, secondary_factor1.075, early_id=True,
tracking_only=False and adaptive feedback. Use `planner_backend='logical'` for a
declared logical-service experiment and `'process'` for actual nonblocking worker
execution. The matched analytical baselines must receive the same new traffic
supervisor/recourse. The original v8 remains a separately labelled frozen reference.

Source timestamps, command FIFO, physical limits, <=150ms proposal lifetime and
owner admission remain mandatory. The V2 supervisor grows future contact
uncertainty consistently and retains a passed vehicle's remaining crossing
occupancy. Although the public feature shape stays17, risk/TTC feature values
change with this supervisor; train/evaluate against an explicitly frozen matching
owner. The emergency improvement mode is explicitly uncertified and its benefits
must be attributed to the common supervisor rather than PPO.

V1's2309-record and V2's1240-record final sets are now exposed evaluation data.
They may become labelled development regressions in a new protocol, but cannot
be reused as untouched final evidence. V2's fresh final actor42 minimum progress
is98.7031%, below99%; its hybrid-vs-adaptive RMSE gain is-0.002964% with a95%CI
spanning zero. The current owner is therefore experimental, with no successful
replacement or learned-benefit claim. The old v8's verified5.186% development
result remains preserved in its original evidence.

Read `outcome-ledger.json` in the restored raw evidence and this module's README
for all quality/progress/timing gates. Default pytest now uses stable qualified
tool-package imports; keep separate Numba cache directories for tests, CPU
campaigns and actual runtimes. All original weights and manifests are included
unchanged in the sealed evidence for reproducibility.
