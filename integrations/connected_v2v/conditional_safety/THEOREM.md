# Conditional longitudinal safety theorem (v1)

This theorem concerns the NEW exact-rational reference shield in `shield.py`.
It does not retroactively certify `RobustFollower`, the bicycle plant, Webots,
Gaussian perception, autonomous lateral association or a physical vehicle.

## Contract and units

All positions are metres on one fixed, straight, shared longitudinal corridor.
`x` is the follower's FRONT bumper; `p_i` is obstacle i's REAR bumper. Speeds
are m/s and accelerations m/s². Vehicle length must be accounted for by the adapter.
Let m>0 be the required bumper gap, b>0 guaranteed emergency deceleration,
h>0 maximum time until the next successful control update, and δ≥0 an acceleration
tracking upper-error bound. A command u provides the upper acceleration a=u+δ.
The reference command range includes u_E=−b−δ. Example values (model choices,
not hardware measurements) are m=2, b=5.5, δ=0.25 and h=0.05.

The following are ASSUMPTIONS, not conclusions of the SMT checks:

**A1 — Corridor/coverage.** Every collision-relevant object ahead is protected.
There are no unobserved intrusions, reverse oncoming traffic, lateral collisions,
rear impacts, changing vehicle dimensions or route/topology changes. A new cut-in
is allowed only when detected/admitted BEFORE collision relevance and the invariant
below holds for its lower bound. There is no guarantee for an unavoidable cut-in.
Objects/bounds are never released on disappearance; no lateral departure theorem
is supplied. Arbitrary curved-road bumper geometry is outside this v1 theorem.

**A2 — Bounded sensing/identity.** Current ego bounds X≥x and V≥v≥0 are valid.
Each admitted obstacle observation supplies a correctly associated rear-position
lower bound L_i≤p_i(t_obs). A measured position z with a VALID error bound e supplies
L_i=z−e. Clock/coordinate conversions, identity and integrity are trusted. Gaussian
noise has unbounded support and does not satisfy this deterministic assumption
merely because a finite simulation happened to stay within a bound.

**A3 — Non-reversal.** Each protected p_i(t) is nondecreasing while retained.
It may brake immediately, arbitrarily strongly, or stop; it never moves backwards.
No positive lower bound on leader displacement is used. Thus an old L_i remains
a spatial lower bound. Its old timestamp does NOT become a fresh velocity/state.

**A4 — Ego flow/refinement.** For a held u, actual nonnegative speed and displacement
are bounded by the non-reversing constant-upper-acceleration flow from (X,V), with
a=u+δ. The update/actuation must meet the h deadline. Extra unmodeled actuation delay,
weaker brakes, numerical/coordinate error, invalid localization or missed deadlines
can falsify this contract. A current measurement may only intersect (reduce) valid
upper bounds; it may not inflate them beyond the previously certified envelope.

**A5 — Initialization and admissions.** For every protected bound, at initialization
and when adding an object, V²≤2b(L_i−X−m). Safety cannot be manufactured from an
initial collision/unrecoverable state. Unknown initial space is not clear-road proof.

**A6 — Faithful execution.** The emitted guard is obeyed and retained memory is not
silently discarded. The theorem is over exact real arithmetic; the reference uses
exact `Fraction` arithmetic. Porting to floating point, fixed point, native vehicle
control, a different plant or concurrency requires a separate refinement argument.

## Flow envelope

Define, for t≥0, W(V,a,t)=max(0,V+at). When a<0 and t>V/(−a), define
S(V,a,t)=V²/(−2a); otherwise S(V,a,t)=Vt+at²/2. Set W=0 after stopping.
For non-reversing dynamics with actual acceleration bounded above by a whenever
moving, the elementary differential comparison lemma gives v(t)≤W and
x(t)≤X+S: integrate v_dot≤a until the upper trajectory stops, then use saturation
at zero and the non-reversing condition. S is nondecreasing in t and W≥0. This
continuous comparison is an analytical lemma, not an ODE proof exported by Z3.

## Guard and invariant

Let B=min_i L_i, Q=2b(B−X−m)−V². Require Q≥0.
For a candidate u, compute s=S(V,u+δ,h) and w=W(V,u+δ,h), and accept only if

    2b s + w² ≤ 2b(B−X−m).                         (G)

The reference enumerates a finite acceleration grid no greater than the clipped
nominal request and always including u_E. The safety result is independent of how
the nominal request is obtained: LANS following gains, a learned proposal, cruise,
or a deliberately adversarial proposal. It proves no performance of that proposal.

## Lemma 1 — Emergency feasibility

For u_E the upper acceleration is −b. If V≥bh, s=Vh−bh²/2 and w=V−bh;
therefore 2bs+w²=V². If V<bh, s=V²/(2b) and w=0, giving the same identity.
Since Q≥0, the emergency candidate satisfies (G). Thus the finite enumeration
cannot be empty in an admissible state. The stopped branch prevents a fictitious
negative speed/negative travel distance from being used as a safety argument.

## Lemma 2 — Invariant preservation

During the next interval, A3 gives p_i(t)≥L_i. A4 gives x(h)≤X+s and v(h)≤w.
Use X_next=X+s, V_next=w and B_next≥B (valid newer bounds can only raise B).
Then (G) implies

    V_next² ≤ 2b(B_next−X_next−m).

Intersecting X_next,V_next with additional VALID current ego upper bounds only
reduces stopping demand. Taking the maximum of valid lower bounds for the SAME
non-reversing object preserves containment. Adding a new object requires A5 again;
it cannot be justified by the previous objects' invariant.

## Lemma 3 — Continuous intersample separation

For every 0≤t≤h, S(V,a,t)≤s and p_i(t)≥B. Because w²≥0, (G) implies
B−X−s≥m. Therefore p_i(t)−x(t)≥B−X−S(V,a,t)≥m throughout the interval,
not only at logged endpoints. This is longitudinal bumper separation, not a
two-dimensional box-overlap or arbitrary-lane theorem.

## Theorem — Conditional safety, including indefinite communication loss

Under A1–A6, if Q≥0 initially and at every admission, and every applied command
satisfies (G), then p_i(t)−x(t)≥m for all protected obstacles and all t≥0 while the
contract remains valid. Proof: emergency feasibility supplies a command; Lemma 2
preserves Q at each update; Lemma 3 covers every intersample interval. Induct over
updates. Valid old spatial bounds remain true under A3, so message loss of arbitrary
duration does not invalidate this safety argument. The follower may stop indefinitely.
No progress, target reacquisition, desired-headway convergence or string stability
follows from this theorem.

## What is mechanically checked

`prove.py` exports 12 negated real-arithmetic obligations in SMT-LIB, requires Z3
4.13.3's QF_NRA solver to return UNSAT, and requires five deliberately invalid
variants to return SAT with witnesses. Unknown/timeouts fail the command. These
are solver-checked algebraic obligations plus the analytical flow/induction argument.
They are not a proof-assistant-kernel theorem, source-code correctness proof, ODE
reachability certificate for the existing 2-D plant, or physical-world validation.

`audit.py` independently reconstructs reference simulation motion and guard
inequalities with stdlib rational arithmetic, checks sensor containment against
fixture truth and minimizes each piecewise-quadratic intersample gap. It imports
neither the shield nor the simulation plant. Runtime certificates and simulations
test correspondence to the equations; they do not eliminate the trusted-computing
base (Python, Fraction, Z3, OS, experiment generator and the written argument).
