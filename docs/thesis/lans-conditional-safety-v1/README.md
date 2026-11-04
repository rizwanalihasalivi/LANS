# LANS simulation thesis and conditional longitudinal proof

Prepared 4 November 2026 (Asia/Shanghai). Author: Rizwan Ali.

- [PDF thesis draft](LANS_Simulation_Conditional_Safety_Thesis.pdf)
- [Editable Word thesis draft](LANS_Simulation_Conditional_Safety_Thesis.docx)
- [Shared Markdown source](LANS_Simulation_Conditional_Safety_Thesis.md)
- [Detailed theorem and assumptions](../../../integrations/connected_v2v/conditional_safety/THEOREM.md)
- [Execution/admission scope notes](../../../integrations/connected_v2v/conditional_safety/PROOF_SCOPE_NOTES.md)
- [Verified results and evidence](../../../integrations/connected_v2v/conditional_safety/RESULTS.md)

The draft contains the problem statement, version-specific related work, LANS
architecture/evidence boundary, formal model, inductive safety argument, mechanical
verification scope, experiment protocol, audited results, limitations and
reproducibility appendix. PDF and Word use the same Markdown and result tables;
Word equations are editable. Institution/degree/student-number declarations are
not invented. Existing opening reports are preserved.

Verified: 12 algebraic UNSAT obligations, five SAT negative controls, 2,160 exact
boundary checks, 72/72 development and 240/240 fresh reference runs, three semantic
corruptions rejected after rehashing, and 164 automated tests. The fresh minimum
continuous bumper gap is 2.0000224264971727 m against a 2 m requirement.

**The claim is conditional longitudinal safety under the written assumptions.**
The new reference assumes a fixed straight corridor, valid bounded observations,
complete protected-object coverage, non-reversal, recoverable initialization/
admissions and a valid braking/update envelope. The reference runs on a fixed
50 ms model grid; it does not establish a variable-period implementation or a
measured hard deadline. It does not certify the broader
2-D LANS/Webots implementation, arbitrary hidden cut-ins, real-time execution or
a physical vehicle. Hardware was not used.

Safety is distinct from performance: permanent blackout can cause an indefinite
stop and large nominal spacing error. Deliberate outside-contract collision
examples are retained. The proof combines an analytical flow/induction argument
with SMT-checked algebra; it is not a proof-assistant-kernel or full source-code
correctness certificate. Final comparative benchmarking remains on hold.

The draft is ready for technical/supervisor review, not asserted institutionally
submission-ready. Official front matter, institution formatting and any later
comparative study are separate remaining tasks.
