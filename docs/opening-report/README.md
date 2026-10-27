# LANS opening report

New experimental method addition: [explicit response-delay input compensation](../research/reviewer-delay-compensation-v7/README.md).
The supervisor forecasts physical policy inputs over a capped causal delay
estimate; latest-state admission and the original 50ms stale threshold remain.
This does not cancel physical sensor/communication/LQR-feedback delay. The
72-episode diagnostic shows mixed gains; frozen-policy distribution shift,
full selection and strict real-time requirements remain unresolved.

Latest evidence: [submitted-action credit study and timing attribution](../research/reviewer-credit-v6/final-update.md).
Six more fixed 100,000-transition pilots and 672 fresh episodes are verified.
Submitted-only PPO gains 2.611% over LQR and 0.561% over the student; full
selection fails. The separate platform diagnostic has 657/7,500 controller
deadline misses and 587/3,000 native heartbeat misses. Functional fallback
passes. No new winner, reserved/native confirmation or vehicle readiness is
claimed. The original twelve reviewer concerns are explicitly tracked in the
[response-status checklist](../research/reviewer-credit-v6/reviewer-response-status.md).

Latest evidence: [causal-history correction and matched training ablation](../research/reviewer-history-v5/final-update.md).
Six fixed 100,000-transition pilots and 672 fresh development episodes are
complete. The balanced diagnostic gains 2.956% over LQR, but its 0.943% gain over
the student fails the frozen 1% requirement. The history variant also exceeds
the steering-rate limit. No winner is selected; strict timing, reserved/native
confirmation and actual hardware validation remain incomplete.

Latest research evidence: [27 October2026 interface/compute diagnosis](../research/reviewer-interface-v4/final-update.md).
Realistic delivery and freshness-only authority improve the unchanged PPO to
2.579% tracking gain over LQR with balanced heading/rate metrics. Full selection
still fails the1% student margin; strict timing and physical validation remain
unresolved. Worker stall/recovery is functionally verified for three seeds.

Prior research evidence: [aligned update](../research/reviewer-aligned-v3/final-update.md).
The new576-episode comparison passes the balanced-versus-LQR screen, but PPO's
approximately0.33% gain over the student remains below the required1% margin.
Full promotion, reserved confirmation, strict timing and actual hardware
validation are still incomplete. The older864-episode follow-up is preserved.

Revised report for Rizwan Ali, uploaded on 26 October 2026 using the author's selected final framework.

- [Editable Word report](Rizwan_Ali_LANS_Opening_Report_Final.docx)
- [PDF reading and printing copy](Rizwan_Ali_LANS_Opening_Report_Final.pdf)

The report distinguishes the retained supervised controller and recorded results from proposed conditional research. The Word equations are editable; the PDF is independently typeset from the same reviewed content, so pagination may differ.

This report is a historical snapshot. Subsequent original-residual PPO work is
tracked in the [reviewer-response campaign](../../tools/reviewer_campaign/README.md)
and its [evidence/status](../research/reviewer-causal-v1/status.json). The old report
must not be read as completed validation of new PPO policies, full-command
PPO/LQR switching, or hard-real-time execution. A research update will accompany
the new evidence; unresolved bibliography verification still prevents treating
the package as submission-ready.

Before institutional submission, fill in the Student No. and official Major on the cover and independently verify bibliography metadata. External reference verification was incomplete because the source sites could not be accessed during the review. The original cover date of 25 October 2026 is retained.

The later [verified related-work supplement](verified-related-work.md) reviews five user-uploaded primary papers, supplies version-specific citations, and updates the comparison to the completed revision13 results. The existing Word/PDF files above are unchanged; use the supplement when preparing their next revision. The [primary-source ledger](../research/primary-papers/README.md) distinguishes verified paper claims from remaining metadata, novelty-search and reproduction work.
