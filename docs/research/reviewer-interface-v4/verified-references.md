# Version-specific primary-source bibliography

Verified against the five PDFs supplied by the author, not inferred publisher
metadata or search snippets. Preprints are cited as the actual supplied versions;
no unverified journal year, volume, DOI or publication status is added. This
completes these five reference entries, not a systematic literature search or an
audit of every citation in the original manuscript.

1. B. Tearle, K. P. Wabersich, A. Carron, and M. N. Zeilinger, “A predictive safety
   filter for learning-based racing control,” arXiv:2102.11907v1, 23 February 2021.
   Title, authors, identifier and date appear on the supplied first page.
2. F. Cano Córdoba, A. Palmisano, M. Fränzle, R. Bloem, and B. Könighofer,
   “Safety Shielding under Delayed Observation,” in *Proceedings of the
   Thirty-Third International Conference on Automated Planning and Scheduling
   (ICAPS 2023)*, pp. 80–85, 2023. Conference title/year are in the first-page
   header; the supplied six-page proceedings article has page numbers80–85.
3. K. P. Wabersich and M. N. Zeilinger, “A predictive safety filter for
   learning-based control of constrained nonlinear dynamical systems,”
   arXiv:1812.05506v4, 17 May 2021. This is the version used for the disclosed
   nominal Eq. (5)/Algorithm1 specialization in reviewer-followup-v2.
4. D. Kalaria, Q. Lin, and J. M. Dolan, “Delay-aware Robust Control for Safe
   Autonomous Driving and Racing,” arXiv:2208.13856v1, 29 August 2022. The supplied
   masthead says *IEEE Transactions on Intelligent Vehicles*, not *IEEE
   Transactions on Control Systems Technology*. It does not independently verify
   final volume/year/DOI; the citation therefore uses the verified arXiv version.
5. A. Tabrizian, Z. Huang, A. Aziz, and P. Wei, “Delay-Aware Reinforcement Learning
   for Highway On-Ramp Merging under Stochastic Communication Latency,”
   arXiv:2403.11852v5, 27 May 2026. The supplied version reports DAROM; results or
   titles from an older version must not be silently substituted.

## What their results establish relative to LANS

| Reference | Primary evidence relevant to LANS | Comparison boundary |
|---|---|---|
|1| Predictive filtering, backup trajectories, an80Hz implementation and1:28-scale physical vehicle experiments | Stronger physical/formal evidence than current LANS; its rate is not an inference-speed comparison |
|2| Safety games/shielding under delayed observations, including CARLA examples | Observation delay differs from delayed PPO-worker availability with fresh local sensing |
|3| Predictive safety filtering with backup/terminal constructions and uncertainty treatment | LANS has only a disclosed nominal specialization; its uncertified LQR fallback is not their theorem |
|4| Vehicle computation/actuator-delay handling, robust control and learned-command guarding | Close application overlap; LANS cannot claim that delay-aware supervision itself is new |
|5| SUMO on-ramp merging, delay-aware encoding and physics-based fallback;99.80% success in the reported high-density2s communication-delay condition | Different task, algorithm and delay mechanism; this percentage cannot rank against LANS tracking RMSE |

No one of these numerical results ranks LANS as “#1.” A matched implementation,
common task/plant, sensing and actuator assumptions, compute resource, training
budget, seeds and delay mechanism would be required. Formal guarantees also
cannot be compared using empirical survival alone. These verified entries should
replace inconsistent metadata for these five works in a revised bibliography.

## Claims that still require evidence

- Reproduction of the complete robust published algorithms/authors code.
- A broader up-to-date prior-art search, including original residual-RL and
  Simplex/runtime-assurance primary references.
- Any claimed novelty, formal safety, physical readiness or universal ranking.
- Every other entry and in-text citation in the original manuscript.

Full uploaded PDFs are not republished in this repository.
