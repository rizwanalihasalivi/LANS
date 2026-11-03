# Fixed runtime alternative, declared after training and before prospective tests

The four-candidate training selection is complete. The original v6-h2 candidate
is the minimum-RMSE eligible tracking winner (0.088436409 m training mean).
The conic-h2-q110 candidate is eligible at 0.088473624 m, about 0.042% higher
RMSE, with the same 2 s horizon and original actual quality/progress limits.
The conic-h1-q104 candidate fails quality and is not promoted.

Keep the tracking selection unchanged. Independently evaluate the already tested
conic-h2-q110 as a fixed engineering/runtime alternative; do not add hyperparameters
or select an alternative after prospective outcomes. This addition is motivated
by the outstanding real-worker deadline misses. It is a distinct causal algorithm,
not a claim of v6 bitwise equivalence and not a pass of its rejected fused backend.

Freeze both candidate identities before any new development case is evaluated.
Use identical 32 prospective development cells, 24 stress cells and original
failure regressions. Share byte-identical non-MPC comparators (LQR, fixed,
deterministic and PPO-only) with explicit provenance; evaluate the alternative's
optimized/adaptive/hybrid branches separately. Total: 752 tracking-winner episodes
plus 480 alternative episodes; 272 shared comparator records are not extra trials.
Keep separate gates, protocols and all raw outcomes; no favorable mixing of methods.

Run exactly the same fixed nine actual-worker checks for both implementations,
all three policies on nominal following, curved ego-blackout and merge crash,
six seconds each. Complete all CPU simulation jobs first. Warm startup/JIT/gains
separately and measure full input-to-issue/cycle timings at a 50 ms budget. Keep
all misses, no slow-case retry. Comparisons are finite shared-cloud measurements,
not WCET or a guarantee. A reduction in compute time cannot satisfy a requested
30% tracking-RMSE target. Report both primary whole-episode and prespecified
secondary phase results, never substitute a phase gain for whole-episode gain.

The minimum-RMSE tracking winner remains the primary controller. The engineering
alternative is not silently adopted after seeing test results. Reserved/formal
runtime promotion/Webots remain unopened unless all original gates and the
requested 30% whole-episode criterion are met under the declared procedure.
No draft, figure or presentation table is produced.
