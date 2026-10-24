# Separate nonlinear model-bank gate comparison

This is a development-only predictor revision; no policy retraining or hidden plant input.

| Region | Policy | Frozen gate RMSE | Model-bank gate RMSE | Survived /12 |
|---|---|---:|---:|---:|
| nominal | legacy | 0.061223 | 0.061504 | 12 |
| tire_mismatch | legacy | 0.172033 | 0.172332 | 12 |
| low_friction | legacy | 0.080137 | 0.080133 | 12 |
| sensor_stress | legacy | 0.059207 | 0.059318 | 12 |
| latency20 | legacy | 0.060969 | 0.061078 | 12 |
| latency100 | legacy | 0.062646 | 0.062646 | 12 |
| nominal | A100k | 0.062454 | 0.062699 | 12 |
| tire_mismatch | A100k | 0.173859 | 0.173888 | 12 |
| low_friction | A100k | 0.081123 | 0.081048 | 12 |
| sensor_stress | A100k | 0.060656 | 0.060619 | 12 |
| latency20 | A100k | 0.062185 | 0.062416 | 12 |
| latency100 | A100k | 0.062646 | 0.062646 | 12 |

## Frozen promotion screen

{
  "legacy": {
    "checks": {
      "survival": true,
      "regional": true,
      "nominal": true,
      "both_seed_stress": false,
      "severe_exact": true
    },
    "eligible": false
  },
  "A100k": {
    "checks": {
      "survival": true,
      "regional": true,
      "nominal": true,
      "both_seed_stress": false,
      "severe_exact": true
    },
    "eligible": false
  }
}

The model bank uses declared uncertainty values, not true scenario parameters. It still relies on estimated state and approximate local geometry. Lower predictor cost is not a safety guarantee. No model was promoted automatically; the frozen controller and historical results remain unchanged.
