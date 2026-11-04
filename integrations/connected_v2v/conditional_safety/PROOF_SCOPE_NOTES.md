# Execution and admission clarification

Read with the frozen [THEOREM.md](THEOREM.md). These notes spell out the actual
reference execution semantics; they do not change experiment source or outcomes.

1. **Admissions occur at control-update boundaries, before the new guard is
   evaluated and before further motion.** The interval proof quantifies over the
   objects protected by that guard. An asynchronous physical intrusion requires
   prior protection covering that interval or an immediate valid safety update.
   Recoverability at an arbitrary instant does not justify continuing an old
   acceleration selected for a different obstacle set. The reference cut-in is
   admitted at tick 120 before `choose`, with the invariant checked for all objects.
2. The protected set is finite and nonempty; memory is not discarded. A departure
   or replacement needs its own coverage argument. No clear-road acceleration
   theorem or lateral departure certificate is supplied here.
3. The command lattice permits abrupt acceleration changes and quantization. No
   jerk, comfort, actuation-lag or acceleration-rate constraint is proved. Adding a
   rate limiter after the shield can remove the emergency candidate and invalidate
   feasibility; it requires a new model/proof rather than a silent output filter.
4. h bounds simulated physical time between effective updates. Offline run speed,
   20 Hz log spacing or a fast Python average does not establish a hard execution
   deadline on a physical controller.
5. Sensor intervals and actuation envelopes are premises checked against fixture
   truth in reference simulations. An actual deployed monitor cannot infer their
   truth merely from reception age or from its own certificates.
6. **The reference propagates its upper state over exactly h at each call.** Its
   verified simulations therefore call it on the fixed h grid. A hold longer than
   h is uncertified. An early extra call must not reuse the full-h predicted speed
   as a current upper bound: during braking, that bound belongs to the later time.
   A variable-period implementation needs propagation at the actual elapsed time,
   valid current bounds and a new correspondence check. The interval theorem is
   conditioned on valid bounds; fixed-grid evidence does not prove such a port.
