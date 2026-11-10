# Source audit of the closest delay-aware mechanism

This is a technical comparison boundary, not a thesis draft or novelty proof.
Kalaria, Lin and Dolan's delay-aware robust vehicle controller is the closest
application mechanism among the primary sources already reviewed in
docs/research/primary-papers. The author repository
https://github.com/dvij542/Delay-aware-Robust-Tube-MPC was inspected read-only at
63cdd3c47fc280bd461697213476dabdd1b764a3. Its README explicitly associates both
the conference2109.07101 and extended2208.13856 works with the code. A source
manifest records the inspected file hashes. No author code is executed or copied
into this implementation; third-party assets and unlicensed files are not
redistributed in the evidence package.

The extended Plan B caller is
[blackbox_controller_refined.py](https://github.com/dvij542/Delay-aware-Robust-Tube-MPC/blob/63cdd3c47fc280bd461697213476dabdd1b764a3/Controller%20racing%20B/blackbox_controller_refined.py#L23).
It imports lqr_steering_adjust_frenet_frame, predicts through buffered controls
at lines260–277, shifts ego/obstacles by estimated delay plus a multiple of
dispersion at lines503–558, time-stamps a sequence at562 and updates the adaptive
delay estimator at573–575. The pre-compensator selects buffered commands using
simulator feedback time (lines95–136 and157–173). These predate LANS: neither
delay prediction, buffered control, CBF correction nor hybrid control alone is a
defensible novelty claim.

The inspected source differs materially from the published Appendix and from
our adaptation. The imported Frenet module is a seven-state steering-lag/pedal
nonlinear sequence program using IPOPT. Its obstacle expression at line113 is
`g[k] = viol_amt[k]`, with the barrier term commented out; the second derivative
condition at116 is also commented out. A separate lqr_steering_adjust_new module
has an active first derivative obstacle expression at106 and a commented second
derivative expression at110, but the inspected refined caller does not import
that module. We have not established which exact code revision/configuration
produced each published figure. Do not infer full-paper fidelity from a filename.

LANS's cbf_reference is therefore explicitly an independently implemented,
paper-mechanism adaptation: current FIFO prediction, six-state shared bicycle,
three model points, second derivative lane/circle inequalities and one scalar
steering QP around the strong R16 LQR. It omits the paper's steering lag, pedal
sequence, INFLUENCE delay estimator, tube/invariant terminal mechanism, racing
reference generator and original CARLA/Gazebo vehicle. It inherits no paper
theorem. The matched old-v8 and analytical/adaptive controllers remain additional
strong references; a win over CBF-LQR alone cannot establish state-of-the-art
superiority. The three CBF frequencies were selected only on192 training runs
before2309 confirmation outcomes, with all failed/reference outcomes retained.

The supported contribution boundary is an implemented combination of original-age
source checks, bounded asynchronous proposals with owner admission, model-aware
quality guards, and explicitly uncertified longitudinal emergency recourse,
with prospective matched evidence. Whether this combination is novel enough
for publication still requires a broader literature and supervisor review.
Tearle/Wabersich-style recursive guarantees require verified terminal backup,
invariant sets and model-error bounds that this controller does not establish.
Finite trajectory checks do not fill those assumptions. Full original-paper
reproduction and a universal novelty/safety claim remain outside these results.
