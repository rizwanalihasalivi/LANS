# Original manuscript bibliography audit

All 32 entries were structurally reviewed against the supplied manuscript. This is not a claim that all publisher metadata or cited numerical statements have been independently verified. The five uploaded PDFs support the version-specific entries in ../reviewer-aligned-v3/verified-references.md. No external publisher access or unseen primary source is invented.

| Original entry | Status and required correction |
|---|---|
| [1] | Primary-source metadata verification pending.  |
| [2] | Primary-source metadata verification pending.  |
| [3] | Primary-source metadata verification pending.  |
| [4] | Primary-source metadata verification pending. Introduction ECU hardware/clock assertion requires an actual ECU datasheet; GPU white paper/driving survey is not sufficient primary evidence for that exact hardware claim. |
| [5] | Primary-source metadata verification pending. Introduction ECU hardware/clock assertion requires an actual ECU datasheet; GPU white paper/driving survey is not sufficient primary evidence for that exact hardware claim. |
| [6] | Primary-source metadata verification pending. Introduction cites this LQR book for GPU power figures; the in-text evidence mapping must be replaced or the unsupported numeric claim removed. |
| [7] | Primary-source metadata verification pending. Do not use a generic vehicle-dynamics/model reference as evidence for neural inference WCET; require directly relevant measured/certified timing evidence. |
| [8] | Primary-source metadata verification pending. Do not use a generic vehicle-dynamics/model reference as evidence for neural inference WCET; require directly relevant measured/certified timing evidence. |
| [9] | Primary-source metadata verification pending.  |
| [10] | Primary-source metadata verification pending.  |
| [11] | Primary-source metadata verification pending.  |
| [12] | Primary-source metadata verification pending.  |
| [13] | Primary-source metadata verification pending.  |
| [14] | Primary-source metadata verification pending.  |
| [15] | Primary-source metadata verification pending.  |
| [16] | Primary-source metadata verification pending.  |
| [17] | Primary-source metadata verification pending.  |
| [18] | Replace and deduplicate using supplied Kalaria arXiv2208.13856v1. Both entries appear to refer to the same work; their IV/TCST venue claims do not match the supplied TIV masthead. Use verified version-specific title including “and Racing”; do not invent final volume/DOI. |
| [19] | Primary-source metadata verification pending.  |
| [20] | Primary-source metadata verification pending.  |
| [21] | Primary-source metadata verification pending.  |
| [22] | Primary-source metadata verification pending.  |
| [23] | Primary-source metadata verification pending. Duplicate title and venue/year with different author attribution; consolidate only after original primary paper is checked. |
| [24] | Primary-source metadata verification pending. Duplicate title and venue/year with different author attribution; consolidate only after original primary paper is checked. |
| [25] | Primary-source metadata verification pending.  |
| [26] | Replace and deduplicate using supplied Kalaria arXiv2208.13856v1. Both entries appear to refer to the same work; their IV/TCST venue claims do not match the supplied TIV masthead. Use verified version-specific title including “and Racing”; do not invent final volume/DOI. |
| [27] | Primary-source metadata verification pending.  |
| [28] | Primary-source metadata verification pending.  |
| [29] | Primary-source metadata verification pending.  |
| [30] | Primary-source metadata verification pending.  |
| [31] | Primary-source metadata verification pending.  |
| [32] | Primary-source metadata verification pending.  |

Before submission, obtain/verify every retained primary source and rebuild in-text numbering after deduplication. Remove unsupported 49-fold speedup, GPU/CPU energy, total blind-distance, global stability and generalization claims rather than attaching unverified citations. An inference benchmark is not a control-period benchmark.

The full robust vehicle-comparator gap is also explicit: a model-error confidence construction, uncertainty-consistent constraint tightening, terminal safe set/controller, initial feasibility and solver-failure/shrinking-horizon handling are needed. The independently verified scalar Algorithm2 contract exercises those mechanisms under its own declared assumptions; it cannot transfer its guarantee to Gaussian noisy-state nonlinear LANS.
