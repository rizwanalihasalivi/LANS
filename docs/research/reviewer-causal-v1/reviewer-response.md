# Reviewer response: experimental evidence draft

This document records work performed and remaining limitations. It is not a claim that all reviewer concerns are resolved, nor a submitted response.

## Comment 1: Novelty / neuro-symbolic

Explicit supervisor predicates, states and transitions specified. Contribution remains application/method evaluation; no first-of-kind claim. Broader verified literature comparison remains incomplete.

## Comment 2: Latency reward

New causal PPO pilots omit exogenous latency penalty and privileged counterfactual bonus. Executed tracking/heading/effort/smoothness determine reward. This corrects the causal claim; it is not a matched retraining reproduction of every original reward ablation.

## Comment 3: Delay implementation

One-in-flight request with original observation timestamps; plant evolves each10ms while unavailable. No pending output/forecast/service oracle enters policy. Simulated-service and actual worker tests are distinct.

## Comment 4: LQR delay contradiction

PPO service delay is separated from local sensor/controller latency. Long PPO stalls do not mean delayed LQR feedback is tolerated. Actual backup response timing reported separately.

## Comment 5: 49x speedup

Original speedup withdrawn. Inference and command-processing distributions are measured;100Hz is not used as PPO inference duration. No cross-hardware speed ranking.

## Comment 6: Ablation timing

Each evaluated arm records actual inference/processing time. Reward/gain removal is not assigned a100Hz inference frequency. Asynchronous processing costs remain separate.

## Comment 7: LQR degradation

LQR-only, same-supervisor constants, causal supervised initialization, scratch and fine-tuned PPO included. Negative gains and heading/steering tradeoffs retained; no automatic promotion.

## Comment 8: Generalization

Development uses known sine/DLC families with exact mirrored physical/noise conditions. New sine parameters reserved only for conditional confirmation. This is not broad unseen-road generalization.

## Comment 9: Stability

Nominal LQR Lyapunov result limited to its linear assumptions. No zero convergence from bounded residual, nonlinear global safety or guaranteed delay robustness is claimed. Saturation/actuator constraints are experimental checks, not proof.

## Comment 10: Missing details

Frozen protocol includes reward coefficients, categorical5 distribution, preprocessing, seeds, budgets, gains/recovery and delay handling. Three training seeds, raw traces, source/model provenance and episode-level metrics retained.

## Comment 11: Energy / blind distance

Unsupported GPU energy and end-to-end freshness comparisons removed. No energy measurements or physical sensor-to-actuator latency are claimed.

## Comment 12: Numerics / citations

New tables generated from raw traces and independently recomputed. Original bibliography is not certified; primary metadata and complete citation verification remain pending.

## Current evidence

Grid: development; episodes: 864; eligibility: False.

See [development results](development/README.md) and status.json for external/uncompleted work.

## Uncompleted external/theoretical requirements

- **physical_vehicle:** unavailable: fresh physical measurements required
- **laptop_rerun:** pending user target-machine results
- **formal_safety:** not established; limited assumptions only
- **primary_reference_verification:** uploaded five PDFs read; publication metadata / broader search incomplete
- **published_algorithm_reproduction:** not implemented; no superiority claim
- **native_ppo:** {'interface_pass': True, 'observed_wall_timing_pass': False, 'scope': 'PPO-export/shared supervisor native interface; no generalization or vehicle claim'}
- **hard_realtime:** FAIL: observed10ms deadline misses; no100Hz guarantee
