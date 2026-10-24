# Pilot selection

Four candidates, two training seeds each, 100k steps per run. All scores are paired development results, not final tests.

| Candidate | Survived / 72 | Mean penalized RMSE (m) | Nominal / LQR | Eligible |
|---|---:|---:|---:|---|
| baseline | 72 | 0.083973 | 0.992880 | True |
| low_exploration | 72 | 0.084256 | 0.996703 | True |
| tracking_reward | 72 | 0.084322 | 0.997839 | True |
| larger_network | 72 | 0.084234 | 0.993599 | True |

Selected **baseline** by the predeclared rule. Freeze this selection before full training and reserved evaluation. A short pilot ranking does not guarantee the same ranking after one million steps.
