# Conditional native sensor-ablation check

Run only after all frozen Python development AND confirmation checks pass.
Use the exact Python `FusionFollower` class, original gains/limits, and native
Webots Radar rather than another robot's Supervisor truth. Compare V2V-only,
radar-ACC and fusion in nominal, V2V-blackout, radar-blackout and dual-blackout
cases: twelve runs, three generic Cars, 12 s per run, no tuning or added learning.

Native sensing/control is 50 ms, radio and Radar sampling 100 ms. Blackouts are
5-6.5 s, leader brake request 7-8 s. Radar uses its actual range/radial-speed,
Gaussian noise 0.05 m/0.02 m/s and nearest forward-target association. All cars
are in one known ordered straight-road convoy. This association is not an
arbitrary-traffic identification result. Radar origin is at the local GPS
(x=1.4 m); target box center is x=1.3 m, so the declared bumper-gap proxy is
distance*cos(azimuth)+0.1-4.6 m. The correction is geometric, not outcome-tuned.

All runs require actual movement, replayable native sensor/message histories,
unchanged source hashes, intact bounds/freshness and positive conservative
longitudinal gap proxies. Report spacing/progress/fallback separately for each
method and case. A Python performance improvement is not assumed to transfer.
No timing, physical safety, main-PPO promotion or string-stability claim follows.
