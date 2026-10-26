# Original manuscript claim and reference audit

These are corrections to the original submitted text, not confirmation of its
historical measurements. New campaign results must never be inserted as if they
were the original MacBook measurements.

| Original claim | Correction |
|---|---|
|49x faster than PPO | Withdraw:100Hz simulation/control period is not measured PPO inference. New matched warm actor benchmark and actual process timing are separate evidence. |
|203us mean,550us p99 establish worst-case deployment | Historical raw timing/provenance needed; p99 is not WCET. A reciprocal actor duration is not actual closed-loop update rate. |
|>200ms jitter tolerance from maximum200ms test | At most successful operation at tested200ms under that protocol; no strict greater-than bound and no LQR delayed-feedback guarantee. |
|15ms LQR margin but>200ms LANS via fallback | Separate delayed learned worker from fresh local feedback; if all commands share the same stall, gain reduction alone cannot preserve timely control. |
|Bounded residual guarantees zero convergence/global safety | Only a conditional nominal ISS argument is possible; saturation, nonlinearities, lag, sampling and delay require further analysis. |
|Latency reward trains faster steering-network execution | Exogenous delay independent of action is not directly controllable by steering; new reward uses executed tracking/heading/effort/movement. |
|Removing gain/reward drops inference4930Hz->100Hz | Unsupported without measured raw distributions for each implementation; no such value is inherited. |
|LANS improves main nominal tracking over classical control | Original table has LQR0.151m and MPC0.145m versus LANS0.199m. Report this degradation and require incremental learned benefit. |
|Broad zero-shot generalization | Original sine/slalom errors1.224/1.254m contradict a broad claim. Similar lane-change success is limited transfer only. |
|50x or18x blind-distance improvement |25m/s*203us=5.075mm;25m/s*550us=13.75mm. Mean and p99 comparisons must not be mixed; neither includes sensing/queue/actuation. |
|LQR100000Hz and0.004mm blind travel |100000Hz corresponds10us and0.25mm at25m/s; stated quantities are inconsistent. Do not retain without raw timing. |
|305x energy advantage | GPU350W TDP times10ms is an assumption, not matched policy energy. No energy-superiority claim without matched measurement. |
|Mass robustness requires no retuning | Original mass results need provenance and a genuinely mass-varying plant. The current campaign varies tire stiffness, not mass, and makes no new mass claim. |

## Citation problems confirmed from the supplied manuscript

- Intro cites Kalaria as[25], but original bibliography[25] is Zhang/networked control.
  AIM5LA[26] and Hao[27] likewise do not match the listed items. Renumber all
  citations consistently after rebuilding the bibliography.
- Original[23] and[24] repeat Residual reinforcement learning for robot control
  with different leading authors; do not treat them as independent contributions.
- Supplied Kalaria PDF is arXiv2208.13856v1, titled Delay-aware Robust Control for
  Safe Autonomous Driving and Racing, with an Intelligent Vehicles journal header.
  The original purported2024TCST entry is not verified by that PDF. Cite the
  supplied version accurately until publisher metadata is verified.
- Exact editions, DOI, pagination and identities of other original references are
  not certified. Do not invent replacement metadata. The five uploaded primary
  PDFs provide a partial verified-text comparison, not a full32-reference audit.

See literature-positioning.md and stability-claim-boundaries.md. The new generated
manuscript is an evidence draft; unresolved reference verification and matched
published-method reproduction prevent calling it submission-ready.
