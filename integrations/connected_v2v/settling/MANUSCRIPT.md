---
title: 'LANS: V2V Following, Formation Recovery and Conditional Safety in Simulation'
subtitle: 'Research thesis draft with a longitudinal reference theorem and continuous 2-D trace certificates'
author: 'Rizwan Ali'
date: '4 November 2026'
lang: en-GB
documentclass: report
fontsize: 11pt
papersize: a4
---

# Abstract {-}

Connected following depends on both braking capability and the quality of the
information used to choose a predecessor. Communication loss must not be confused
with a vehicle leaving the lane, and collision avoidance alone does not imply
that a formation returns to its desired spacing. This thesis develops and audits
a hardware-free simulation study of those distinct properties in LANS.

The implementation combines original-time V2V messages, anonymous radar
observations, observation-driven target association, conservative braking and
positive-departure recovery. The final architecture adds route-normal steering,
measured recovery modes, bounded cooperative head pacing and priority relaying
within the original 150 m direct-link range. Performance is evaluated with
consecutive two-second sampled association and settling windows, meaningful progress,
final-window spacing and speed errors, and restoration of head cruise speed.

@ABSTRACT_RESULTS@

Two mathematical claims are kept separate. An earlier one-dimensional reference
supervisor preserves a stopping invariant prospectively under explicit sensing,
admission, braking, timing and non-reversal assumptions. The broader result
certifies completed two-dimensional trajectories continuously between logged
endpoints under declared body, pose, acceleration and yaw bounds. It includes
curves, lateral cut-in/out, non-connected actors and actual simulated Webots
motion, without assuming that commanded acceleration equals physical response.
It is an a posteriori finite-trace result, not prospective invariance of the
entire controller. No hardware or unconditional real-world safety claim is made.
Final comparative benchmarking remains on hold.

# Research problem and contribution

## Safety, information and useful recovery

A connected follower may receive delayed, lost, duplicated or replayed messages.
Radar can supply a fresh relative observation when radio is unavailable, but can
also miss a vehicle because of occlusion, bearing limits, noise or scan latency.
If both sources become unavailable, extrapolating an expired state indefinitely
can cause an unsafe decision. Conversely, always braking on uncertainty may
leave a stopped follower while the head travels outside every communication path.

An autonomous predecessor selector must distinguish a positively observed lane
departure from silence. It must also distinguish a plausible predicted intrusion
from evidence that an anonymous object is already a member of the lane. The
controller can brake for an uncertain approaching object before admitting that
object as the selected predecessor. This distinction matters because a false
admission followed by missing observations can leave a permanent ghost target.

The thesis therefore treats four properties separately: fresh admissible
information, physically collision-free motion, correct stable association and
formation convergence. A safe stop can satisfy the second property while failing
the fourth. An isolated correct association sample does not establish stability.
A small error after a long transient does not establish a small whole-run error.

## Questions answered by the study

1. Can observation-triggered recovery reduce excessive following gaps while
   retaining conservative approach braking and the original freshness rules?
2. Under the original 150 m communication range, can causal head pacing and
   bounded relaying retain useful recovery paths in the declared scenarios?
3. Does recovered association remain correct and fresh at every control tick, and does
   formation spacing settle while the head returns to its cruise speed?
4. What conditional mathematical statement can be made about the broader curved,
   lateral and native-simulator trajectories without physical hardware?
5. Can the reported outcomes be reconstructed from complete raw evidence,
   frozen execution source, independent scores and explicit failure history?

The contribution is the integrated implementation and its evidence boundary.
Stopping guards and safety filtering are established techniques; their use alone
is not a novelty claim. No reviewed controller has been reproduced as a matched
baseline in this work. The experiments do not establish superiority over other
methods or deployment readiness.

## Related work

@RELATED_WORK@

# Architecture and observation-driven recovery

## Communication and sensing

Each connected vehicle publishes its own observed state with an original
timestamp and monotonic sequence number. Receivers enforce admissible age,
identity and replay conditions. A relay forwards original bytes rather than
replacing observation time with its own receipt time. This prevents an old
measurement from becoming apparently fresh as it traverses the formation.
Claimed radio identities are not cryptographic authentication.

Radar produces fallible anonymous range, bearing and range-rate detections.
Association uses geometry and motion consistency rather than fixture actor labels.
The ego controller receives local measurements and actually delivered messages;
simulator truth is reserved for post-control scoring and trajectory verification.
In native Webots, each controller reads its own GPS, IMU, Gyro, Radar, Emitter and
Receiver. NPC maneuver paths are fixtures; ego target changes are not scripted.

Nominal radar freshness remains 0.2 s and nominal V2V freshness 0.4 s. Loss of a
selected target does not supply positive departure evidence. If selected knowledge
is unavailable, the ego preserves that uncertainty and requests conservative
braking. The old observation timestamp is retained in all recovery modes.

## Formation recovery policy

Normal approach keeps conservative guarding of adjacent traffic. Only positive
observed departure enables lane-aware catch-up. The recovery guard examines a
0.6 s lateral preview with a declared 3 m/s² lateral uncertainty allowance and
an extra margin. A newly measured cut-in restores the conservative mode. Two
seconds of measured spacing and relative-speed settling end catch-up.

Initial approach remains conservative. After an observed cut-in, three distinct
fresh, unblocked selected-source observations establish following before the
lane-aware guard can be used in ordinary following. Repeated control ticks on one
stamp do not count, and a new selected target resets confirmation. This prevents
unnecessary prolonged adjacent-traffic stops once a predecessor has been admitted.
Missing selected knowledge still requires braking in either guard mode.

Prediction can immediately trigger braking but does not establish lane membership.
Near-boundary anonymous membership requires two distinct measurement frames,
unless the return is strongly inside the lane. Reusing one scan on multiple
control ticks cannot manufacture confirmation. This change addresses a preserved
development failure in which a noisy adjacent return became a missing predecessor.

A uniquely matched fresh cooperative scan can anchor the next peer association
after an old local track expires. The association-chain gap is limited to 0.5 s,
and every contributing observation must retain original age at most 0.2 s. This
anchor contributes identity/exit evidence only. It does not become fresh local
radar or a nominal-following packet. Silence still supplies no departure evidence.

Steering uses Frenet route-normal errors on known straight or circular routes.
This avoids the old short Cartesian road-graph restriction when a vehicle reaches
a large circular arc. Tested stations stay on one atan2 branch below a half-turn;
full laps need station unwrapping. Known-route steering does not solve arbitrary
route planning.

## Connectivity support and its limit

@PACING_DESCRIPTION@

Relays prioritize configured head/member roles in a 2:1 schedule under the same
maximum one forwarded packet per 100 ms and 0.25 s original-age allowance. Group
membership configures routing; it does not provide the ego's selected target.
The controller must still choose a predecessor from actual observations.

The necessary recovery condition is the return of an actual fresh local sensing
or original-age radio path. Pacing and routing improve retention but cannot
manufacture information when every path is absent. A direct 150 m range in the
simulation is a link-model setting, not a radio-frequency guarantee. Multi-hop
reach requires every actual hop and the original-age budget to remain valid.

# Conditional longitudinal reference safety

This chapter describes the earlier, separately implemented one-dimensional
reference supervisor. Its prospective invariant is not silently applied to the
broader recovery controller or Webots speed servo. The original source, reference
runs, theorem and evidence remain separately versioned.

@LONGITUDINAL_MODEL@

# Continuous two-dimensional trajectory certification

## Why a separate claim is needed

Curved-road motion, lateral intrusion and native vehicle response invalidate a
direct transfer of a one-dimensional command-envelope theorem. The broader
system also contains uncertain association decisions, fallible scans and actual
simulator actuation. A global future-safety proof would require prospective
perception, admission, dynamics and feasibility refinements for all these parts.
That claim is not established by the present finite campaigns.

The new theorem instead verifies every actual actor pair throughout each completed
interval. Its collision conclusion does not depend on which target the controller
selected. Association is checked as a separate observation and identity property.
Future endpoint poses are used only after execution and never enter control.

## Body, pose and dynamics contract

Let $c(t)=(x(t),y(t))$ and $\theta(t)$ be an actor reference position and yaw.
Assume that its planar body lies in a rectangle with half-length $\ell=2.6$ m and
half-width $w=1.1$ m about that reference. Endpoint coordinate and body-projection
reconstruction error together must fit $\epsilon=0.02$ m per coordinate.
For interval length $h$, assume $|x''|,|y''|\le A=20$ m/s² and
$|\theta'|\le\Omega=2$ rad/s. Every collision-relevant actor must be included.

These are mathematical premises. Native GPS is mounted 1.4 m forward of the
vehicle origin; the fixture chassis collision box is 3.8 by 1.5 m, centred 1.3 m
forward, with wheel and pose allowances included in the declared envelope.
The envelope is specific to the fixtures and does not certify an arbitrary
production vehicle. Native roll/pitch and recorded motion are separately checked.
Continuous body containment remains a premise; the sampled pose gate alone does
not prove containment for every possible wheel/suspension configuration.

## Center and rotating-support bounds

For twice-differentiable scalar $f$, write the endpoint chord as
$q(t)=(1-t/h)f(0)+(t/h)f(h)$. The interpolation remainder gives

$$|f(t)-q(t)|\le A t(h-t)/2\le Ah^2/8.$$

For rational nonzero direction $n=(n_x,n_y)$, let $N=|n_x|+|n_y|$.
A pair's center-projection uncertainty is at most $NAh^2/4+2N\epsilon$.
The rectangle support is

$$r(\theta,n)=\ell|n_x\cos\theta+n_y\sin\theta|
 +w|-n_x\sin\theta+n_y\cos\theta|.$$

Every interior time lies within $h/2$ of one endpoint. Rotating a body point
changes its projection by at most $(\ell+w)N$ times the yaw change. Thus each
body's support is bounded by its maximum endpoint support plus
$(\ell+w)N\Omega h/2$. This permits different headings and lateral motion.

## Separating certificate and theorem

Orient $n$ so the endpoint relative-center projections $d_0,d_1$ are positive.
Let $r_a,r_b$ be the maximum endpoint support of each body. If

$$\min(d_0,d_1)>r_a+r_b+(\ell+w)N\Omega h+NAh^2/4+2N\epsilon, \tag{2}$$

the relative-center chord exceeds both body supports and every permitted
intersample deviation. Their projected occupancies are strictly disjoint at
every interior instant. Separation on one axis excludes a physical intersection.
Applying (2) to every actor pair and consecutive interval proves disjoint bodies
throughout that completed horizon, conditional on the contract.

Endpoint-only checking is insufficient. For example, the scalar separation
$1-8t(1-t)$ is positive at both ends of $[0,1]$ but negative at its midpoint.
The acceleration bridge prevents that trajectory from being certified merely
because its endpoints are separated.

## Exact arithmetic and mechanical scope

Candidate axes have integer components divided by $10^6$. Floating trigonometry
only chooses an axis; any nonzero rational axis is admissible. Safety support
calculations use fixed-point interval arithmetic at scale $10^{18}$. Sine through
degree 25 and cosine through degree 24 use outward rounding and Lagrange remainder
bounds on headings in $[-4,4]$. Endpoint separation rounds down to micrometres;
occupancy rounds up. Acceptance requires a strictly positive integer difference.
The verifier keeps the first valid axis. Dividing its margin by the axis
L1 norm gives a conservative Euclidean clearance lower bound; it is neither an
actual nearest-body distance estimate nor the best bound available over all axes.

Six exported real-arithmetic implications must be UNSAT when negated. They check
the chord, bridge subtraction, axis exclusion, outward rounding, nearer-endpoint
time and set-coverage algebra. An omitted-bridge control is SAT. The continuous
interpolation, support and Taylor-remainder lemmas remain analytical arguments.
This is neither a proof-assistant-kernel nor full source-code correctness proof.

A projection margin is not automatically a Euclidean clearance. Dividing it by
$N$ gives a conservative Euclidean lower bound because $\|n\|_2\le N$.
The evidence retains the actual rational axis and integer lower/upper witness for
each pair and interval so the strict comparisons can be reconstructed.

## Native refinement evidence

Control runs at 50 ms; native motion files record each vehicle's own GPS/IMU/Gyro
every 10 ms. Qualification checks sample count, finite data, velocity/yaw
increments, exact agreement with control-time poses, every recorded intermediate
point against the bridge, initial world-placement consistency and planar pose.
Requested-versus-measured acceleration differences are retained explicitly.
The native guard plans braking with 2.5 m/s² and a 0.8 s reserve instead of assuming
that the -6 request is realized by the factory SPEED-mode motor ramp. It uses only
the common controller's fresh observed guard objects. Raw nominal commands, the
native override and actual API readback are stored separately. A 0.3 s release
hold bridges intermittent detections. This is a native planning refinement, not
a guaranteed physical braking bound or a transfer of the 1-D invariant theorem.

These measurements support finite consistency with the declared contract. They
do not formally verify Webots' integrator or establish every unmeasured derivative
at every real instant. The continuous conclusion remains conditional on those
between-sample bounds and body/pose containment. The prospective theorem from the
previous chapter is not asserted for the actual native speed servo.

# Experimental method and research integrity

## Scenarios and data separation

Every final ordinary episode lasts 70 simulated seconds at 20 Hz control.
The eight profiles cover curved roads, dense curved traffic, noisy non-connected
traffic, burst misses, occlusion with braking, dual blackout, V2V blackout and a
combined case. There are three or eight actors. Native curves have radius 600 m;
Python curves 800 m. The two-lane physical road extends to station 1500 m.
Native cruise speeds are 8 and 12 m/s; Python also tests 16 m/s.
Native recovery setpoints are capped at 16 m/s and actual planar speed is qualified
at most 16.5 m/s from the 10 ms motion records. A higher-speed native steering
failure is preserved; this limit is an operating envelope, not a general stability
proof. The original heading and lane gates remain unchanged.

Traffic maneuver and noise definitions are retained, while the head now follows
causal pacing dynamics. This is an architectural change. A different leader plant,
longer horizon or new final-window metric cannot justify an isolated causal
percentage improvement over the old 32/35-second fixtures.

@COHORT_DESCRIPTION@

Execution source is frozen before campaigns. Validation requires matching source
hashes and passing development gates. Native validation additionally waits for
Python validation. If a runtime change follows a fresh failure, a new development
root and genuinely new validation seeds are required; failed campaigns remain
visible. Published seeds are reproduction inputs after the fact, not permission
to tune and relabel the same validation cohort.

## Acceptance definitions

All original collision, requested-actuator, freshness, blind-braking and lane
gates remain. Progress must exceed 60% of cruise distance. Each episode must
observe the intruder correctly and demonstrate a two-second consecutive correct
fresh association with the returned head after cut-out.

The two-second windows mean 40 consecutive 20 Hz control ticks with no failed
sample. Association and freshness are sampled properties. The separate physical
certificate covers intersample time under its contract; a continuous-time
perception-correctness theorem is not inferred from the sampled association gate.

Settling requires two-second consecutive sampled headway error at most 2 m and relative
speed error at most 0.5 m/s. Its onset must be by elapsed time 60 s. The reported
settling delay is the start of that confirmed window after cut-out, not its end.
Final-five-second gates require spacing RMS at most 2 m, maximum absolute error
at most 5 m, relative-speed RMS at most 0.5 m/s, correct fresh head fraction at
least 95%, and head cruise-speed RMS error at most 0.5 m/s. The last condition
prevents success by permanently slowing the entire formation.

The desired bumper gap is $6+1.2v$ metres. Correctness combines source identity
where available with independent geometry. An anonymous fresh observation may
be geometrically correct; an inconsistent original radio identity cannot pass
as the head. Whole-window correct-target RMS and stopped time remain separately
reported because final-window accuracy does not describe transient performance.

## Independent audit, replay and negative evidence

The independent standard-library scorer imports neither controller nor plant.
It checks complete grids, raw hashes, original source states, acceptance/replay
outcomes, relay bytes/budgets, causal head pacing, requested bounds, geometry and
the stronger performance gates. Python sensor/network input regeneration checks
local scans, cooperative scans and complete 150 m deliveries from audited states.
It shares the declared sensor/network model and is not independent physics.

Each execution also replays the actual controller against stored inputs; Python
replays the shared bicycle step, while native replay does not pretend to rerun
Webots physics. Five semantic corruptions must be rejected after their file
hashes are updated: an aggregate, an original source wire state, a native
control-time motion sample, an intersample motion sample at 1.01 s and a bypassed
native stop API readback.
The latter must fail the bridge consistency check even though recorded control
poses are unchanged. Rehashing alone must not make incorrect evidence acceptable.

Deliberately unreachable 150 m experiments are separate diagnostics. Their ordinary
recovery classification remains false. They test expected braking and absence of
invented fresh targets; a safe stop outside the connectivity envelope is not added
to the ordinary recovery pass denominator.

# Audited results

@RESULTS@

@RESULTS_TABLE@

![Python combined profile, fixed first validation seed at maximum tested speed. The complete transient and final-window inset are both shown.](figures/python-formation-trace.png){width=95%}

![Native Webots combined profile, fixed first validation seed at maximum tested speed. Pacing goal, measured speeds and observed association are retained.](figures/webots-formation-trace.png){width=95%}

![Per-profile final-five-second spacing RMS medians and full observed ranges. Simulator cohorts differ and are not a matched method comparison.](figures/tail-spacing-coverage.png){width=95%}

## Preserved failures and engineering interpretation

@FAILURE_HISTORY@

The final-window result describes eventual convergence in this operating
configuration. Initial gaps, conservative braking and loss episodes can produce
large transient error and stopped intervals. None is removed from the raw record.
All-actor certificates and ordinary recovery gates are separate evidence; good
tail spacing alone cannot establish collision freedom or correct association.

# Discussion, limitations and thesis status

## What hardware-free work establishes

Simulation permits repeatable message faults, sensor faults, association failures
and native vehicle dynamics without physical vehicles. Combined with explicit
mathematical contracts it supports a defensible simulation thesis and conditional
safety claims. Hardware is not logically necessary to prove a mathematical
reference theorem or a conditional finite-trajectory separation statement.

Hardware would be required to validate physical sensor bounds, actuator/braking
guarantees, real radio propagation, synchronization and deployment deadlines.
Neither the 150 m field nor zero collisions in finite trials establishes those
facts. No public-road or production-vehicle safety certification follows here.

## Remaining boundaries of the completed research scope

Recovery requires actual returning information and an admissible physical
situation. Arbitrary hidden close intrusions, initially unavoidable collisions,
adversarial identities and arbitrary reverse motion are outside the present
guarantee. Known straight/circular two-lane fixtures do not cover every route,
junction, vehicle class, weather or traffic density. The native Radar adapter excludes the ambiguous outer 0.33–0.35 rad fringe:
pinned R2025a source confirms that partially visible bodies can have their center
azimuth clipped there. Raw returns are preserved and rejected returns mean unknown,
not clear road. The usable central aperture matches the Python model.
Gaussian sensor errors are unbounded in theory; finite draws do not prove deterministic perception bounds.

The two-dimensional result certifies these completed traces under premises;
it does not prove recursive feasibility or invariance for every future action
of the full target selector. A prospective broader proof would need additional
perception/admission, lateral reachable-set, native-plant and timing refinements.
That is a distinct research claim, rather than a wording change to this result.

Zero failures in a finite seeded cohort are not a population failure-rate bound.
Profiles, speeds, simulator families and correlated vehicles are not interchangeable
independent physical trials. No comfort, string-stability or communication-security
property is established. The work retains source and evidence so these questions
can be studied without rewriting the present conclusion.

## Review status

The requested simulation fixes, stronger finite validation, broader conditional
trace proof and reproducible evidence form the completed technical scope of this
draft. Official institutional front matter, degree declarations and formatting
are not invented. The document is ready for technical/supervisor review, not
asserted institutionally submission-ready. Final comparative benchmarking remains
on hold under the user's instruction.

# Reproducibility appendix

@REPRODUCIBILITY@

# References {-}

@REFERENCES@
