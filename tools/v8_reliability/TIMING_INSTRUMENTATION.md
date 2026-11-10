# Timing instrumentation declared before formal native/live outcomes

The two V1 engineering smokes retained one scheduled complete-cycle miss each
under simultaneous CPU confirmation. Their sensor-to-issue responses passed;
they do not establish that the complete50ms cycle passes on the shared machine.

For formal engineering cohorts retain the fixed release origin and all original
deadline definitions. Add owner process CPU time and voluntary/involuntary
context-switch deltas to the immutable timing sidecar. Native records also retain
the wall time of the50 actual physics substeps; the sidecar records inline trace
serialization/write/flush wall time. Live records retain Python plant propagation
wall time under the same complete-cycle definition. Instrumentation itself is
inside the measured cycle. The timing sidecar is serialized after the episode.

These observations separate controller response, simulator/plant execution,
logging and release lateness. Owner wall time exceeding its process CPU time
can include simulator IPC, waiting and OS scheduling; it does not identify a
unique OS root cause. Subprocess solver/inference startup and synthetic kernel
warmup remain explicitly outside measured control ticks. A later miss is retained
and classified by observed phase contributions; no pass-until-rerun selection,
schedule reset, tick dropping or shortened measurement. All timing conclusions
are finite engineering evidence, not worst-case execution-time guarantees.
