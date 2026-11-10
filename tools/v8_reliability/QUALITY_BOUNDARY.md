# Tracking and body-heading metrics under the common bicycle model

This technical note explains a metric trade-off; every declared gate is retained.
The scored heading error is body yaw minus road-tangent yaw. In a dynamic
bicycle, a nonzero sideslip can be required for steady curved-path tracking.
Zero lateral path error and zero body-heading error are not generally the same
equilibrium objective.

The existing ScheduledLQR uses the steady lateral-velocity expression

    vy = (lr*v - m*lf*v^3 / ((lf+lr)*Cr)) * curvature

and target body-heading error -vy/v. With the fixed LANS parameters
m=1650kg, lf=1.2m, lr=1.4m, Cr=80000*stiffness N/rad, the coefficient of
curvature in that heading target at16m/s is approximately1.037m at nominal
stiffness and1.646m at0.8stiffness. Adaptive tracking can therefore reduce lateral
error while increasing the scored body-heading error. This observation does not
establish an unavoidable lower bound on full-episode RMS or excuse a failed gate.

V8's mixed-objective ranking and per-model two-second quality guards are local
prediction checks. Tightening their factors does not prove dominance of actual
closed-loop heading/rate RMS over an independently evolving LQR trajectory.
The calibration-selected guard showed a modest improvement on its training
fixtures; prospective results determine whether that generalizes. The unchanged
5%/1%, heading/rate, confidence and every-case progress gates remain primary.
PPO gain optimization and any new learned policies belong to the separate agent.
