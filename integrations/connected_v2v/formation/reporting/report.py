"""Post-evaluation report separating feedback, actuator interface and fixture."""
import argparse
import json
from pathlib import Path
import statistics as stats
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from integrations.connected_v2v.demo import digest,write
from integrations.connected_v2v.formation.campaign import check,assess,PROTOCOL


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',required=True);p.add_argument('--native',required=True);a=p.parse_args()
    root=check(a.study);native=Path(a.native)
    assert json.loads((native/'plan.json').read_text())['fixture']=='longroad-v1','Invalid short-road data must not enter performance report'
    stages={};gates={};ticks=0
    for stage in ['development','confirmation']:
        rows=json.loads((root/stage/'summary.json').read_text());gate=json.loads((root/stage/'gate.json').read_text())
        assert gate==assess(rows) and gate['passed']
        for row in rows:
            folder=root/stage/f'{row["seed"]}-{int(row["speed"])}-{row["scenario"]}-{row["variant"]}'
            assert digest(folder/'ticks.jsonl')==row['raw_sha256'] and digest(folder/'case.json')==row['case_sha256']
            assert json.loads((folder/'formation.json').read_text())==row
            audit=json.loads((folder/'audit.json').read_text());assert audit['passed'] and audit['ticks']==row['vehicle_ticks']
            ticks+=row['vehicle_ticks']
        stages[stage],gates[stage]=rows,gate
    independent=json.loads((root/'independent.json').read_text());assert independent['passed'] and independent['episodes']==288
    records=json.loads((native/'summary.json').read_text());assert len(records)==16 and all(r['passed'] for r in records)
    for row in records:
        folder=native/f'{row["case"]}-{row["variant"]}-{row["adapter"]}'
        assert json.loads((folder/'verification.json').read_text())==row
    write(root/'integrity.json',dict(passed=True,python_episodes=288,python_vehicle_ticks=ticks,independent_scoring=True,
        valid_native_runs=16,native_samples=sum(r['native_samples'] for r in records),
        native_radio_receipts=sum(r['radio_receipts'] for r in records),invalid_shortroad_runs_preserved=16,
        scientific_protocol_sha256=digest(root/'protocol.json')))
    evidence=Path(__file__).resolve().parents[1]/'evidence';evidence.mkdir(exist_ok=True)
    colors=['#65758B','#16836B'];variants=['baseline','damped']
    fig,axes=plt.subplots(2,2,figsize=(13,9),layout='constrained')
    names=['Dual blackout','Cut-out'];events=['dual','cut_out'];x=np.arange(2)
    for i,v in enumerate(variants):
        values=[gates['confirmation']['recovery'][event]['baseline_s' if v=='baseline' else 'damped_s'] for event in events]
        axes[0,0].bar(x+(i-.5)*.32,values,.32,label=v,color=colors[i])
    axes[0,0].set_xticks(x,names);axes[0,0].set_ylabel('Mean settling time after event (s)')
    axes[0,0].set_title('Held-out recovery: both followers within 1 m');axes[0,0].legend()
    for i,v in enumerate(variants):
        folder=root/'confirmation'/f'7101-12-dual_blackout-{v}'
        rows=[json.loads(s) for s in (folder/'ticks.jsonl').read_text().splitlines()]
        values=[]
        for row in rows:
            errors=[]
            for own,front in [('follower-1','leader'),('follower-2','follower-1')]:
                s=row['after'][own];f=row['after'][front]
                errors.append(abs(f[0]-s[0]-4.6-6.-1.2*s[3]))
            values.append(max(errors))
        axes[0,1].plot([r['time_s']+.05 for r in rows],values,label=v,color=colors[i])
    axes[0,1].axvspan(1.15,2.65,color='#D58B27',alpha=.15,label='Sensor blackout')
    axes[0,1].axhline(1.,color='black',linestyle=':',linewidth=1)
    axes[0,1].set_xlabel('Simulation time (s)');axes[0,1].set_ylabel('Maximum follower absolute gap error (m)')
    axes[0,1].set_title('Fixed example: seed 7101, 12 m/s');axes[0,1].legend(fontsize=8)
    cases=PROTOCOL['scenarios'];x=np.arange(len(cases))
    for i,v in enumerate(variants):
        values=[stats.mean(r['first20_spacing_rms_m'] for r in stages['confirmation'] if r['variant']==v and r['scenario']==case) for case in cases]
        axes[1,0].bar(x+(i-.5)*.32,values,.32,color=colors[i],label=v)
    axes[1,0].set_xticks(x,[case.replace('_','\n') for case in cases],fontsize=8)
    axes[1,0].set_ylabel('First-20-second spacing RMS (m)');axes[1,0].set_title('Longer observation does not dilute this score')
    factors=[('baseline','legacy'),('damped','legacy'),('baseline','recovery'),('damped','recovery')]
    for offset,case in enumerate(['nominal','dual_blackout']):
        values=[next(r['final5_spacing_rms_m'] for r in records if r['case']==case and (r['variant'],r['adapter'])==factor) for factor in factors]
        axes[1,1].bar(np.arange(4)+(offset-.5)*.32,values,.32,label=case.replace('_',' '))
    axes[1,1].set_xticks(np.arange(4),['Old gains\nold cap','New gains\nold cap','Old gains\nrecovery cap','New gains\nrecovery cap'],fontsize=8)
    axes[1,1].set_ylabel('Native final-5-second RMS (m)');axes[1,1].set_title('Native factorial: cap correction is a separate effect');axes[1,1].legend(fontsize=8)
    fig.suptitle('Formation recovery v3: faster fresh-data recovery, unchanged blind braking\n3 independent Python seed clusters per stage; 1 native seed; no physical-safety/string-stability claim',fontsize=12)
    fig.savefig(evidence/'formation-v3.png',dpi=170);fig.savefig(evidence/'formation-v3.pdf');plt.close(fig)
    stage=gates['confirmation'];rows=stages['confirmation']
    table=[]
    for case in cases:
        values=[stats.mean(r['first20_spacing_rms_m'] for r in rows if r['scenario']==case and r['variant']==v) for v in variants]
        table.append('| '+case+' | '+' | '.join(f'{v:.4f}' for v in values)+' |')
    native_table=[]
    for case in ['nominal','v2v_blackout','radar_blackout','dual_blackout']:
        for variant,adapter in factors:
            row=next(r for r in records if r['case']==case and r['variant']==variant and r['adapter']==adapter)
            native_table.append(f'| {case} | {variant} | {adapter} | {row["first20_spacing_rms_m"]:.4f} | {row["final5_spacing_rms_m"]:.4f} |')
    dual=lambda v,c:next(r for r in records if r['case']=='dual_blackout' and r['variant']==v and r['adapter']==c)
    cap_gain=100*(1-dual('baseline','recovery')['first20_spacing_rms_m']/dual('baseline','legacy')['first20_spacing_rms_m'])
    gain_only=100*(1-dual('damped','recovery')['first20_spacing_rms_m']/dual('baseline','recovery')['first20_spacing_rms_m'])
    peak_accel=max(r['speed_derived_accel_range'][name]['max_m_s2'] for r in records for name in r['speed_derived_accel_range'])
    max_speed=max(r['peak_speeds_m_s'][name] for r in rows if r['variant']=='damped' for name in r['peak_speeds_m_s'])
    body=f'''# Formation recovery v3 — 3 November 2026

Base: `43679a5b`. One analytically chosen fresh-data feedback candidate passed
all frozen development and held-out gates. Separate native factorial tests
identify the follower speed-cap adapter mismatch. Blind-phase braking is
preserved; unknown traffic is never replaced with fabricated fresh knowledge.

[Protocol](PROTOCOL.md) · [Run instructions](README.md) · [Figure](evidence/formation-v3.png) · [PDF](evidence/formation-v3.pdf)

## What changed

For fixed-headway error e and predecessor relative speed dv, the same law
`a=kp*e+kv*dv` now has one candidate kp=0.64, kv=0.832, derived from nominal
double poles -0.8 /s. Baseline remains kp=0.35, kv=0.9. This nominal calculation
is not a nonlinear/delayed/string-stability proof. Both variants retain 6 m
standstill gap, 1.2 s headway, v2 sensing/source agreement, original timestamps,
0.4 s V2V / 0.2 s range TTL and [-6,2.5] m/s² requested acceleration limits.
Both variants receive the same cruise+8 m/s follower speed envelope; leaders
remain at cruise. No learning, parameter search, target-seed selection or
post-outcome criterion change occurred.

## Held-out Python results

144 development + 144 confirmation episodes, **{ticks:,} vehicle ticks**.
Each stage has three independent seeds, three speeds and eight scenario
classes, comparing both variants with matched initial states/noise/faults.
Confirmation uses new seeds 7101/7102/7103 and events shifted by 0.15 s.
All receiver/control/physics replays and an independent standard-library scoring
checker passed; a corrupted summary was rejected.

| Recovery event | Baseline settling | New settling | Reduction |
|---|---:|---:|---:|
| Dual-sensor blackout, after event ends | {stage['recovery']['dual']['baseline_s']:.2f} s | **{stage['recovery']['dual']['damped_s']:.2f} s** | **{stage['recovery']['dual']['gain_percent']:.2f}%** |
| Cut-out predecessor handover | {stage['recovery']['cut_out']['baseline_s']:.2f} s | **{stage['recovery']['cut_out']['damped_s']:.2f} s** | **{stage['recovery']['cut_out']['gain_percent']:.2f}%** |

Settling requires BOTH followers within 1 m fixed-headway error for at least
2 s, fresh source knowledge, and no later error violation in that segment.
Neither baseline nor candidate was censored at 30 s in the primary events.
The three-seed-cluster bootstrap bounds passed, but some intervals collapse
because all clusters share a 50 ms quantized event time. A zero-width bootstrap
interval does NOT establish zero uncertainty or generalization to new traffic.

The observation horizon is 30 s to see settling; fixed FIRST-20-second spacing
RMS below prevents apparent improvement merely by averaging over a longer run:

| Scenario | Baseline RMS (m) | New RMS (m) |
|---|---:|---:|
{chr(10).join(table)}

Every frozen gate passed: at least 20% settling gains, first-20 target RMS
nonregression, nominal nonregression, >=99% matched follower progress in EACH
cell at both horizons, and the original 5%+0.1 command-jerk budget. Candidate
collision/corridor/stale-source/blind-brake/actuator/speed-envelope violations
were all zero. Command jerk mean changed from {stage['command_jerk_mean']['baseline']:.4f}
to {stage['command_jerk_mean']['damped']:.4f} m/s³, so faster response has a small
measured smoothness cost within the frozen budget. Maximum candidate speed on
confirmation was {max_speed:.4f} m/s (scenario-dependent envelope <=cruise+8).
These are finite-model observations, not vehicle-safety guarantees.

**The blind phase is not solved:** dual-blackout first-20 RMS remains about
6 m. Braking without fresh knowledge is retained. Cut-in/out first-20 RMS
also remains about 7.9 m because imposed target changes create an abrupt gap
reference and bounded acceleration cannot close that gap instantly. This work
improves subsequent recovery, not autonomous cut-in recognition or all errors.

## Native adapter correction and factorial attribution

The old native adapter clipped ALL speed setpoints to the leader's 8 m/s,
preventing followers from catching up to a large gap. The new adapter keeps
leaders at 8 m/s and allows followers a bounded recovery setpoint up to 16 m/s.
This is compared separately from feedback gains: 2 laws x 2 adapters x 4 cases,
**16 valid 30 s runs / {sum(r['native_samples'] for r in records):,} native samples**,
with native Radar and Emitter/Receiver and all source/control/pose audits passed.
Each native cell has one world seed 42; there is no native multi-seed interval.

| Case | Law | Adapter | First-20 RMS (m) | Final-5 RMS (m) |
|---|---|---|---:|---:|
{chr(10).join(native_table)}

On the native dual-blackout case, correcting the cap with OLD gains reduces
first-20 RMS by **{cap_gain:.2f}%**. With the corrected adapter held fixed,
the new gains add a separately measured **{gain_only:.2f}%** reduction. Do not
attribute the combined effect to gains alone. Final-5 RMS falls from
{dual('baseline','legacy')['final5_spacing_rms_m']:.4f} m (old law/cap) to
{dual('damped','recovery')['final5_spacing_rms_m']:.4f} m (new law/recovery cap).

Native acceleration checks bound the REQUESTED commands and setpoints. The
speed servo/tire response differs: maximum observed speed-derived acceleration
was {peak_accel:.4f} m/s², slightly above the requested +2.5 m/s² ceiling. No
physical acceleration hard-bound certification is claimed. Height, tilt, forward
heading, corridor and road-bound checks now validate every native sample.
Positive gap proxies are not a contact-sensor collision certificate.

## Fixture defect found and corrected

The initial 30 s native fixture reused a 200 m road centered at x=50 (bounds
[-50,150]). Cars crossed its end; late headings flipped and messages disappeared.
Those **16 short-road runs are invalid as on-road performance evidence** even
though their old longitudinal-gap-only proxy checks said passed. Their worlds,
source snapshots and raw outcomes are retained with an invalidation record.

Only the flat-road extent was corrected to [-500,1500], with added explicit
GPS height/attitude/map/corridor guards. The SAME 16 controller/adapter cases
were rerun with unchanged gains, sensor models, seed, fault timing and bounds.
Only these valid long-road runs enter the table. Python outcomes were unaffected.
This was a fixture correction, not relaxed criteria or retuning to a preferred result.

## Checks, evidence and remaining scope

158 tests passed in the combined regression command; the updated four native
fixture tests passed separately (one repeat plus three new negative pose cases):
**161 distinct tests passed**. Scientific source freeze:
`{digest(root/'protocol.json')}`. Controller/model replay shares the original
kernels; the separate stdlib checker independently recomputes first-20/full
metrics, constraints, progress and settling/censoring but is not a new simulator.

[Python/source bundle](evidence/formation-python-v3.zip) and
[native bundle including invalid fixture diagnostics](evidence/formation-native-v3.zip)
retain all runs, hashes, protocols, tests, source snapshots and figures.
[Outer checksums](evidence/SHA256SUMS) and each ZIP's MANIFEST.json verify integrity.
Current-instance data roots are `results/connected-v2v-formation-v3/`,
`results/connected-v2v-formation-native-v3/` (INVALID short road), and
`results/connected-v2v-formation-native-v3-longroad/` (VALID native factorial).

V1/v2 sources/evidence and the main PPO/controller track remain unchanged.
Membership/target identity is still scripted; native cut-in transfer, general
multi-lane/unconnected perception, string stability, real radio/time-sync,
wall-clock deadlines and physical validation remain open. The next stage must
declare new data/criteria rather than retune on these held-out results.
'''
    (Path(__file__).resolve().parents[1]/'RESULTS.md').write_text(body)
    print('Report sealed: 288 Python episodes and 16 valid native runs; 16 invalid short-road diagnostics retained.')


if __name__=='__main__':main()
