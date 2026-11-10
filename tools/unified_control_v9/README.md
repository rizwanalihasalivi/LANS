# V9 saved validation and reproducible evidence

The asynchronous strict-quality candidate is not promoted. All fixed experiments
and failures are retained. The requested 30% whole-run gain remains unmet.
This directory contains technical execution records, not thesis drafts or figures.

Completed and independently audited: 576 controller-calibration episodes, 448
geometric-baseline calibration episodes, 49,152 additional PPO training steps
with matching shadow-LQR transitions, 2,416 frozen comparison episodes, 20
actual-worker checks and 16 native Webots single-vehicle transfer episodes.
The focused suite has 101 unique passing tests.

Final Python mean RMSE is 0.081518675 m versus LQR 0.081571953 m: only 0.065315%
improvement, with a 95% clustered interval spanning zero. Heading and steering
rate are slightly lower, but minimum matched progress is 97.5396%, below 99%.
The candidate is 4.28818% worse in RMSE than the frozen v8 hybrid on these same
cases. Incremental gain over adaptive-only is 0.000214%. The original performance
gate and the 30% target both fail. Earlier v8 results remain separate evidence.

All 3,440 calibration/evaluation episodes completed without recorded collision
or corridor failure. Training nevertheless contains five crossing collisions:
each matched LQR shadow collides at the same tick, with no PPO selection in those
episodes. These are unresolved shared failures, not proven unavoidable states.
PPO was selected on only 23 of 49,152 training ticks. At 100 ms command delay,
the 50 ms service reaches the strict 150 ms expiry boundary and gives no learned
authority. Full training diagnostics and failed logging attempts are retained.

All 2,400 actual-worker ticks have zero observed local and scheduled deadline
misses. This finite cohort does not erase the previous miss or establish WCET.
Native Webots completes 1,920 ticks without corridor failures, but mean RMSE gain
is only 0.004313%, and no PPO/MPC proposal is selected. One complete native cycle
misses its scheduled deadline, despite zero controller-response budget misses.
The world has no interacting traffic; collision avoidance and full V2V transfer
are not validated. Physical wheel-rate peak is approximately 0.6032 rad/s, while
command slew is bounded at 0.6 rad/s. Native dynamics are not replayed as a Python
bicycle. Stanford/Stanley and pure-pursuit comparisons are documented geometric
adaptations, not completed primary-paper or closest-method reproductions.

## Recovery

`evidence/` seals raw traces, all three policy endpoints and checkpoints, source
snapshots, protocols, failed attempts, logs and the independent audit. Archives
are below 50 MiB; SHA256SUMS, SEAL.json, every member hash and reconstructed trace
hash are checked. Large traces are split without dropping bytes. Restore into a
fresh directory; existing evidence files are never overwritten:

```bash
python -m tools.unified_control_v9.package --verify
python -m tools.unified_control_v9.package --restore /workspace/lans-v9-restored
```

Original v2 policy inputs remain in the earlier tracked archive
`tools/unified_campaign/evidence/python-v2-training.zip`; restore those historical
dependencies before numerical replay. Use the recorded Python 3.10 environment,
v5 dependency pins and Clarabel 0.9.0. With raw evidence restored at repository
root, run `python -m tools.unified_control_v9.verify`. SUMMARY.json and
verification.json under restored results/publication-v9 contain the technical
results and audit. The fixed final cohort must not be reused for tuning.

Remaining research includes meaningful learned benefit, the 30% target, shared
crossing failures, progress, full native traffic, target-hardware timing and
closest published-method/novelty evidence. No full-framework final pass is claimed.
