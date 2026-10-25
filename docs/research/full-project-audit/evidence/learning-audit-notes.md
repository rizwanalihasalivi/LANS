# Revision6–9 learning audit

## Confirmed bug fixed: incomplete revision9 checkpoint-selection contract

`research/revision9/evaluate9.py:93` previously trusted upstream row counts, omitted severe100ms exact fallback from candidate eligibility, and paired frozen student/finetune0 by list order. A supplied complete grid containing a50000-step candidate with a false100ms improvement and nonzero gate activity was eligible and selected. Missing/duplicate conditions could also reach aggregate selection if called independently; row ordering affected floating sums and positional parity assumptions.

Fix: selection validates the complete unique paired development grid, finite scores/active fractions, explicit survival and declared development noise IDs; canonicalizes protocol order; enforces per-cell100ms score equality and zero gate activity as candidate eligibility; verifies frozen-student parity by paired keys. This is a selection correctness fix, not controller retuning.

Changed files:
- `integrations/webots/research/revision9/evaluate9.py`
- `integrations/webots/research/revision9/test_step3.py`

Historical impact: all1188 stored DEV rows reproduce the entire saved six-arm/pair selection dictionary exactly, including every candidate score/reason. Existing final performance claims are unchanged. This guard omission therefore does NOT explain the historical2% gain.

Evidence:
- `/tmp/learning-selection-probe.py` reproduces old function directly from commit048ee96 and compares fixed behavior on a synthetic invalid-fallback grid.
- `/tmp/learning-selection-before-after.json`: old selected50k invalid candidates, fixed rejects and selects100k valid candidate (all three scratch seeds).
- `/tmp/learning-audit-tests.txt`: six revision9 tests passed, including actor transfer/load parity, physical-action/reward/horizon equality, split/reset checks, complete-grid/severe-fallback guards and exact recorded-selection parity.

## Quantified learning-mechanism evidence (not a causal explanation)

`/tmp/learning-stochastic-probe.py` reads the existing24,300 revision8 DEV observations/costs and fixed student weights, without fitting/selection/rollouts. It calculates mean episode-aggregated clipped teacher regret for deterministic argmax versus expected categorical sampling from the same logits. Raw JSON: `/tmp/learning-stochastic-diagnostic.json`.

| Student seed | Argmax teacher regret | Sampled expected teacher regret | Probability of non-argmax action |
|---|---:|---:|---:|
|701|0.01334896|0.01588152|11.7076%|
|802|0.01296314|0.01567779|12.0823%|
|903|0.01329655|0.01615860|12.1093%|

PPO samples actions; the retained student and evaluation use argmax. Thus identical initial logits preserve deterministic policy exactly but produce a different exploratory training behavior with higher expected finite-teacher regret on these fixed observations. This is standard PPO behavior, not an implementation bug. The probe is off-policy and privileges stored teacher costs; it cannot establish fresh tracking performance or prove this causes later PPO degradation.

Existing recorded `revision9-finetuning/optimization-diagnostics.json` additionally reports:
- fine-tune gate-active fractions0.06608,0.08903,0.07753;
- mean tracking reward approximately0.96, versus relative reward around0.0005–0.0007 in the first two jobs;
- finite PPO losses/KL/critic fit and actual optimizer counters near5000.
`actor-drift.md` reports final student agreement92.01%,82.14%,82.82% and higher teacher regret at100k for all three seeds. Target KL0.01 is against each rollout policy, not a permanent constraint against original student. These facts are consistent with weak action-dependent opportunities and cumulative drift under a different reward; they are not causal isolation, vanishing-gradient proof, or permission to tune against final tests.

## Positive checks / research limits

Inspected active revision6 direct/execution environment and trainer/evaluator/MPC implementation; revision7 kernel/gate interfaces (another agent owns fixes there); revision8 teacher/data merge/split generation/student fit and loading; revision9 actor transfer, environment, train/resume, DEV selection and reporting. No evidence found that doubled LQR, wrong±.08 mapping, missing observation standardization, failed actor copying, reset optimizer, or dead gradients caused revision9's negative fine-tuning result. Actor transfer, saved serialization, categorical action mapping and full horizon match their stated protocols/tests. Model copies, normalization buffers and reward-normalizer continuation remain intact.

The current finite teacher uses five residuals,200ms hold search, three noise forecasts and an unchanged nominal gate. Its≈2.23% recorded gain is not a global ceiling. Gate authority and frequency, strong LQR, objective/short-vs-long horizon mismatch, categorical exploration and cumulative actor drift are supported mechanisms or hypotheses to isolate. They do not justify an unconditional5–10% improvement promise or weakening LQR.

No old data/checkpoint/source snapshot, protocol, objective, optimizer, model or final-test selection was changed. No new training/native/full campaign was run. Scope here is learning-path audit, not exhaustive mathematical proof or fresh evaluation of every research artifact.
