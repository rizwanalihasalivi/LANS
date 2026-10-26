# LANS research handoff — 24 October 2026

For present status, see the [full project audit and corrections](full-project-audit/README.md). The initial handoff below is historical.

The latest [mirrored confirmation and balanced-control study](../../integrations/webots/results/revision13-balanced/interpretation.md) verifies the original nonlearned gain at 9.131% with fresh noise and records full-grid heading/steering metrics across 7,776 surviving episodes. None of three balanced objectives preserves tracking, so reserved/native/learning stages remain untriggered. [Primary-source literature verification](literature-primary-check.md) remains proxy-blocked.

The preceding [predictor/objective ablation](../../integrations/webots/results/revision12-ablation/interpretation.md) distinguishes a 4.528% student tracking gain from larger 6.864%/9.122% nonlearned gains, records heading/steering trade-offs, and stops further training under its frozen criteria.

This checkpoint preserves environment work, supplied research materials, reviews and design discussions before new experiments. The updated controller is **proposed, not implemented or validated**. Existing repository code and historical results must not be presented as results of the new design.

- [Design and experimental specification v0.1](specification-v0.1.md)
- [Discussion decisions and next steps](decisions.md)
- [Review findings](reviews.md)
- [Environment setup and verification record](../../tools/cloud/README.md)
- [Original uploaded materials](../../research-inputs/README.md)

These documents summarize the discussion; they are not a verbatim chat transcript. Source attachments are preserved separately. User authorization for this checkpoint is to publish completed work and discussion to GitHub. New research experiments remain a subsequent phase.

## Subsequent independent audit

[ARIS project audit — 25 October 2026](../../EXPERIMENT_AUDIT.md) reviews commit `966e034`, including later controller repairs and research revisions. Current research receives a qualified WARN; unrestricted repository-wide evidence acceptance receives FAIL for the documented remaining reporting/provenance issues. See the linked coverage ledger for inspected and unverified material.
