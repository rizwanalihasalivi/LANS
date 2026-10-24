"""Verify range-matched budget, all paired cells and native decoder evidence."""
import csv,hashlib,itertools,json,math,sys
from pathlib import Path
from statistics import mean,stdev
import numpy as np
import torch
from stable_baselines3 import PPO
HERE=Path(__file__).resolve().parent;RESEARCH=HERE.parent;ROOT=RESEARCH.parent
TRAIN=ROOT/'results/revision3-training';TEST=ROOT/'results/revision3-test';NATIVE=ROOT/'results/revision3-native-smoke'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    torch.set_num_threads(1)
    protocol=json.loads((HERE/'protocol.json').read_text());done=json.loads((TEST/'complete.json').read_text());start=json.loads((TEST/'start.json').read_text())
    assert sha(TEST/'episodes.csv')==done['episodes_sha256'] and done['source_sha256']==start['source_sha256']
    for n,d in done['source_sha256'].items():assert sha(TEST/'source'/n)==d and sha(RESEARCH/n)==d
    assert start['gate_freeze_sha256']==sha(ROOT/'results/revision2-development/freeze.json')
    training=[]
    for seed in protocol['seeds']:
        folder=TRAIN/f'residual-{seed}';m=json.loads((folder/'complete.json').read_text());model=PPO.load(folder/'policy.zip',device='cpu')
        assert model.seed==m['seed']==seed and model.num_timesteps==m['steps']==1000000
        assert m['residual_scale_rad']==.08 and m['training_profile']=='range_matched_residual_v3'
        assert sha(folder/'policy.zip')==m['policy_sha256']==done['policy_sha256'][str(seed)]['matched']
        for n,d in m['source_sha256'].items():assert sha(folder/'source'/n)==d and sha(RESEARCH/n)==d
        completed_steps=0;episodes=0
        for f in folder.glob('*.monitor.csv'):
            with f.open() as stream:
                next(stream)
                for row in csv.DictReader(stream):completed_steps+=int(row['l']);episodes+=1
        assert 0<=1000000-completed_steps<6400 and episodes>0
        training.append(dict(seed=seed,steps=m['steps'],completed_episode_steps=completed_steps,completed_episodes=episodes,wall_s=m['wall_s']))
    with (TEST/'episodes.csv').open() as f:rows=list(csv.DictReader(f))
    keys=[(int(r['seed']),int(r['speed']),r['path'],r['scenario'],r['method']) for r in rows]
    expected=set(itertools.product(protocol['seeds'],protocol['speeds'],protocol['paths'],protocol['scenarios'],protocol['methods']))
    assert len(keys)==len(set(keys))==len(expected)==done['episodes']==900 and set(keys)==expected
    indexed={k:r for k,r in zip(keys,rows)}
    for r in rows:
        assert float(r['max_rate'])<=.3500001 and int(r['steps'])<=int(r['scheduled_steps'])
        if r['survived']=='True':assert r['steps']==r['scheduled_steps']
        if r['method'] not in ['legacy_gated','lqr']:
            assert float(r['requested_residual_max_abs_rad'])<=.08000001 and float(r['requested_over_gate_cap_fraction'])==0
        if r['scenario']=='latency100' and r['method'].endswith('gated') and r['method']!='matched_ungated':
            base=indexed[int(r['seed']),int(r['speed']),r['path'],r['scenario'],'lqr']
            assert float(r['active_fraction'])==0 and r['penalized_rmse']==base['penalized_rmse']
    native_start=json.loads((NATIVE/'start.json').read_text());native_done=json.loads((NATIVE/'complete.json').read_text());native=json.loads((NATIVE/'summary.json').read_text())
    assert native_done['cases']==len(native)==5 and sha(NATIVE/'summary.json')==native_done['summary_sha256']
    assert native_start['source_sha256']==native_done['source_sha256']
    for n,d in native_done['source_sha256'].items():assert sha(NATIVE/'source'/n)==d and sha(ROOT/n)==d
    packets=0
    for name,m in native.items():
        folder=NATIVE/name;proof=json.loads((folder/'provenance.json').read_text())
        assert m==json.loads((folder/'metrics.json').read_text()) and proof['metrics_sha256']==sha(folder/'metrics.json') and proof['telemetry_sha256']==sha(folder/'telemetry.csv')
        assert m['case']['policy_sha256']==done['policy_sha256'][str(m['case']['policy_seed'])]['matched']
        with (folder/'residual-packets.csv').open() as f:
            data=list(csv.DictReader(f));assert data
            for row in data:
                mapped=float(row['mapped_residual_rad']);raw=float(row['legacy_encoded_rad'])
                assert abs(mapped)<=.08000001 and math.isclose(mapped,raw*.16,abs_tol=1e-12)
                packets+=1
        with (folder/'telemetry.csv').open() as f:data=list(csv.DictReader(f))
        assert len(data)==m['steps']
        if m['survived']:assert len(data)==1300
        for row in data:
            assert abs(float(row['command_rad']))<=.5 and abs(float(row['actuator_rate_rad_s']))<=.35000001
            if float(row['ppo_weight'])==0:assert row['command_rad']==row['lqr_command_rad']
        # Record mapping-log integrity alongside the original native runner provenance.
        (folder/'mapping-verification.json').write_text(json.dumps(dict(packets=len(list(csv.DictReader((folder/'residual-packets.csv').open()))),sha256=sha(folder/'residual-packets.csv'),max_residual_rad=.08),indent=2)+'\n')
    lines=['# Range-matched residual retraining: reserved comparison','',
           '**5,000,000 new training steps**, five scratch-trained policies (1M each); 900 paired surrogate episodes. Candidate residual range is ±0.08 rad in training and inference; frozen gate settings are unchanged.','',
           '| Region | Method | Survived / 30 | Mean penalized RMSE (m) | Active fraction | Requests beyond gate cap |','|---|---|---:|---:|---:|---:|']
    for region,method in itertools.product(protocol['scenarios'],protocol['methods']):
        rs=[r for r in rows if r['scenario']==region and r['method']==method]
        lines.append(f"| {region} | {method} | {sum(r['survived']=='True' for r in rs)} | {mean(float(r['penalized_rmse']) for r in rs):.6f} | {mean(float(r['active_fraction']) for r in rs):.2%} | {mean(float(r['requested_over_gate_cap_fraction']) for r in rs):.2%} |")
    lines+=['','## Paired range-matched gated policy comparisons','',
            'Primary comparator: legacy_gated. LQR and simply rescaled old policies are predefined secondary references. Each seed mean averages six speed/path cells; intervals are descriptive t(4) 95%, without multiple-comparison adjustment. Negative change favors retraining.','',
            '| Region | Comparator | RMSE change | Paired difference (m) | 95% interval (m) | Better seeds / 5 | Survival delta | Clear ≥5% benefit |','|---|---|---:|---:|---|---:|---:|---|']
    comparisons={}
    for region,comparator in itertools.product(protocol['scenarios'],['legacy_gated','lqr','legacy_rescaled_gated']):
        subset=lambda method,seed:[r for r in rows if r['scenario']==region and r['method']==method and int(r['seed'])==seed]
        differences=[mean(float(r['penalized_rmse']) for r in subset('matched_gated',seed))-mean(float(r['penalized_rmse']) for r in subset(comparator,seed)) for seed in protocol['seeds']]
        a=[r for r in rows if r['scenario']==region and r['method']=='matched_gated'];b=[r for r in rows if r['scenario']==region and r['method']==comparator]
        delta=mean(differences);sd=stdev(differences);half=2.776445105*sd/math.sqrt(5);ratio=delta/mean(float(r['penalized_rmse']) for r in b)
        survival=sum(r['survived']=='True' for r in a)-sum(r['survived']=='True' for r in b);wins=sum(d<0 for d in differences)
        result=dict(relative_change=ratio,seed_differences=differences,mean_difference=delta,ci95=[delta-half,delta+half],better_seeds=wins,survival_delta=survival,consistent_improvement=wins==5 and survival>=0,clear_advantage=ratio<=-.05 and wins==5 and survival>=0)
        comparisons[f'{region}/{comparator}']=result
        lines.append(f"| {region} | {comparator} | {ratio:+.2%} | {delta:+.6f} | [{delta-half:+.6f}, {delta+half:+.6f}] | {wins} | {survival:+d} | {result['clear_advantage']} |")
    survived=sum(m['survived'] for m in native.values())
    lines+=['','## Native range/interface check','',f'Five new-policy native 20 m/s nominal DLC220 smoke runs: **{survived}/5 survived**; **{packets} received worker packets** checked against the ±0.08 rad mapping. The original worker encodes normalized action ×0.5; the adapter converts that exactly once to ×0.08 before the unchanged gate. These are unpaired interface checks, not native evidence of performance improvement.','',
            '## Limits','',
            'Matching the candidate action range does not match the entire deployment distribution: training still applies the residual directly to LQR, while deployment gates, weights and delays it. This is not gate-aware training. Same normalized initial policy variance now means smaller physical exploration variance. The old policy rescaling ablation helps separate decoder effects from retraining; it does not isolate every exploration mechanism.',
            '', 'Fixed end-of-budget checkpoints only, no best-seed selection or test-driven retuning. Training seeds and known paths are reused, with fresh paired noise. Friction/stiffness/sensor/delay stresses are evaluation conditions, not a new training curriculum. All negative outcomes are retained. Five seeds and these scenarios do not establish convergence, stability, safety or broad superiority. Full paired native evaluation of the new policies remains separate.']
    (TEST/'report.md').write_text('\n'.join(lines)+'\n')
    (TEST/'verification.json').write_text(json.dumps(dict(verified=True,total_training_steps=5000000,training=training,episodes=len(rows),native_smoke_survived=survived,native_mapping_packets=packets,comparisons=comparisons),indent=2)+'\n')
    print(f'Verified five 1M-step checkpoints, 900 evaluation episodes and five native mapping checks; {survived}/5 native survived')
if __name__=='__main__':main()
