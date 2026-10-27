# Frozen follow-up: attribution and smoother residual assistance

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /workspace/lans-venv/bin/python tools/reviewer_followup/run.py --publish
```

No new policy training. The prior3x25k fine-tuned PPO endpoints and causal students
are compared under identical per-profile gates, including both fixed corrections.
Three prespecified smoothing/predictor profiles are screened against the original
age-gain reference. All864 fresh development episodes and failed criteria are
retained; previous campaigns and reserved data are unchanged.

The nominal PSF reference implements the supplied Wabersich–Zeilinger paper's
Section4.1 Eq5/Algorithm1 linear specialization with a terminal equilibrium and
shortened-horizon fallback. Its uncertainty-aware Algorithm2 and authors' code are
not reproduced. Model-certainty/fixed-dynamics assumptions do not hold exactly on
the noisy nonlinear plant; no published safety theorem is inherited. Infeasible
problems and uncertified LQR fallbacks are counted. Source OSQP requirements are
pinned separately and preserve NumPy/SciPy/Torch versions.

Raw filter state is audited causally, and resets immediately when information is
stale/invalid. Valid history may persist during predicted-cost rejection; authority
remains zero until admissible. Confirmation additionally requires independent
observed10ms timing success and a separately frozen manifest. No post-result tuning.
