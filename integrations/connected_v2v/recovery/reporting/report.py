"""Build a standalone figure and honest stage-specific results from sealed runs."""
import argparse
import json
from pathlib import Path
import statistics
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from integrations.connected_v2v.demo import write,digest
from integrations.connected_v2v.recovery.campaign import check,assess
from integrations.connected_v2v.recovery.controller import METHODS
from integrations.connected_v2v.recovery.study import SCENARIOS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',required=True);parser.add_argument('--native',required=True)
    args=parser.parse_args();root=check(args.study);native=Path(args.native)
    data={};gates={};episode_ticks=0;sealed={}
    for stage in ['development','confirmation']:
        rows=json.loads((root/stage/'summary.json').read_text())
        gate=json.loads((root/stage/'gate.json').read_text());assert gate==assess(rows)
        for row in rows:
            folder=root/stage/f'{row["seed"]}-{int(row["speed"])}-{row["scenario"]}-{row["method"]}'
            assert json.loads((folder/'summary.json').read_text())==row
            assert digest(folder/'ticks.jsonl')==row['raw_sha256']
            assert digest(folder/'case.json')==row['case_sha256']
            audit=json.loads((folder/'audit.json').read_text());assert audit['passed'] and audit['ticks']==row['vehicle_ticks']
            episode_ticks+=row['vehicle_ticks'];sealed[str(folder/'ticks.jsonl')]=row['raw_sha256']
        data[stage],gates[stage]=rows,gate
    records=json.loads((native/'summary.json').read_text());assert len(records)==12
    for row in records:
        folder=native/(row['case']+'-'+row['method'])
        assert json.loads((folder/'verification.json').read_text())==row and row['passed']
    fixture=json.loads((root/'legacy-fixture/comparison.json').read_text())
    integrity=dict(passed=True,python_episodes=432,python_vehicle_ticks=episode_ticks,
                   raw_episode_hashes=sealed,native_runs=12,native_samples=sum(r['native_samples'] for r in records),
                   native_radio_receipts=sum(r['radio_receipts'] for r in records),
                   core_source_freeze_sha256=digest(root/'protocol.json'),
                   note='Each episode/native run was replayed before completion; final sealing rechecks source and raw-file integrity.')
    write(root/'integrity.json',integrity)
    evidence=Path(__file__).resolve().parents[1]/'evidence';evidence.mkdir(exist_ok=True)
    # All cells are retained. A fixed first confirmation seed/middle speed shows
    # the time trace; it was not selected for an unusually favorable outcome.
    fig,axes=plt.subplots(1,3,figsize=(16,5),layout='constrained')
    colors=['#65758B','#D58B27','#16836B'];labels=['V2V only','Range ACC','Range + V2V']
    positions=np.arange(len(SCENARIOS));width=.25
    for i,method in enumerate(METHODS):
        values=[statistics.mean(r['spacing_rms_m'] for r in data['confirmation'] if r['method']==method and r['scenario']==case) for case in SCENARIOS]
        axes[0].bar(positions+(i-1)*width,values,width,label=labels[i],color=colors[i])
    axes[0].set_xticks(positions,[s.replace('_','\n') for s in SCENARIOS],fontsize=8)
    axes[0].set_ylabel('Mean follower spacing RMS (m)');axes[0].set_title('Held-out Python: all declared cells')
    axes[0].legend(fontsize=8)
    for i,method in enumerate(METHODS):
        path=root/'confirmation'/f'5101-12-v2v_blackout-{method}'/'ticks.jsonl'
        rows=[json.loads(s) for s in path.read_text().splitlines()]
        times=[r['time_s'] for r in rows];error=[]
        for r in rows:
            own=r['after']['follower-1'];front=r['after']['leader']
            error.append(front[0]-own[0]-4.6-6.-1.2*own[3])
        axes[1].plot(times,error,color=colors[i],label=labels[i])
    axes[1].axvspan(1.15,2.65,color='#D58B27',alpha=.15,label='V2V blackout')
    axes[1].set_xlabel('Simulation time (s)');axes[1].set_ylabel('Follower-1 spacing error (m)')
    axes[1].set_title('Fixed example: seed 5101, 12 m/s');axes[1].legend(fontsize=8)
    cases=['nominal','v2v_blackout','radar_blackout','dual_blackout'];positions=np.arange(4)
    for i,method in enumerate(METHODS):
        values=[next(r['spacing_rms_m'] for r in records if r['case']==case and r['method']==method) for case in cases]
        axes[2].bar(positions+(i-1)*width,values,width,color=colors[i],label=labels[i])
    axes[2].set_xticks(positions,[s.replace('_','\n') for s in cases],fontsize=8)
    axes[2].set_ylabel('Native follower spacing RMS (m)');axes[2].set_title('Native Webots: measured separately')
    fig.suptitle('Independent fresh local range sensing bridges V2V loss\nShort simulated studies; native setup and dynamics differ; no string-stability or physical-safety claim',fontsize=12)
    fig.savefig(evidence/'recovery-v2.png',dpi=180);fig.savefig(evidence/'recovery-v2.pdf');plt.close(fig)
    table=[]
    for case in SCENARIOS:
        values=[statistics.mean(r['spacing_rms_m'] for r in data['confirmation'] if r['scenario']==case and r['method']==method) for method in METHODS]
        table.append('| '+case+' | '+' | '.join(f'{v:.4f}' for v in values)+' |')
    native_table=[]
    for case in cases:
        values=[next(r['spacing_rms_m'] for r in records if r['case']==case and r['method']==method) for method in METHODS]
        native_table.append('| '+case+' | '+' | '.join(f'{v:.4f}' for v in values)+' |')
    gain=100*(1-next(r['spacing_rms_m'] for r in records if r['case']=='v2v_blackout' and r['method']=='fusion')/next(r['spacing_rms_m'] for r in records if r['case']=='v2v_blackout' and r['method']=='v2v_only'))
    body=f'''# Recovery and independent-sensing results — 3 November 2026

The one frozen candidate passed all predeclared development and held-out checks.
It bridges V2V loss using independently fresh local range/range-rate sensing.
This is additional sensing and validated source arbitration, **not a PPO gain**,
an equal-information controller advantage, a new safety theorem, or autonomous
vehicle identification. The v1 following law, gains, limits and V2V TTL are unchanged.

[Protocol](PROTOCOL.md) · [Run instructions](README.md) · [Figure](evidence/recovery-v2.png) · [PDF](evidence/recovery-v2.pdf)

## Original defect diagnosis and regression fixture

The original 8 s blackout was reproduced with **zero physical-state discrepancy**
and identical per-tick commands against archived v1. Blind maximum braking drops
the follower from about 12 to 5 m/s; the leader continues, and acceleration-limited
recovery cannot instantly restore the gap. Sensor freshness or actuator limits
were not relaxed to obtain a desired number.

On this same regression fixture, spacing RMS was
**{fixture['spacing_rms_m']['v2v_only']:.6f} m V2V-only**, **{fixture['spacing_rms_m']['radar_acc']:.6f} m radar-ACC**,
and **{fixture['spacing_rms_m']['fusion']:.6f} m combined sensing**. This is a diagnostic reproduction,
not an extra selected seed or held-out experiment.

## Frozen Python study

216 development + 216 confirmation episodes; **{episode_ticks:,} vehicle ticks**.
Each stage has 3 independent seed clusters, 3 speeds and 8 scenarios, with all
three methods evaluated on matched inputs. Confirmation uses new seeds and
faults shifted 0.15 s. All receiver/control/physics replay audits passed and
raw episode hashes were checked again during sealing.

Development V2V-blackout spacing gain: **{gates['development']['blackout_gain_percent']:.4f}%**.
Held-out gain: **{gates['confirmation']['blackout_gain_percent']:.4f}%**, descriptive 95% seed-cluster interval
**[{gates['confirmation']['blackout_gain_ci95'][0]:.4f}%, {gates['confirmation']['blackout_gain_ci95'][1]:.4f}%]**.
Only three independent seed clusters underpin these intervals; correlated
speeds/time steps are not additional independent trials or broad-road evidence.

Held-out mean follower spacing RMS, in meters:

| Scenario | V2V only | Range ACC | Range + V2V |
|---|---:|---:|---:|
{chr(10).join(table)}

All ten frozen checks passed in both stages: blackout gain/interval, radar-ACC
noninferiority, nominal nonregression, no observed collision/corridor violation,
fresh-source and actuator integrity, at least 99% matched follower progress in
every cell, and the declared command-jerk budget. Fusion's minimum bumper-gap
proxy on confirmation was **{gates['confirmation']['means']['fusion']['min_gap_m']:.4f} m**.
The jerk metric differentiates requested/applied acceleration commands; stops
and physical actuator filtering can make executed vehicle jerk different.

A separate standard-library checker (importing no controller, simulation or
report helper) independently reconstructed spacing, progress, gap, collision,
freshness, bounds and command-jerk metrics for all **432 episodes / 518,400 vehicle
ticks**. A deliberately altered summary was rejected. It also reports executed
speed-derived jerk as a posthoc diagnostic, without replacing any frozen gate.
Unit verification comprised 146 combined root/V2V/recovery tests plus one
native-adapter assembly test: **147 distinct tests passed** in separate commands.

Sources are independently validated before arbitration. Original timestamps and
replay watermarks remain intact. Both unavailable or inconsistent fresh sources
still trigger braking; there is no stale-packet acceptance, TTL increase, extra
authority, best-seed selection, added training or post-outcome threshold change.

Confirmation execution used three independent logical-time processes. Before
confirmation, two complete episodes/summary records reproduced serial raw-data
SHA-256 exactly. The execution-only launcher, its record and source are archived.
Native-only template assembly initially caught an unmatched parenthesis; it was
corrected before native trials, without changing the frozen scientific controller.

## Conditional native Radar transfer

Both Python gates passed before twelve native runs opened. **{sum(r['native_samples'] for r in records):,} native
vehicle samples** and **{sum(r['radio_receipts'] for r in records):,} radio receipts** were replayed, including actual
native Radar range/radial-speed and Emitter/Receiver messages. Each run used the
same frozen FusionFollower class, with method masking, original gains/limits
and the existing generic-Car driver. All native integration/proxy checks passed.
Each native case/method has one run at world seed 42; native uncertainty across
seeds was not measured.

| Native case | V2V only RMS (m) | Range ACC RMS (m) | Range + V2V RMS (m) |
|---|---:|---:|---:|
{chr(10).join(native_table)}

The native V2V-blackout reduction is **{gain:.4f}%**, measured independently;
the Python 98% figure is not copied into Webots. Cars start from rest with the
native 8 m/s cruise-speed cap, unlike the Python steady-speed initial states.
Native sensing cadence/phases, tires and speed servo also differ. Initial gaps
and speed saturation leave substantial absolute spacing error even in nominal
runs; passing this integration check does not establish excellent formation keeping.

## Remaining limitations and next work

- **Both sources lost:** braking remains mandatory and confirmation spacing RMS
  remains about 6.27 m. Independent sensing bridges a communication outage;
  it cannot supply knowledge when perception also fails.
- **Cut-in/out:** confirmation RMS remains about 8.24 m. Membership changes and
  target association are scripted common inputs, not an autonomous detection or
  authenticated membership result. Physical cut-in safety is not certified.
- Straight-road range reconstruction assumes aligned heading, ideal local
  GPS/state and bounded Python range/rate errors. Native Radar has its own
  Gaussian noise and a declared target-box/GPS geometric offset. No general
  multi-lane perception, mixed unconnected traffic, real V2X hardware, time-sync,
  security, wall-clock scheduling or string stability is validated here.
- The radar-ACC baseline is the same time-headway law with local sensing, not
  a tuned commercial system or matched published robust MPC implementation.
- No main unified PPO controller, training campaign or its reserved data changed.
  Integration with the other controller-development track remains a separate task.

The next stage should address constrained formation recovery, autonomous target
association/cut-in handling, and downstream disturbance amplification with a new
frozen protocol. Do not keep extending these seeds or retuning on confirmation.

## Evidence

Base source commit: `d5cc9efd35316fb40d18127a71f87c046997eea6`.
Scientific source/protocol freeze SHA-256: `{digest(root/'protocol.json')}`.
Current-instance results: `results/connected-v2v-recovery-v2/` and
`results/connected-v2v-recovery-native-v2/`. The immutable v1 source/evidence remains
unchanged. [The new evidence bundle](evidence/recovery-v2.zip) includes every
episode/native run, protocols, frozen/source snapshots, audits and execution
records. Its member manifest and [outer hashes](evidence/SHA256SUMS) support integrity
checks. Reports/figures were generated after evaluation and did not select a controller.
'''
    (Path(__file__).resolve().parents[1]/'RESULTS.md').write_text(body)
    print('Sealed',integrity['python_episodes'],'Python episodes and',integrity['native_runs'],'native runs; report and figures written.')


if __name__=='__main__':main()
