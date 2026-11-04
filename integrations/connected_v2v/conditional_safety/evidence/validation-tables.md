# Fresh reference validation — safety and progress reported separately

| Profile | Runs | Minimum continuous gap (m) | Maximum spacing RMS (m) | Maximum stopped time (s) | Median progress (m) |
| --- | ---: | ---: | ---: | ---: | ---: |
| steady_connected | 30 | 48.191046 | 45.256 | 0.00 | 475.772 |
| leader_emergency | 30 | 6.049214 | 22.390 | 20.35 | 167.275 |
| v2v_blackout | 30 | 48.191046 | 46.238 | 0.00 | 472.904 |
| dual_blackout | 30 | 6.082835 | 35.537 | 17.25 | 167.257 |
| bounded_sensor_error | 30 | 11.437291 | 26.306 | 0.00 | 403.515 |
| admissible_cutin | 30 | 14.004791 | 19.342 | 0.00 | 433.845 |
| adversarial_nominal | 30 | 2.000022 | 11.218 | 28.65 | 171.349 |
| permanent_blackout | 30 | 48.191046 | 292.207 | 30.35 | 111.685 |

Every intersample minimum is checked exactly before decimal formatting.
These are new 1-D bounded-error reference trials, not Webots validation of the theorem.
Spacing/progress are descriptive and do not form a convergence or superiority claim.
