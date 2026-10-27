## Exact aligned method and objectives

The architecture remains LQR plus a bounded PPO residual. The vehicle feedback
and local LQR are independent of learned-worker completion by design; timely
execution still requires measurement. This is not full-command PPO/LQR switching.

For a valid held packet, the causal residual filter is

$$
f_t=f_{t-1}+\left(1-e^{-T/0.3}\right)
\left[\operatorname{clip}(\Delta\delta_t,-0.08,0.08)-f_{t-1}\right],
\qquad T=0.01\;\mathrm{s}.
$$

The candidate authority uses the retained age-gain and a ramp:

$$
\bar w_t=\min\!\left\{0.25e^{-0.8\max(0,1000a_t-5)},\;w_{t-1}+0.05\right\},
\qquad a_t=t-t_{\mathrm{observation}}.
$$

Packet eligibility requires finite data, non-regressing sequence, nonnegative
age below50ms, lateral estimated error within1.5m and heading error within0.25rad.
An invalid/stale packet immediately clears filter, authority and recovery count.
A performance rejection retains the valid causal filter history while returning
authority to zero. Three consecutive good control ticks are required for
admission; they are not necessarily three distinct worker responses.

The nominal linear-bicycle/actuator predictor has100 steps of10ms each, observable
curvature previews at0/10/20m,0.05s actuator lag and0.35rad/s actuator-rate limit.
It compares LQR continuation with a repeated-current-residual/filter trajectory.
It admits the candidate only when

$$
J_0-J_1\geq\max(10^{-7},0.001J_0).
$$

Each predictive stage uses lateral error, heading error, actual predicted
actuator rate and steering effort with weights1,0.2,0.2,0.005 and normalizers
0.5m,0.1rad,0.35rad/s,0.5rad. The assumed continued healthy service is only a
performance-prediction assumption; no future completion forecast enters the
policy, and the predictor is not a robust safety certificate.

The applied steering command is

$$
\delta_{\mathrm{cmd},t}
=\operatorname{clip}\!\left(\delta_{\mathrm{LQR},t}+w_t f_t,-0.5,0.5\right).
$$

Training uses the actual executed transition reward

$$
r_t=-\left(\frac{e_{y,t}}{0.5}\right)^2
-0.2\left(\frac{e_{\varphi,t}}{0.1}\right)^2
-0.2\left(\frac{\dot\delta_{a,t}}{0.35}\right)^2
-0.005\left(\frac{\delta_{\mathrm{cmd},t}}{0.5}\right)^2
-10\,\mathbf{1}_{\mathrm{failure}}.
$$

This removes the old raw command-jump penalty in this newly frozen variant.
There is no reward penalty for exogenous worker latency. The learner can change
driving actions, not the injected computation/service delay. Training reward is
not itself a guarantee that the separate development criteria will pass.

The five categorical residuals are−0.08,−0.04,0,+0.04,+0.08rad. The actor has two
64-unit tanh layers, frozen original TRAIN normalization and three independent
PPO seeds, each with exactly100,000 additional transitions. Original supervised
pretraining is extra and disclosed. Endpoints, not best intermediate scores, are
evaluated. Complete optimizer/rollout settings are in the frozen protocol.

The20-channel policy interface includes estimated lateral/heading errors,
estimated lateral-error derivative, yaw rate, measured speed, actuator angle,
curvature previews, held-packet history and prior command/authority. The five
previously removed future/oracle channels remain zero. Causality does not prove
full observability: the internal residual-filter state is not a separate policy
feature, so a fully Markov policy-state claim is not made.

All methods share sensing, actuator and supervisor settings in the matched
comparison. A promising PPO endpoint must improve lateral RMSE by at least1%
over LQR, same-supervisor student and both fixed corrections, preserve survival,
improve over the student for every seed, limit nominal degradation to2%, and
keep heading/actuator-rate RMS within5% of LQR. All conditions are required.

Original10ms deadlines remain unchanged. Offline tracking, asynchronous software
execution and physical sensing-to-actuation latency are separate measurements.
No hard-real-time, global convergence or real-vehicle safety theorem follows
from clipping the residual or observing simulation survival.
