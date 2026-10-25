# Literature positioning for the current LANS controller

Date: 25 October 2026. Reference implementation: audit commit `e78b691b3e8efee3fd8f18804721a5dc66a4ad9a`. The predictor/objective ablation is a new development experiment; it does not inherit an improvement or novelty claim from this document.

**The defensible contribution is presently an application and experimental-method contribution:** a baseline-preserving, age-aware, performance-gated residual controller, with explicit execution semantics and an auditable comparison of learned versus nonlearned proposals. Residual learning, delay-aware control and predictive filtering each have substantial prior work. Their combination is not, by itself, evidence of a first-of-its-kind algorithm.

## Source-access status

This is a qualified literature-positioning record, **not a completed systematic review or a reproduced algorithm benchmark**. Four closely relevant source leads are identified below. The implementation and result statements are checked against the repository; the external papers could not be retrieved in this session.

A single read-only sandbox escalation requested three arXiv abstract pages, a Crossref title search for Kalaria et al., and the corresponding arXiv title search. All five requests failed with `Tunnel connection failed: 403 Forbidden`. The request itself was not rejected by approval review; the network proxy prevented access. No proxy or access-control bypass was attempted. Thus the paper URLs below are verification leads, not evidence that their pages or full texts were read successfully here.

The original manuscript's bibliography is also not a verified source catalogue. It lists the same residual-RL title under both Chebotar and Johannink, and the same Kalaria title under 2022 and purported 2024 publication entries. Do not count those as independent works without verification. The repository's [review](reviews.md) and [reproduction status](../../research-inputs/REPRODUCTION_STATUS.md) already record unverified references and absent original reference-audit files.

## Four closest prior-work candidates

The selected works cover the nearest method families and vehicle-delay application; this is not an exhaustive ranking of the literature available in 2026. Titles and source leads below must be checked against primary metadata before use in a submission. In particular, do not invent a DOI, venue pagination or direct paper identifier for the unresolved Kalaria entry.

| ID | Source lead | Why it is close | Verification status |
|---|---|---|---|
| R1 | T. Johannink et al., **Residual Reinforcement Learning for Robot Control**, 2019. [arXiv:1812.03201](https://arxiv.org/abs/1812.03201) | A learned residual augments an existing controller; directly overlaps the basic LQR-plus-learned-correction idea. | Primary page blocked. The title also appears in the supplied manuscript, with duplicate/inconsistent author entries. |
| R2 | K. P. Wabersich and M. N. Zeilinger, **A predictive safety filter for learning-based control of constrained nonlinear dynamical systems**, 2021. [arXiv:1812.05506](https://arxiv.org/abs/1812.05506) | Predictive filtering mediates learned commands before they reach a constrained plant. It is a necessary comparison family for any claimed supervisor/filter novelty. | Primary page blocked; no theorem-by-theorem or implementation comparison performed. |
| R3 | S. Ramstedt et al., **Reinforcement Learning with Random Delays**, 2021. [arXiv:2010.02966](https://arxiv.org/abs/2010.02966) | Delayed observations/actions change the effective learning problem and credit assignment; this overlaps the motivation for execution-aware training. | Primary page blocked; no original delay-correcting implementation reproduced. |
| R4 | D. Kalaria, Q. Lin and J. M. Dolan, **Delay-aware robust control for safe autonomous driving**. The original manuscript cites an IV 2022 version and a purported 2024 TCST version. [Primary title search](https://arxiv.org/search/?query=Delay-aware+robust+control+for+safe+autonomous+driving&searchtype=title) | Same vehicle-control application and explicit delay/robustness objective; potentially the closest application-level overlap. | **Exact publication identity unresolved.** Crossref/arXiv lookup blocked. The supplied bibliography is not sufficient to verify either venue entry or to conclude they are separate works. |

The comparison below uses established method-family distinctions and inspected LANS code. It does **not** attribute an omission or weakness to a particular paper whose full text was unavailable. For example, it would be unjustified to say that all residual-RL work ignores latency, all safety filters ignore performance, or all delay-aware methods use fixed fusion.

## Overlap, candidate distinction and unresolved comparison

| Closest family | What already exists | What LANS actually implements | What remains to establish |
|---|---|---|---|
| Residual learning (R1) | Learning a correction around an existing controller rather than replacing it. | LQR remains the default; a bounded proposal receives authority only after freshness/validity checks and predicted improvement of the **actual fused command** over LQR. | The residual formulation is not novel. Whether this particular acceptance/execution design is distinct from the nearest residual controllers requires full-text comparison and matched implementations. |
| Predictive safety/performance filtering (R2 and related work) | A model-based layer evaluates or modifies a learned proposal before execution; classical backup/fallback is a longstanding design pattern. | A nominal short-horizon predictor compares tracking/yaw/effort costs for several ramp-limited fusion weights. It also checks observation age, sequence, envelope and recovery persistence. | LANS has **no formal invariant-set, recursive-feasibility or vehicle-safety certificate**. A predicted cost advantage is not equivalent to a safety guarantee or a guaranteed realized improvement. It must not be presented as stronger than a proven safety filter. |
| Delay-aware reinforcement learning (R3) | Delays alter action availability and the association between observations, actions and rewards. Delay-aware learning is not new. | One-in-flight worker semantics, held/pending packet history, original observation timestamps, age-based rejection and rewards based on the command actually executed. The local LQR does not wait for the learned worker. | No superiority to a delay-correcting RL algorithm is established. Current simulated service cases are bounded protocols, not a general treatment of arbitrary queues, network delays or hardware scheduling. |
| Delay-aware robust vehicle control (R4) | Vehicle tracking under delay and uncertainty is already an active control problem, including nonlearning approaches. | The learned correction is conditional on both measured information age and estimated incremental benefit over a strong classical baseline, evaluated with actuator/sensor limits. | Exact overlap with R4 cannot be settled from its title. No matched reproduction, equal-information comparison, end-to-end timing advantage or robust-control superiority has been demonstrated. |

The executable details are in [the gate](../../integrations/webots/research/revision2/gating.py), [the shared execution interface](../../integrations/webots/research/revision5/execution.py), and [the execution-aware environment](../../integrations/webots/research/revision5/execution_env.py). The original [v0.1 specification](specification-v0.1.md) is a discussion baseline proposing PPO-majority full-command fusion. It is not an accurate description of the best current measured controller.

## The problem being addressed

The narrow research problem is: **when a classical tracker is already strong, can a learned correction earn useful authority despite delayed execution, while preserving the baseline when that correction is stale or unhelpful?**

This separates three issues which a useful experiment must measure together:

1. **Freshness and usefulness are different.** A fast, valid learned command can still worsen tracking. Conversely, an otherwise useful command can become invalid because it was computed from an old observation. LANS tests both before granting authority.
2. **Proposed action and executed action are different.** The worker may be busy, a prior packet may be held, the gate may reject the action, and the actuator may lag. The current shared interface represents this execution state; training solely on an unconstrained proposal would optimize a different system.
3. **A good hybrid score does not prove that learning caused the benefit.** Fixed corrections under the same gate, a finite teacher, the actual sensor-only student, and failed or unhelpful PPO fine-tuning are reported separately. This is stronger attribution than comparing only hybrid versus standalone PPO, although it is not yet a comparison against the closest published algorithms.

These are limitations of particular designs or evaluation practices, not claims that the entire prior literature overlooked them. General remedies already exist; LANS investigates a specific combination under its declared vehicle-tracking protocol.

## What current results support

The [revision8 report](../../integrations/webots/results/revision8-student/report.md) compares five methods on 540 fresh paired surrogate episodes: three optimization/noise pairs, three speeds, two known paths and six condition families. Each method survives 108/108 episodes. Mean failure-penalized episode RMSE reductions versus LQR are:

| Method | Reduction versus LQR |
|---|---:|
| Fixed −0.04 rad proposal through the same gate | 0.819% |
| Finite privileged expected-cost teacher | 2.231% |
| Sensor/history-only supervised student | 2.158% |
| Previous execution-trained PPO reference | 0.098% |

The student is approximately 1.35% better than that fixed correction and equals LQR under the tested severe 100 ms delay. This supports a modest, repeatable benefit from the learned proposal on the declared known task families. It does not establish broad generalization, superiority to published controllers, or that PPO produced the benefit. The teacher and prior PPO also use different data/budgets; their comparison is descriptive.

The current successful student is a **supervised classifier over five residual actions**, trained with privileged finite-teacher labels and observed/history inputs only. In [revision9](../../integrations/webots/research/revision9/README.md), development selection retained the original student for all three fine-tuning seeds; additional PPO training did not improve it. A paper built around the current best evidence should identify the learner correctly.

The [full audit](full-project-audit/README.md) further establishes that the later 50 ms-query diagnostics had a timestamp defect. Corrected replays preserve the originals and supersede their interpretation. They identify predictor/objective disagreements but do not demonstrate 5–10% headroom. The two native audit smoke cases use the legacy model; they are not native validation of the current supervised student.

## How the proposed predictor/objective ablation fits

The next experiment can investigate an unresolved mechanism rather than merely increasing training budget: whether nominal/local-geometry prediction or the decision objective causes harmful approvals and missed useful corrections in tire mismatch.

The proposed development design has three gate arms: the legacy gate, a preview-only predictor change, and a lateral-objective-only change. Each is compared with fixed −0.04 rad, fixed +0.04 rad and the frozen student as proposal sources, with a shared LQR reference. No hidden plant parameters enter the gate. These are proposed ablation arms, not completed results or direct reproductions of R1–R4.

A defensible ablation changes the predictor and objective separately while holding the proposal source, packet timing, candidate fusion limits, gate recovery, actuator, sensors and LQR baseline fixed. It compares whole closed-loop episodes, not only minima from privileged shadow branches. Survival, nominal tracking and exact stale fallback remain declared checks; comparisons retain simple nonlearned proposals. A privileged teacher or true-parameter predictor, if used diagnostically, must remain explicitly nondeployable.

Even if that experiment succeeds, changing a model or a cost is not automatically a new algorithmic contribution. Its contribution would be evidence that a particular mechanism explains and improves selective learned assistance under the stated execution conditions. A stronger methodological claim requires a clear new rule or analysis and direct comparison with relevant existing methods. The protocol and success criteria must precede outcomes, and existing reserved results must not select the new design.

## Defensible paper wording and remaining work

A supportable current claim is:

> We study a baseline-preserving residual vehicle controller that grants learned corrections authority only when their information is fresh and a predictor favors the executed fused command over LQR. A shared asynchronous execution model and matched nonlearned baselines separate proposal quality from supervisory filtering. On the declared surrogate scenarios, a sensor-only distilled policy modestly improves tracking while reproducing LQR under severe delay; PPO fine-tuning adds no demonstrated benefit.

Avoid “first latency-aware hybrid,” “new residual-RL principle,” “PPO dominance,” “guaranteed safety,” “universally better than LQR/MPC,” and “5–10% improvement.” A numerical novelty percentage or a promise of publishability is also unsupported. The name *neuro-symbolic* does not itself establish a symbolic-reasoning contribution: the current implementation has numerical control and explicit supervisor rules, not a demonstrated logic/planning inference method.

Before claiming a literature gap is closed:

- Retrieve and verify the four primary sources, resolve the Kalaria identity and duplicate manuscript citations, and search for more recent directly overlapping performance/age-aware residual controllers.
- Record each close method's actual assumptions, safety/performance objective, timing semantics, learning role and evaluated domains from its full text. Replace the qualified family-level table with a verified paper-level matrix.
- Reproduce at least the closest feasible published method under matched sensors, actuator limits, information, timing, failures and budgets, or explicitly explain why a reproduction is unavailable. A bibliography table cannot replace this benchmark.
- Complete the frozen predictor/objective development comparison and evaluate a selected design only on appropriately reserved new data. Establish the current student's native transfer separately if the paper claims simulator transfer.

This document completes a source-access-limited positioning record. The blocked primary-source review and missing direct literature benchmark remain open, and must not be reported as completed experimental validation.
