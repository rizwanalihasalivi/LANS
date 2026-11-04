# Conditional safety: completed verification and reference evidence

Prepared 4 November 2026 (Asia/Shanghai), after parent checkpoint `9daa1487`.
This is a new **one-dimensional bounded-error reference study**, not a retroactive
certificate for the existing curved/dense Webots controller or a hardware result.

## Verified outcomes

| Evidence | Outcome |
| --- | --- |
| Written contract, comparison lemma and inductive proof | [THEOREM.md](THEOREM.md), with [execution scope](PROOF_SCOPE_NOTES.md) |
| Z3 nonlinear real-arithmetic obligations | **12/12 UNSAT** |
| Deliberately invalid SMT controls | **5/5 SAT**, witnesses retained |
| Exact parameter/boundary grid | **2,160/2,160 passed** |
| Source-frozen development | **72/72 passed**, 57,600 intervals |
| Fresh reference validation | **240/240 passed**, 192,000 intervals |
| Independent stdlib exact audit | **312/312 episodes passed** |
| Semantic corruptions after trace rehashing | **3/3 rejected** |
| Full V2V automated tests | **164 passed** |

The required front/rear bumper margin is **2 m**. The exact intersample minimizer
found no violations in either valid cohort. Minimum continuous gap was
**2.000204812940913 m** in development and **2.0000224264971727 m** in fresh
validation (decimal representations; checks use exact fractions, without a
negative-margin tolerance). These are finite supporting trials. The all-time
conditional claim comes from the invariant argument and its stated premises.

Fresh validation uses eight profiles × three speeds (8/12/16 m/s) × ten NEW seeds;
development uses three different seeds. Runs last 40 s at 0.05 s physical model
intervals. Source hashes match the development freeze; sources were not tuned
after opening validation. All 249,600 development/fresh intervals are retained.

## What the conditional claim means

Given valid ego upper bounds, associated obstacle rear-position lower bounds,
non-reversing protected objects, initial/admission stopping feasibility and a valid
actuation/update envelope, the reference guard preserves longitudinal bumper gap
≥2 m. New admissions happen before choosing a command at update boundaries.
Indefinite message loss is permitted because a valid old rear-position lower bound
remains a spatial fact; it is never relabeled as fresh velocity/state.

Example model parameters are guaranteed braking 5.5 m/s², acceleration tracking
error at most 0.25 m/s² and a fixed reference update interval of 0.05 s, with no
longer hold certified. Variable-period ports need their own bound propagation.
These values are
assumptions, not physical measurements. The protected corridor is fixed/straight,
and hidden lateral intrusions are excluded. See A1–A6 and the scope notes.

The proof comprises an analytical flow comparison/induction argument plus
solver-checked algebraic obligations. It is not a proof-assistant-kernel or full
Python correctness certificate, an established hard execution deadline, a native
actuation refinement, an arbitrary 2-D cut-in guarantee or real-world validation.

## Performance and excluded diagnostics remain visible

No progress gate is imposed for this safety study. Permanent blackout can require
an indefinite stop. Maximum fresh-reference stopped time is **30.35 s** and maximum
nominal spacing RMS is **292.207 m**, on the permanent-blackout profile. The
adversarial nominal profile has abrupt shield changes: no jerk/comfort guarantee
is supplied. Correct separation is not settled nominal formation.

The boundary package deliberately falsifies assumptions:

| Outside-contract diagnostic | Minimum bumper gap | Interpretation |
| --- | ---: | --- |
| 16 m/s, stationary object only 1 m ahead | **−22.272727 m** | Initial recoverability false; admission rejected |
| Braking only 2 m/s² when 5.5 m/s² was assumed | **−38.727273 m** | Actuation premise false |

These collision examples are preserved and never counted among valid-cohort
passes. Rehashed sensor containment, unsafe guard and plant-transition mutations
are independently rejected. SAT controls demonstrate failed premises/recoverability,
not a measured collision probability or a final controller benchmark.

## Artifacts

- [English thesis draft: PDF, Word and shared Markdown](../../../docs/thesis/lans-conditional-safety-v1/README.md).
- [Full protocol and seeds](PROTOCOL.md), [commands](README.md).
- [Complete raw evidence archive index](evidence/INDEX.md) and [checksums](evidence/SHA256SUMS).
- [Per-profile results](evidence/validation-tables.md).

All final reference raw trajectories, execution source, proof scripts/results,
negative diagnostics, audits, environment records and the thesis are archived.
The actual runtime freeze and later reporting sources are separately inventoried.
Archived standalone audit/replay checks are recorded alongside the archive index.

The original broader evidence remains unchanged: Python 240/240, native 300 m
36/36, native 150 m 35/36, with large spacing and one censored Python stable-return
interval disclosed in [robustness/RESULTS.md](../robustness/RESULTS.md).
Those cohorts are outside this new theorem's deterministic longitudinal contract.
Final thesis comparison/benchmarking remains on hold.
