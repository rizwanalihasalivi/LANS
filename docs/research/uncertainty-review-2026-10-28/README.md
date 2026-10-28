# Proposed uncertainty-calibrated residual admission: literature and design review

## Conclusion and access limits

The broad idea **learn where a predictor is unreliable from past data, then adjust control decisions using that uncertainty** is established. A narrower candidate contribution is to calibrate **one-sided overestimation of incremental tracking benefit over LQR**, conditioned on proposal age and observable driving context, for the actual expiry-aware residual/recovery decision. This is a research hypothesis, not established originality or a measured performance improvement. There is no defensible "novelty percentage."

Live searches of OpenAlex, Crossref, Google, a PMLR primary page and public GitHub paper repositories were attempted. Requests returned proxyHTTP403/Forbidden; outside-sandbox retries also failed where completed. The Doubao link could not be loaded, but the user subsequently supplied its full conversation as text. This review uses that supplied text, available primary PDFs, archived source/data and independent reduced-model checks. It is **not a completed systematic literature search** and does not establish the absence of an exact prior method.

## Comparison with existing approaches

| Prior work / family | Established overlap | Remaining candidate distinction | Verification level here |
|---|---|---|---|
| Wabersich & Zeilinger, *A predictive safety filter for learning-based control of constrained nonlinear dynamical systems*, arXiv1812.05506v4,2021 | Data-driven model belief; uncertainty depending on state and input; Bayesian/model-confidence sets; confidence-dependent planning and constraint tightening. Definition4.4 and Eqs.(13)–(16) explicitly describe data-dependent confidence maps. | Calibrate the error in a **paired baseline-versus-residual cost difference**, including proposal lifetime and recovery authority, rather than treating only dynamics error/constraint safety. This different target is not itself proof of novelty. | Supplied full text reread, especially Section4.2, pp.7–9. |
| Kalaria, Lin & Dolan, *Delay-aware Robust Control for Safe Autonomous Driving and Racing*, arXiv2208.13856v1,2022 | Past computation-time observations update a delay model and uncertainty estimate; a confidence-adjusted delay estimate affects state prediction/control. It also includes robust control and a learned-controller guard. | Learn the overoptimism of **predicted tracking benefit conditional on current proposal age/context**, not merely the duration of the delay. | Supplied full text reread, SectionsIII-H/I/J. |
| High-confidence / safe policy improvement, including Thomas, Theocharous & Ghavamzadeh, *High Confidence Policy Improvement* (2015), and Laroche, Trichelair & Tachet des Combes, *Safe Policy Improvement with Baseline Bootstrapping* (2019) | Uncertainty-aware evaluation/improvement relative to a baseline and conservative decisions with insufficient data are established research ideas. | Current-packet, finite-horizon vehicle residual admission is a different decision granularity from typical offline policy-level improvement. Exact overlap needs primary verification. | Relevant known literature leads; primary pages were unavailable in this session. No full-text comparison or reproduction claimed. |
| Conformal calibration, including Romano, Patterson & Candès, *Conformalized Quantile Regression* (2019), and Angelopoulos et al., *Conformal Risk Control* (2024) | Held-out calibration of prediction-error quantiles/risk; covariate-dependent uncertainty modeling and statistically conservative decisions are established tools. | An age/context-conditioned bound for incremental benefit, with candidate selection, packet expiry and closed-loop data dependence explicitly handled. | Relevant known literature leads; full texts not retrieved in this session. Do not claim a conformal guarantee simply by naming these methods. |

Primary links: [Wabersich](https://arxiv.org/abs/1812.05506v4), [Kalaria](https://arxiv.org/abs/2208.13856v1). Verification leads: [High Confidence Policy Improvement](https://proceedings.mlr.press/v37/thomas15.html), [SPIBB](https://proceedings.mlr.press/v97/laroche19a.html), [Conformalized Quantile Regression](https://arxiv.org/abs/1905.03222), [Conformal Risk Control](https://arxiv.org/abs/2208.02814). Links in the second group identify works to verify; they are not claims of successful retrieval.

## A precise version of the user's proposal

Define predicted improvement as predicted LQR cost minus predicted candidate-assisted cost over the **same** horizon, initial estimated state, constraints and continuation policy. The candidate includes the actual admissible weight/filter/recovery behavior and only the available packet lifetime, then LQR continuation.

For offline calibration experiments, measure a paired realized cost difference from cloned initial states under matched disturbances/noise and reference. The prediction-overestimation error is:

`error = predicted improvement - paired realized improvement`.

Learn a one-sided upper error allowance `q(age, observable context, candidate)` on separate calibration data. A proposed admission rule is:

`predicted improvement - calibrated upper error allowance > required margin`,

subject to all existing validity, freshness, operating-envelope and execution-budget checks. This is a **proposed new experiment**, not implemented or validated by the existing v13 results.

Illustration only: predicted improvement is0.020 cost units, the calibrated overestimation allowance is0.017, and the required margin is0.005. The conservative benefit is0.003, so assistance is rejected despite a positive point prediction. These numbers are not LANS results or a coverage guarantee.

The useful research question is whether calibrating the **difference directly** can improve the trade-off between harmful admissions and useful assistance compared with a fixed margin or separate conservative bounds on both costs. Paired cost errors may be correlated. This possible advantage must be measured; learning dynamics uncertainty and learning benefit uncertainty are different targets but neither distinction automatically establishes originality.

## Conditions that cannot be skipped

1. **Counterfactual labels:** an executed vehicle trajectory does not reveal what LQR would have done from exactly the same state at the same time. Use explicitly paired simulator branches for offline labels, or a justified off-policy/counterfactual estimator. Comparing different runs/states as if they were a paired true benefit is invalid. Simulator labels are not physical-vehicle ground truth.
2. **Causal context:** use available estimated state, speed, reference curvature, actuator/filter history, packet age and selected authority. Do not use hidden true friction, future response time or future sensor values as deployable calibration inputs.
3. **Bias versus uncertainty:** correcting the mean overestimation is not a calibrated upper error bound. An ensemble standard deviation alone does not establish frequentist coverage.
4. **Conditional coverage:** standard split-conformal coverage is generally marginal under exchangeability, not automatically95% in every age/speed/curvature bin. Sparse conditions, new policies and shifted dynamics need explicit treatment and conservative abstention. Adjacent control ticks are not independent samples; separate by episodes/seeds and justify any temporal assumptions.
5. **Selection:** selecting the best of multiple residuals/weights can invalidate a bound calibrated for one fixed candidate. Calibrate the actual selection procedure or account for simultaneous candidate errors.
6. **Accepted-only risk:** marginal lower-bound coverage does not by itself imply a95% chance of benefit among accepted actions. Conditioning on admission can concentrate errors. Define and calibrate the intended risk explicitly.
7. **Closed-loop reuse:** changing the supervisor changes the visited-state distribution. Repeated adaptive decisions and online updates need their own justification; a fixed offline test-set guarantee does not automatically apply throughout the new closed loop.
8. **Scope:** a bound on tracking-cost improvement is not a vehicle-safety or stability proof. Invalid/stale packets still lose authority, and a slow uncertainty evaluator can still miss the loop deadline.

## Experiment that would establish whether this is useful

Keep the controller, actor, sensing and actuator model fixed. Compare: existing point-prediction gate; a development-tuned fixed margin; a global calibrated error allowance; and an age/context-conditioned allowance. Use the same PPO, student and fixed corrections under each gate. Treat additional candidate-selection changes as separate factors.

Use disjoint fitting, calibration and confirmation episodes. Measure harmful-admission rate, conservative-benefit coverage, coverage by age/context, learned authority, rejected useful candidates, tracking/heading/rate metrics, survival and supervisor execution time. Include sparse/out-of-distribution cases. Test candidate-selection effects and distribution shift explicitly. Preserve all failures and frozen acceptance criteria.

Uncertainty correction may reject more PPO proposals and reduce tracking gains; it cannot create a useful residual where none exists. The goal is better-supported decisions and a useful risk/performance trade-off, not an assumed20% PPO gain.

## Novelty wording

> We investigate calibration of the one-sided overestimation error in predicted incremental benefit of asynchronous neural residuals over LQR, conditioned on proposal age and observable driving context. The resulting bound is incorporated into an expiry-aware admission rule and evaluated against fixed-margin, globally calibrated and nonlearned alternatives.

This identifies a concrete proposed mechanism. "First," a novelty percentage, guaranteed conditional coverage, hard real-time execution, formal safety and journal acceptance are not established. The current contribution level is a **specific candidate methodological extension with substantial prior-art overlap**, pending primary-source comparison and a frozen experiment.

See also [the detailed review of the supplied Doubao conversation](DOUBAO_REVIEW.md).
