# Frozen follow-up: same-gain attribution and smoothing

| Profile/source | RMSE m | Gain vs LQR | Heading rad | Rate RMS rad/s | Survival |
|---|---:|---:|---:|---:|---:|
| lqr/none | 0.071486 | 0.000% | 0.016738 | 0.061775 | 48/48 |
| age_original/negative | 0.094622 | -32.364% | 0.016812 | 0.061840 | 48/48 |
| age_original/positive | 0.094622 | -32.364% | 0.016812 | 0.061840 | 48/48 |
| age_original/student | 0.065686 | 8.114% | 0.016596 | 0.113815 | 48/48 |
| age_original/ppo | 0.065992 | 7.685% | 0.016596 | 0.113233 | 48/48 |
| age_filtered/negative | 0.078616 | -9.973% | 0.016755 | 0.061838 | 48/48 |
| age_filtered/positive | 0.078616 | -9.973% | 0.016755 | 0.061838 | 48/48 |
| age_filtered/student | 0.067114 | 6.116% | 0.016350 | 0.078943 | 48/48 |
| age_filtered/ppo | 0.067347 | 5.789% | 0.016340 | 0.078754 | 48/48 |
| predictive_filtered/negative | 0.073447 | -2.743% | 0.017002 | 0.062052 | 48/48 |
| predictive_filtered/positive | 0.073447 | -2.743% | 0.017002 | 0.062052 | 48/48 |
| predictive_filtered/student | 0.071486 | -0.000% | 0.016738 | 0.061769 | 48/48 |
| predictive_filtered/ppo | 0.071486 | -0.001% | 0.016739 | 0.061768 | 48/48 |
| preview_filtered/negative | 0.072141 | -0.917% | 0.016695 | 0.061413 | 48/48 |
| preview_filtered/positive | 0.072141 | -0.917% | 0.016695 | 0.061413 | 48/48 |
| preview_filtered/student | 0.070996 | 0.685% | 0.016668 | 0.062064 | 48/48 |
| preview_filtered/ppo | 0.070965 | 0.728% | 0.016663 | 0.062013 | 48/48 |
| nominal_psf/ppo | 0.066875 | 6.450% | 0.016528 | 0.124771 | 48/48 |

Selected eligible profile: None.

Nominal PSF is the disclosed Eq5/Algorithm1 linear specialization with terminal equilibrium. Its model certainty, fixed-curvature/dynamics and perfect-state assumptions do not hold exactly on this nonlinear noisy plant. Solver infeasibility and uncertified LQR fallbacks are retained; no transfer of the paper safety theorem or superiority to its full uncertainty-aware algorithm is claimed.

No new training or after-outcome tuning. Same-gain controls identify whether any benefit comes from the proposal or from supervisory filtering. Previous failed campaigns remain unchanged.
