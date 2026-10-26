# Stability analysis and limits

For the explicitly assumed delay-free unsaturated nominal linear error system,
let A_c=A-BK be Hurwitz and P>0 satisfy A_c^T P+P A_c=-Q_c, Q_c>0.
For bounded additive residual/disturbance d(t), xdot=A_c x+B d, V=x^T P x gives:

Vdot <= -lambda_min(Q_c)||x||^2 + 2||PB||||x||||d||
     <= -(lambda_min(Q_c)/2)||x||^2
        + (2||PB||^2/lambda_min(Q_c))||d||^2.

This supplies a conditional input-to-state/ultimate-boundedness argument for
that nominal linear system. Bounded nonzero d does NOT establish x->0.
Zero-input asymptotic stability must not be substituted for residual-assisted
nonlinear convergence or safe operation.

The evaluated vehicle has Fiala tire nonlinearities, reference forcing, an
observer, actuator lag/rate limits, command saturation and packet timing.
The4-state feedback's stability alone does not prove the augmented closed loop.
An augmented unsaturated linearization can be numerically assessed, but is not a
proof for nonlinear saturation, switching or arbitrary time-varying delay.

LQR remains freshly computed while PPO service is delayed. Consequently rejection
of a1s-old PPO proposal is not tolerance of1s-delayed LQR sensor feedback. Any local
scheduler miss remains a timing failure even if the selected command equals LQR.

Nominal predictor improvement is not a barrier certificate, invariant set, robust
feasibility or guaranteed realized cost reduction. Experiment envelope/survival
checks are finite observations, not safety proofs. No global safety, guaranteed
100Hz/WCET, collision avoidance or real-vehicle readiness is claimed.
