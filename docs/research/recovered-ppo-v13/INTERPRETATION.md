# Scope and interpretation of the recovered result

The requested 7.685% result refers to the mean of **three paired PPO policies** in `reviewer-followup-v2`, not one checkpoint that won every scenario. All three are recovered, and their original traces reproduce. The student comparison is paired; no favorable training seed is substituted.

On the original 20m/s grid, the archived per-scenario means are:

| Scenario | PPO tracking gain vs LQR | Student tracking gain vs LQR | PPO actuator-rate RMS increase vs LQR |
|---|---:|---:|---:|
| Zero-service nominal | 13.5053% | 14.1317% | 183.7448% |
| Zero-service tyre stiffness stress | 11.7458% | 12.4557% | 145.2252% |
| 20ms service | 0.0002120% | 0.0002036% | 0.0001514% |
| 100ms service | 0% | 0% | 0% |

These numbers are recomputed from the unchanged `reviewer-followup-v2/episodes.csv`. Aggregate 7.685% is a ratio of overall mean episode RMSE; it is not the arithmetic mean of the four percentages. The student had better tracking in the two active conditions, but **also failed smoothness**. It is incorrect to infer that the student had solved the steering problem.

The audit establishes a train/deploy supervisor mismatch, a command-versus-actuator reward mismatch, and discontinuous high-authority corrections in the recovered configuration. It does not identify a single unique cause for every worse PPO action. Fine-tuning changes the student on only 3.72% of its common-input queries, and PPO improvement is not guaranteed by its training objective. The paired fresh experiment tests the proposed repairs rather than presuming that they work.

Version13 is a **separate experimental repair of the historical latency-gain profile**. It leaves the existing main predictive/compensation controller, original scientific records, acceptance thresholds and reserved evaluations untouched. Its actuator-rate projection is a nominal local rule, not the full predictive vehicle-cost supervisor or a certified robust safety filter. A successful development outcome would need integration and validation in the proposed full architecture before promotion.

Fresh results in README.md use a broader matched grid (15/20/25m/s plus a one-tick10ms service case). Compare methods within that new table. Do not subtract a new percentage from the old7.685% and attribute the difference entirely to the repair: the scenario mixture has changed.

The reported1% selection screen and user20% target concern aggregate improvement against the explicitly declared comparators, with separate smoothness, heading, survival and nominal checks. Exact100ms fallback intentionally equals LQR, so a claim of positive PPO benefit in every delay condition would contradict the fallback design. No real-worker timing, native Webots or physical test is implied by this experiment.
