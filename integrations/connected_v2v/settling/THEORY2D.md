# Conditional continuous 2-D safety of completed trajectories

This extends the earlier [one-dimensional reference proof](../conditional_safety/THEOREM.md)
with **a posteriori finite-trace certification** on curved/multi-lane Python and
native Webots trajectories. It is not a prospective proof that this entire
controller always remains feasible or avoids every possible future intrusion.
Future endpoint poses are never supplied to the controller.

## Contract

For each actor, let c(t)=(x(t),y(t)) be a planar reference point and θ(t) its yaw.
The projected physical body is contained in a rectangle of half-length ℓ=2.6 m
and half-width w=1.1 m about that point. This is a declared conservative envelope
for the fixtures, not a claim about an arbitrary production vehicle. Native GPS
is mounted1.4 m forward; the envelope includes that reference-point offset.
The fixture chassis collision box is3.8×1.5 m, with wheel/pose allowances retained.

At the recorded endpoints, the combined coordinate/pose reconstruction error is
at most ε=0.02 m per coordinate. The budget must cover translation and the endpoint
body projection effect of heading/representation errors together. During an
interval of length h, assume |x''|,|y''|≤A=20 m/s² and |θ'|≤Ω=2 rad/s, and that
the body envelope remains valid. All relevant actors must be included. These are
the mathematical premises; no real hardware bounds are inferred from simulation.

Python uses declared model poses; native endpoints come from actual simulated
GPS/IMU records. Native10 ms motion records supply finite consistency checks on
velocity increments, yaw increments, pose synchronization and the control-interval
bridge. They are not a formal verification of Webots' integrator or proof of an
unmeasured derivative bound at every real instant.

Body containment is also an explicit continuous premise. The sampled planar-pose
qualification alone is not a derivation of containment for every possible wheel
steering/suspension configuration. A universal mechanical refinement would need
that additional argument; the present theorem states the enclosing-body contract.

## Lemma 1: continuous center bridge

For a scalar twice-differentiable f with |f''|≤A on[0,h], let
q(t)=(1−t/h)f(0)+(t/h)f(h). The interpolation remainder/Green-function bound gives

    |f(t)−q(t)| ≤ A t(h−t)/2 ≤ A h²/8.

For a rational separating direction n=(nx,ny), define N=|nx|+|ny|. Projection
error is at most NAh²/8 for each center, and NAh²/4 for a pair. Including endpoint
pose reconstruction adds2Nε. The bound applies in world Cartesian coordinates;
it does not assume a straight road or a particular target identity.

## Lemma 2: rotating body support

The rectangle support in direction n at yaw θ is

    r(θ,n)=ℓ|nx cosθ+ny sinθ|+w|−nx sinθ+ny cosθ|.

A body point has distance at most ℓ+w from the reference point. Hence changing yaw
by Δθ changes projected support by at most(ℓ+w)N|Δθ|. Every interior time is within
h/2 of one endpoint. Thus

    r(θ(t),n) ≤ max(r(θ(0),n),r(θ(h),n)) +(ℓ+w)NΩh/2.

For two equal enclosing rectangles, the combined rotation allowance is
(ℓ+w)NΩh. Different headings and lateral cut-in/out motion are allowed; the rate
bound and body/pose contract must hold. No constant-heading vehicle assumption is
used inside the interval.

## Separating certificate and theorem

For actors a,b, orient a nonzero rational n so that their endpoint relative-center
projections d0,d1 are positive. Define ra,rb as each body's maximum endpoint support.
If

    min(d0,d1) > ra+rb +(ℓ+w)NΩh +NAh²/4 +2Nε,       (C)

then their projected occupancies are disjoint at every time in that interval.
Proof: the relative-center chord is at least min(d0,d1); subtract the center/pose
bridge allowances and compare to the two body supports from Lemma2. Strict
separation on one fixed axis excludes a physical intersection.

If(C) is certified for every actor pair and every consecutive interval, the bodies
are disjoint throughout that completed finite trace, under the contract. Applying
the argument interval by interval covers curves, full circular arcs, lane changes,
non-connected actors and the native trajectories without assuming that requested
acceleration equals actual acceleration. The theorem does not promise that a
certificate exists for every future controller action.

## Exact implementation and checked algebra

`trace_certificate.py` uses rational directions with integer components divided
by10^6. Floating trigonometry merely chooses candidate directions: *any* nonzero
rational direction is legal. All safety support calculations use fixed-point
interval arithmetic at10^18 scale. Sin is expanded through degree25 and cos through
degree24; for endpoint headings in[−4,4], Lagrange remainders are bounded by
4^27/27! and4^26/26!. Every integer multiplication/division rounds outward.

Endpoint separation is rounded DOWN to micrometers; total occupancy allowance is
rounded UP. The verifier accepts only a strictly positive integer difference.
There is no negative-gap tolerance. A reported projection margin is not itself a
normalized Euclidean clearance; dividing by N gives a conservative clearance lower
bound, because ||n||₂≤N.
The verifier keeps the first strictly valid axis, rather than optimizing clearance.
Its smallest reported lower bound need not approximate the actual nearest-body
distance or the strongest available certificate on another axis.

`prove2d.py` exports six negated real-arithmetic implications and requires Z3 to
return UNSAT. These cover chord/order separation, bridge subtraction, axis
exclusion, outward rounding, nearer-endpoint time and set coverage independent of
labels. An omitted-bridge negative control is SAT. The continuous interpolation,
rotation and Taylor remainder lemmas are analytical, not ODE theorems generated by
Z3. This is not a proof-assistant-kernel or full source-code correctness certificate.

For example, point separation1−8t(1−t) is1 at both endpoints of[0,1] and−1 at the
midpoint. Merely testing endpoints would miss the overlap; the acceleration bridge
allowance prevents certification of that example.

## Association and actual native refinement

Collision certification uses all actors from the generated world/log registry,
not whichever target ego happened to select. Association is checked separately:
original radio identity, source timestamps, raw wire provenance, geometric target
agreement, continuous fresh return and final formation metrics. No identity or
world-truth label enters ego's target choice. Claimed IDs are not cryptographic
authentication, and correctness on these traces is not a universal perception proof.

The2 s association/settling windows mean40 consecutive20 Hz control ticks without
a failed sample. Freshness/identity is checked at each tick. The continuous-time
theorem concerns physical footprint separation under its contract, not perception
correctness at every unmeasured instant.

Native motion files are generated by10 ms reads of each vehicle's OWN GPS/IMU/Gyro.
Control still runs every50 ms. The qualifier checks measured coordinate acceleration,
yaw, agreement with control-time poses, and every logged intermediate point against
the bridge allowance. Requested-vs-measured acceleration differences are retained;
the original1-D model's commanded braking assumption is not silently applied to the
native speed servo. World/controller/source hashes and the full raw logs are retained.

The known initial native endpoint is derived from generated world placement and
the GPS mounting transform, and checked against the first native record. The
certificate covers the declared0–70 s horizon. All these finite checks support the
contract; physical bounds, arbitrary unobservable traffic, deployment timing and
future recursive safety remain outside this hardware-free claim.

## Native planning/input refinement used in the final campaign

The common Python controller remains frozen. The native wrapper records its raw
nominal command separately, then may request an earlier stop from fresh guard
objects using2.5m/s² planning braking and0.8s reserve. Factory SPEED-mode motor
stopping realizes about2.78m/s² in the inspected surrogate, not the requested-6.
A0.3s release hold bridges intermittent returns. Friction intensity stays zero;
the source-confirmed motor ramp, mass and world friction are unchanged. Planning
allowances are not asserted hardware bounds or a transfer of the1-D invariant.

Pinned R2025a WbRadar.cpp lines500–508 clamp center azimuth to the physical edge
when only part of a body is visible. The native adapter excludes the ambiguous
0.33–0.35rad fringe, matching Python's central aperture. Rejected returns remain
unavailable and scans incomplete; absence never declares a clear lane. All raw
returns and inspected official-source hashes are preserved. Continuous footprint
certificates still use actual poses of every actor, independent of these labels.

The final native recovery setpoint cap is16m/s, with sampled planar speed
qualified at most16.5m/s from10ms records. This declares an empirical steering
envelope after the retained native-v3 lane failure; it is not a stability theorem
for arbitrary speed. All heading/lane gates and the continuous body contract stay
unchanged. See [NATIVE_PROTOCOL_V4.md](NATIVE_PROTOCOL_V4.md).
