# Balanced-gate confirmation and mirrored-road study

This user-authorized revision follows the 9.122% nonlearned development result and the heading/steering trade-offs found in revision12. The [protocol](protocol.json) is frozen before new outcomes. Existing models, results, source snapshots, specification and phase1 artifacts remain unchanged. Latest main's real-worker timing evidence is retained; native timing and causal student-interface limitations remain explicit.

The finite sequence is:

1. **Independent confirmation:** 2,160 episodes, five methods, fresh noise, original and new roads in both directions. The exact original positive-orientation subset is reported separately when assessing replication of the earlier 9.122%. Mirrored copies share reflected noise and are not independent repetitions.
2. **Balanced development:** 5,616 episodes. Three predeclared heading/actuator-rate cost profiles share the original predictor, authority, worker lifecycle and plant. Both fixed residual signs and the frozen student are compared under each gate. Full-grid lateral, heading, steering, survival and fallback metrics are recorded for every episode.
3. **Conditional reserved confirmation:** select one eligible nonlearned balanced controller from development, commit that selection, then evaluate 3,024 fresh-noise episodes. Two additional mirrored road geometries were excluded from gate development. Do not reselect after reserved outcomes.
4. **Conditional native confirmation:** after the selected controller passes reserved checks, run 48 private Webots cases against LQR, with measured heading/steering trade-offs and severe fallback. The native controller is the known fixed correction; this is not a native transfer of the current student or a real-worker timing benchmark.
5. **Conditional learning headroom and pilots:** only after a balanced baseline is confirmed, a gate-matched teacher must beat both fixed controls while preserving the heading/smoothness budgets before two 100k PPO pilots are permitted. Their old simulated pending-context interface remains explicitly surrogate-only. No full training or automatic deployment follows.

Selection thresholds are engineering spending criteria, not certified comfort or safety limits. No candidate is forced through if all three profiles fail. Fixed positive/negative controls should tie when averaged over exact mirror pairs; this is a symmetry check, not two independent successes. Novel road shape/scale variations are limited analytic tests, not broad real-road generalization.

From repository root, use the pinned research Python environment and fresh output directories:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export NUMBA_CACHE_DIR=/tmp/lans-v13-numba MPLCONFIGDIR=/tmp/lans-v13-mpl
/workspace/lans-setup/venv/bin/python integrations/webots/research/revision13/test_contracts13.py -v
/workspace/lans-setup/venv/bin/python integrations/webots/research/revision13/test_report13.py -v
/workspace/lans-setup/venv/bin/python integrations/webots/research/revision13/test_run13.py -v
/workspace/lans-setup/venv/bin/python integrations/webots/research/revision13/test_native13.py -v
/workspace/lans-setup/venv/bin/python integrations/webots/research/revision13/run13.py \
  --phase confirmation --output /tmp/lans-v13-confirmation
/workspace/lans-setup/venv/bin/python integrations/webots/research/revision13/report13.py \
  --run /tmp/lans-v13-confirmation
/workspace/lans-setup/venv/bin/python integrations/webots/research/revision13/run13.py \
  --phase development --output /tmp/lans-v13-development
/workspace/lans-setup/venv/bin/python integrations/webots/research/revision13/report13.py \
  --run /tmp/lans-v13-development
```

The reserved runner additionally requires an eligible `--selection` JSON whose exact bytes have been committed to the repository. A failed development decision is a stopping result, not permission to change weights or budgets. Native execution separately requires the selected controller, development proof and passing reserved proof. Every run stores executable source/model hashes and independent phase/noise identities.

Primary-paper retrieval is tracked separately in [the source verification record](../../../../docs/research/literature-primary-check.md). Proxy-blocked sources must not be described as read or as reproduced competing algorithms.
