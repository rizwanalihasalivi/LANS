"""Audit raw native CSVs and report all frozen operating regions, including regressions."""
import argparse,csv,hashlib,itertools,json,math
from pathlib import Path
from statistics import mean,stdev
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def read_csv(folder):
    with (folder/'telemetry.csv').open() as f:
        return [{k:(v if k=='supervisor_reason' else float(v)) for k,v in r.items()} for r in csv.DictReader(f)]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();out=args.output
    start=json.loads((out/'start.json').read_text());complete=json.loads((out/'complete.json').read_text());protocol=start['protocol']
    summary=json.loads((out/'summary.json').read_text());assert sha(out/'summary.json')==complete['summary_sha256']
    assert complete['source_sha256']==start['source_sha256']
    for name,digest in start['source_sha256'].items():
        assert sha(out/'source'/name)==digest
        assert sha(ROOT/name)==digest
    freeze=json.loads((out/'source/results/revision2-development/freeze.json').read_text())
    assert start['freeze_sha256']==sha(ROOT/'results/revision2-development/freeze.json')
    for name,digest in freeze['source_sha256'].items():assert sha(ROOT/'research'/name)==digest
    for name,digest in start['policy_sha256'].items():assert sha(ROOT/'results/research-training'/name/'policy.zip')==digest
    expected={(s,v,region,m) for s,v,region,m in itertools.product(protocol['seeds'],protocol['speeds'],protocol['scenarios'],protocol['methods'])} if start['phase']=='reserved' else {(0,20,'nominal',m) for m in protocol['methods']}
    assert len(summary)==complete['cases']==len(expected)
    seen=set();rows=[]
    for name,metrics in summary.items():
        folder=out/name;case=json.loads((folder/'case.json').read_text());proof=json.loads((folder/'provenance.json').read_text());vehicle=json.loads((folder/'vehicle.json').read_text())
        assert case==metrics['case'];assert json.loads((folder/'metrics.json').read_text())==metrics
        for file,key in [('case.json','config_sha256'),('generated-world.wbt','generated_world_sha256'),('telemetry.csv','telemetry_sha256'),('metrics.json','metrics_sha256')]:assert sha(folder/file)==proof[key]
        assert proof['source_sha256']==start['source_sha256']
        assert abs(vehicle['mass_kg']-1650)<1e-8 and abs(vehicle['nominal_cg_x_m']-1.4)<1e-8 and abs(vehicle['nominal_yaw_inertia']-4224)<1e-7
        assert vehicle['physics_step_s']==.001 and vehicle['controller_period_s']==.01
        key=(case['policy_seed'],case['speed'],case['scenario'],case['mode']);assert key not in seen;seen.add(key)
        assert case['gate_config']==freeze['selected_config']
        spec=protocol['scenarios'][case['scenario']]
        assert all(case[k]==v for k,v in spec.items())
        if start['phase']=='reserved':assert case['seed']==protocol['noise_seed_base']+case['policy_seed']*10000+case['speed']*100+list(protocol['scenarios']).index(case['scenario'])
        if case['mode']!='lqr':assert case['policy_sha256']==sha(Path(case['policy']))
        records=read_csv(folder);scheduled=round((220/case['speed']+2)/.01)
        assert len(records)==metrics['steps']<=scheduled==metrics['scheduled_steps']
        if metrics['survived']:assert len(records)==scheduled
        squares=[];weights=[];ages=[];gates=[];inferences=[];lastseq=0;unique=[]
        for i,r in enumerate(records):
            assert all(math.isfinite(v) for k,v in r.items() if k!='supervisor_reason')
            assert r['step']==i+1 and abs(r['t_test_s']-i*.01)<1e-8
            assert abs(r['t_state_s']-r['t_command_s']-.01)<1e-8
            assert abs(r['command_rad'])<=.5 and abs(r['actuator_rad'])<=.5 and abs(r['actuator_rate_rad_s'])<=.35000001
            assert 0<=r['ppo_weight']<=.5
            if r['ppo_weight']>0:
                assert r['supervisor_reason']=='earned' and r['prediction_available']==1
                assert r['predicted_lqr_cost']-r['predicted_candidate_cost']>=max(1e-7,.01*r['predicted_lqr_cost'])-1e-14
                assert r['ppo_available']==1 and 0<=r['command_age_s']<.05
            else:assert r['command_rad']==r['lqr_command_rad']
            if r['ppo_available']:
                assert abs(r['t_command_s']-r['t_observation_s']-r['command_age_s'])<1e-8
                assert r['t_available_sim_s']<=r['t_command_s']+1e-9
                assert r['t_available_sim_s']-r['t_observation_s']>=case['delay_ms']/1000-1e-9
                assert r['inference_end_wall_s']>=r['inference_start_wall_s'] and r['output_sequence']>=lastseq
                if r['output_sequence']>lastseq:unique.append(r['inference_wall_s'])
                lastseq=r['output_sequence'];ages.append(r['command_age_s'])
            squares.append(r['error_m']**2);weights.append(r['ppo_weight']);gates.append(r['gate_wall_s'])
        score=math.sqrt((sum(squares)+(scheduled-len(records))*6.25)/scheduled)
        assert abs(score-metrics['penalized_rmse_m'])<1e-12
        assert abs(math.sqrt(mean(squares))-metrics['rmse_m'])<1e-12
        row=dict(case=name,seed=case['policy_seed'],speed=case['speed'],scenario=case['scenario'],method=case['mode'],survived=metrics['survived'],penalized_rmse_m=score,rmse_m=metrics['rmse_m'],active_fraction=mean(w>0 for w in weights),mean_weight=mean(weights),age_p99_s=float(np.quantile(ages,.99)) if ages else 0,age_stale_fraction=mean(a>=.05 for a in ages) if ages else 0,gate_p99_wall_s=float(np.quantile(gates,.99)),inference_unique_packets=len(unique),inference_p99_wall_s=float(np.quantile(unique,.99)) if unique else 0,dropped_requests=int(records[-1]['worker_dropped_requests']))
        rows.append(row)
    assert seen==expected
    exact=[]
    if start['phase']=='reserved':
        fields=['t_command_s','t_state_s','command_rad','actuator_rad','measured_center_angle_rad','speed_truth_m_s','x_cg_m','y_cg_m','heading_rad','vy_truth_m_s','yaw_rate_rad_s','error_m','heading_error_rad','estimated_error_m','estimated_vy_m_s','lqr_command_rad']
        for seed,speed in itertools.product(protocol['seeds'],protocol['speeds']):
            base=read_csv(out/f'latency100-seed{seed}-v{speed}-lqr')
            for method in ['gated_residual','gated_full']:
                records=read_csv(out/f'latency100-seed{seed}-v{speed}-{method}')
                assert all(r['ppo_weight']==0 and r['command_rad']==r['lqr_command_rad'] for r in records)
                same_length=len(base)==len(records)
                differences={k:max(abs(a[k]-b[k]) for a,b in zip(base,records)) for k in fields}
                exact.append(dict(seed=seed,speed=speed,method=method,same_length=same_length,max_abs_differences=differences,exact=same_length and all(v==0 for v in differences.values())))
    with (out/'episodes.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    lines=['# Frozen-gate native Webots transfer','',f"Audited **{len(rows)} native runs**, survived **{sum(r['survived'] for r in rows)}/{len(rows)}**. Frozen gate and all policy hashes verified; no retraining or retuning.",'',
           '| Region | Method | Survived | Mean penalized RMSE (m) | Active ticks | Mean weight | Mean per-run p99 age (ms) |','|---|---|---:|---:|---:|---:|---:|']
    for scenario,method in itertools.product(protocol['scenarios'],protocol['methods']):
        subset=[r for r in rows if r['scenario']==scenario and r['method']==method]
        if not subset:continue
        lines.append(f"| {scenario} | {method} | {sum(r['survived'] for r in subset)}/{len(subset)} | {mean(r['penalized_rmse_m'] for r in subset):.6f} | {mean(r['active_fraction'] for r in subset):.2%} | {mean(r['mean_weight'] for r in subset):.4f} | {1000*mean(r['age_p99_s'] for r in subset):.2f} |")
    comparisons={}
    if start['phase']=='reserved':
        lines+=['','## Paired comparisons','', 'Each paired seed mean aggregates the three speeds. Intervals are descriptive t(4) 95% intervals across five seed differences; no multiplicity-adjusted significance claim. Residual is primary; full-command is a predefined secondary comparison.','',
                '| Region | Hybrid | RMSE change | Paired difference (m) | 95% interval (m) | Better seeds / 5 | Survival delta | Clear ≥5% advantage |','|---|---|---:|---:|---|---:|---:|---|']
        for scenario,method in itertools.product(protocol['scenarios'],['gated_residual','gated_full']):
            selected=lambda m,s:[r for r in rows if r['scenario']==scenario and r['method']==m and r['seed']==s]
            differences=[mean(r['penalized_rmse_m'] for r in selected(method,s))-mean(r['penalized_rmse_m'] for r in selected('lqr',s)) for s in protocol['seeds']]
            base=[r for r in rows if r['scenario']==scenario and r['method']=='lqr'];hybrid=[r for r in rows if r['scenario']==scenario and r['method']==method]
            delta=mean(differences);sd=stdev(differences);half=2.776445105*sd/math.sqrt(5);relative=delta/mean(r['penalized_rmse_m'] for r in base)
            survival=sum(r['survived'] for r in hybrid)-sum(r['survived'] for r in base);wins=sum(d<0 for d in differences)
            comparisons[f'{scenario}/{method}']=dict(seed_differences=differences,mean_difference=delta,seed_sd=sd,ci95=[delta-half,delta+half],relative_change=relative,survival_delta=survival,better_seeds=wins,consistent_improvement=wins==5 and survival>=0,clear_advantage=relative<=-.05 and wins==5 and survival>=0,nominal_preserved=relative<=.02 and survival>=0 if scenario=='nominal' else None)
            lines.append(f'| {scenario} | {method} | {relative:+.2%} | {delta:+.6f} | [{delta-half:+.6f}, {delta+half:+.6f}] | {wins} | {survival:+d} | {comparisons[f"{scenario}/{method}"]["clear_advantage"]} |')
        lines+=['',f"Severe-delay paired physical/control trajectories exactly equal LQR: **{sum(r['exact'] for r in exact)}/{len(exact)}**. Zero learned weight and local command equality verified for every severe-delay tick. Per-field maximum differences are retained in `verification.json`; exact means numerical equality, not a tolerance."]
    lines+=['','## Scope and limits','',
            'DLC220 only; same five trained policy seeds, fresh native noise seeds. Every method shares each physical/sensor condition. The gate uses nominal state estimates, local curvature and measured wheel angle; it never receives changed contact parameters. Native force-dependent contact slip is not Fiala. Contact softening divides calibrated slip by 0.65; this is not a measured 35% corner-stiffness reduction.',
            '', 'Both learned controllers use a real separate inference process, one job in flight, drop while busy. Added 0/20/100 ms is a minimum simulation-clock availability delay, not a guarantee of actual age. Two native runs share the cloud CPU; timing and output schedules are not deterministically repeatable or real-time guarantees. Zero learned authority should give deterministic physical LQR behavior, which is checked directly.',
            '', 'The actuator keeps the existing explicit Euler 1 ms lag/rate implementation and native wheel-angle proxy; these differ slightly from surrogate RK4/virtual-angle sensing. Nominal mass/CG/inertia audits pass. Native warmup and zero initial path offset differ from the surrogate initial disturbance. Reported improvement is conditional on this tested grid, not broad generalization or safety/stability proof. All scenarios and both learned roles are reported without post-test selection or retuning.']
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    (out/'verification.json').write_text(json.dumps(dict(verified=True,cases=len(rows),survived=sum(r['survived'] for r in rows),comparisons=comparisons,severe_delay=exact),indent=2)+'\n')
    print(f'Audited {len(rows)} runs; survived {sum(r["survived"] for r in rows)}; severe-delay exact {sum(r["exact"] for r in exact)}/{len(exact)}')
if __name__=='__main__':main()
