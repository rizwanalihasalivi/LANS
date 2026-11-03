# Equivalent backend correction, declared before its timing rerun

The first nine selected-controller functional checks retain four >50 ms
input-to-issue/cycle misses out of 1,080 ticks (maximum about 51.37 ms).
No case is deleted. The bottleneck repeats physical integration once to project
each steering plan and again to score that same projected trajectory.

Fuse projection/scoring into one traversal with identical dynamics, constraints,
candidate order, amplitudes, objective and selection comparisons. Verify exact
refined-plan array equality on 96 fixed random state/plan/model/route cases,
including both 1 s and 2 s horizons. Cost/margin consistency tolerance remains
1e-12. Do not change tuning, policies, thresholds or search budget.

Also compare all eight previously recorded full-controller trajectories from
the first traffic replicate of each scenario at nominal and delayed-command
profiles. Require issued/applied commands and all physical states to match at
1e-12 absolute tolerance; preserve repeated diagnostic traces separately and
do not count them as new independent trials.

Disclosed verification amendment: the first historical-trace regression failed
at case 32 with a maximum state difference of 2.073e-10 versus the 1e-12 bound.
An isolated diagnosis reproduces both original and fused implementations exactly
against that historical case. Numerical solver/cache context is a possible cause;
the failed historical comparison is retained and is not marked passed. To isolate
the implementation change, pair each fused run with a fresh original-backend run
in the same process/read-only matrix-cache context for all eight fixed cases.
Keep the same 1e-12 command/state bound, save both traces before checking, and
record original-versus-historical differences separately. This paired regression
does not establish bitwise cross-process historical reproducibility.

After equivalence passes, repeat the same complete nine-check functional cohort
once in a new output directory, preserving the first measurements. Record the
new source/backend explicitly. This is a justified implementation correction,
not best-run/seed selection. Statistical promotion and its unmet 5% target are
unchanged. No formal runtime promotion or final Webots pass is inferred.

Outcome: the amended paired comparison also fails the unchanged 1e-12 command
bound, with a difference about 8.255e-11. The fused backend is REJECTED for
promotion under this exact-equivalence protocol. Do not run its planned timing
rerun, relax the bound, or reuse original timing measurements as fused results.
All initial tests, failed trajectories and diagnostic data are preserved.
