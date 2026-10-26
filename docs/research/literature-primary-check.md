# Primary-source literature verification: revision13 follow-up

**Later update, 26 October 2026:** the user supplied five PDFs, now reviewed in the [verified primary-paper comparison](primary-papers/README.md). This resolves local full-text access for Kalaria, Tearle, Wabersich–Zeilinger, Cano Córdoba and Tabrizian v5. The earlier proxy failures below remain an accurate historical record; they no longer block review of these uploads. Johannink and Ramstedt were not supplied, broader coverage/final publisher metadata remain incomplete, and no published controller has been reproduced. [Opening-report supplement](../opening-report/verified-related-work.md).

**Earlier access attempt, 26 October 2026.** This follow-up accompanied the balanced-gate investigation and extended the [qualified literature positioning](literature-positioning.md). At that point, primary-paper verification remained incomplete because the configured network route rejected the source requests. The remaining sections preserve that earlier attempt, its bibliographic leads and its then-open checks; use the later comparison above for present source status.

## Access attempts and local evidence

The available tools were checked again; no web-search or browser tool was exposed. Seven standard HTTPS requests were attempted through the configured network route, with a 15-second timeout and no proxy override. All seven failed before an article or metadata response was returned, with:

```text
<urlopen error Tunnel connection failed: 403 Forbidden>
```

| Attempt | Requested source | Outcome |
|---|---|---|
| R1 abstract | `https://arxiv.org/abs/1812.03201` | Proxy tunnel HTTP 403 |
| R2 abstract | `https://arxiv.org/abs/1812.05506` | Proxy tunnel HTTP 403 |
| R3 abstract | `https://arxiv.org/abs/2010.02966` | Proxy tunnel HTTP 403 |
| R4 title search | arXiv title search for “Delay-aware robust control for safe autonomous driving” | Proxy tunnel HTTP 403 |
| R4 metadata search | Crossref works query for the same title, three results requested | Proxy tunnel HTTP 403 |
| R1 DOI metadata | `https://doi.org/10.1109/ICRA.2019.8794127`, CSL JSON requested | Proxy tunnel HTTP 403 |
| R2 DOI metadata | `https://doi.org/10.1016/j.automatica.2021.109597`, CSL JSON requested | Proxy tunnel HTTP 403 |

The initial requests were recorded at 08:26 UTC / 16:26 Asia/Shanghai on 26 October 2026; the [raw access log](../../integrations/webots/results/revision13-balanced/verification/literature-access.json) is archived. This was a network-proxy access failure, not an automatic approval rejection. No access-control bypass was attempted. The prior positioning record separately documents an earlier unsuccessful escalated read; repeating that escalation was not necessary to claim a new result here.

The [new opening-report Word document](../opening-report/Rizwan_Ali_LANS_Opening_Report_Final.docx) was inspected locally. Its reference [4] supplies the Johannink DOI and reference [10] supplies the Wabersich–Zeilinger DOI used above. Its [README](../opening-report/README.md) explicitly says external reference verification was incomplete and bibliography metadata needs independent verification. Thus these DOI strings are useful search leads, **not independently verified metadata**. That revised bibliography does not contain the Ramstedt or Kalaria source leads and cannot resolve their identity for us.

## Closest-source matrix and required paper-level checks

| Lead | Bibliographic information available locally | Method-family overlap with LANS | Exact comparison that remains unverified |
|---|---|---|---|
| R1 | T. Johannink et al., *Residual Reinforcement Learning for Robot Control*; supplied report lists ICRA 2019, pp. 6023–6029, DOI `10.1109/ICRA.2019.8794127`; earlier lead `arXiv:1812.03201`. | A learned residual augments an existing controller. This principle is already established and is not a LANS novelty claim. | Verify the paper's actual base-controller/proposal composition, information and training assumptions, timing treatment, task scope and ablations. Do not infer that it lacks delay handling or performance supervision solely from its title. |
| R2 | K. P. Wabersich and M. N. Zeilinger, *A predictive safety filter for learning-based control of constrained nonlinear dynamical systems*; supplied report lists *Automatica* 129, 109597 (2021), DOI `10.1016/j.automatica.2021.109597`; earlier lead `arXiv:1812.05506`. | A predictive layer mediates proposed control. It is a necessary comparison family for any claimed supervisory/filter contribution. | Read the exact model, constraint, feasibility and safety assumptions, objective and intervention rule. LANS has no comparable formal safety certificate; predicted tracking benefit must not be equated with a theorem from this source. |
| R3 | S. Ramstedt et al., *Reinforcement Learning with Random Delays*; earlier lead `arXiv:2010.02966`, 2021 publication year unverified here. | Observation/action delay changes action availability and learning credit. LANS's packet lifecycle and executed-action reward address a related execution problem. | Verify delay distributions, observation versus action delay, queue/buffer semantics, delayed-action credit assignment and available implementation. LANS's declared scheduler cases do not establish superiority to that algorithm. |
| R4 | D. Kalaria, Q. Lin and J. M. Dolan, *Delay-aware robust control for safe autonomous driving*; original manuscript has unresolved IV 2022 and purported TCST 2024 entries. No exact DOI or paper identifier verified. | Closest identified application-level lead: vehicle control under delay and uncertainty, including nonlearned robust control. | Resolve whether the entries identify one work/version or distinct papers. Then compare dynamics, delay estimation/compensation, uncertainty, constraints, path geometry, sensing and computation assumptions. A title match cannot establish that LANS solves an omission in this work. |

This matrix deliberately separates method-family overlap from paper-specific findings. No full text was available, so it would be unjustified to attribute a particular missing feature, inferior metric, unsupported theorem, or failed experiment to these authors. There has also been no exhaustive search for more recent work or proof that these four are the closest publications available in 2026.

## Consequences for the current contribution claim

Repository evidence supports a bounded control/evaluation contribution, not a first-of-its-kind residual-RL or delay-compensation principle. The [revision12 experiment](../../integrations/webots/results/revision12-ablation/interpretation.md) found 4.528% lower mean lateral RMSE for the frozen student under a lateral-only gate objective, while the same gate with fixed proposals achieved 6.864% and 9.122%. Its representative traces also exposed heading and steering-activity costs. The larger nonlearned gain cannot be presented as evidence that PPO learning produced the improvement.

The completed [balanced-gate follow-up](../../integrations/webots/results/revision13-balanced/interpretation.md) replicates the original-positive nonlearned gain at 9.131% and finds 7.049% on the expanded mirrored grid. Full-grid steering-rate RMS and total movement rise by 36.543% and 48.823% versus LQR. Three balanced profiles reduce movement but worsen tracking; no candidate qualifies for reserved/native/learning stages. This improves the **mechanistic attribution** and trade-off evidence, but does not establish algorithmic novelty, statistical superiority, a literature gap closed, or success against the named published methods.

The newly merged [real-worker timing campaign](realtime-latency-2026-10-26/README.md) also makes an important scope distinction: functional fault handling passed, while strict 10 ms software-response timing failed. It is software-in-the-loop evidence, not native Webots, physical I/O or hard-real-time certification. A literature comparison must use the measured timing result and the disclosed causal-feature adapter, rather than describe LANS as deadline-guaranteed.

## What remains necessary

1. Obtain accessible primary records/full texts for R1–R4, verify author/title/venue/year/DOI mappings, and resolve the duplicated or inconsistent original citations.
2. Record actual assumptions and mechanisms from those texts. Replace the unresolved-question column with paper-specific, page/section-supported comparisons only after reading them.
3. Search for directly overlapping age-aware performance filters and residual vehicle controllers, including more recent publications. Do not use a four-paper sample to support “first” or comprehensive novelty claims.
4. Choose a feasible closest published method for a matched reproduction, with common paths, disturbances, sensors, actuator bounds, action-age definitions, failure accounting and declared computational budgets. Any inability to reproduce it must be explained rather than substituted with a bibliography table.
5. Keep the controller's measured tracking/heading/steering trade-offs, functional fallback, actual deadline results, and formal-safety status separate in the paper.

Until these checks are possible, the supportable wording is: **“We investigate execution-aware selective correction and the effect of supervisory objectives under a declared vehicle-tracking protocol, with matched nonlearned controls and explicit limits.”** The primary-source review and direct published-method comparison remain open work; no new literature-performance claim was verified in this retry.
