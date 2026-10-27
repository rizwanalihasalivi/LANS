"""Audit all arm budgets, gate/reward diagnostics and the complete paired grid."""
import csv,hashlib,itertools,json,math,pickle
from statistics import mean
from pathlib import Path
import torch
from stable_baselines3 import PPO
from bootstrap import HERE,RESEARCH,ROOT
from run_pilots import screening
OUT=ROOT/'results/revision4-pilots';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def read(path):
    with path.open() as f:return list(csv.DictReader(f))
def typed(rows):
    output=[]
    for r in rows:
        x=dict(r)
        for k in ['seed','speed','steps','scheduled_steps']:x[k]=int(x[k])
        for k in ['penalized_rmse','rmse','active_fraction','mean_weight','max_rate','corridor_violation_fraction','age_p99']:x[k]=float(x[k])
        x['survived']=x['survived']=='True';output.append(x)
    return output

def main():
    torch.set_num_threads(1)
    protocol=json.loads((HERE/'protocol.json').read_text());reserved=json.loads((HERE/'reserved_split.json').read_text());assert not set(reserved['development_ids']) & set(reserved['reserved_ids']);assert reserved['pilot_protocol_sha256']==sha(HERE/'protocol.json');start=json.loads((OUT/'start.json').read_text());done=json.loads((OUT/'complete.json').read_text());decision=json.loads((OUT/'pilot-decision.json').read_text())
    assert start['source_sha256']==done['source_sha256']==decision['source_sha256']
    for n,d in start['source_sha256'].items():assert sha(RESEARCH/n)==d and sha(OUT/'source'/n)==d
    assert start['gate_freeze_sha256']==sha(ROOT/'results/revision2-development/freeze.json')
    training=[]
    for phase,steps,arms in [('training',100000,list(protocol['arms'])),*([('extension',300000,[done['selected_for_extension']])] if done['selected_for_extension'] else [])]:
        for arm,seed in itertools.product(arms,protocol['pilot_seeds']):
            folder=OUT/phase/f'{arm}-{seed}';meta=json.loads((folder/'complete.json').read_text());model=PPO.load(folder/'policy.zip',device='cpu')
            assert model.num_timesteps==meta['steps']==steps and model.seed==meta['seed']==seed and meta['arm']==arm
            assert meta['training_mode']==protocol['arms'][arm] and meta['policy_sha256']==sha(folder/'policy.zip')
            for n,d in meta['source_sha256'].items():assert sha(RESEARCH/n)==d and sha(folder/'source'/n)==d
            optimizer=sorted({int(v['step'].item()) for v in model.policy.optimizer.state_dict()['state'].values()});assert optimizer==[steps//20]
            with (folder/'normalization.pkl').open('rb') as f:norm=pickle.load(f)
            assert not norm.norm_obs and norm.norm_reward and abs(norm.ret_rms.count-steps)<.001
            if phase=='extension':assert meta['initial_policy_sha256']==sha(OUT/'training'/f'{arm}-{seed}'/'policy.zip')
            monitors=[]
            for p in folder.glob('*.monitor.csv'):
                with p.open() as f:
                    next(f);monitors.extend(csv.DictReader(f))
            count=sum(int(r['l']) for r in monitors);budget=100000 if phase=='training' else 200000
            assert 0<=budget-count<6400
            avg=lambda key:sum(float(r[key])*int(r['l']) for r in monitors)/count
            if arm in ['A','B']:assert all(float(r['episode_mean_bonus'])==0 for r in monitors)
            if arm!='D':assert all(float(r['mu'])==.9 and float(r['stiffness'])==1 and float(r['sensor_noise'])==1 and int(r['sensor_delay'])==0 for r in monitors)
            else:assert all(.6<=float(r['mu'])<=.9 and .65<=float(r['stiffness'])<=1 and 1<=float(r['sensor_noise'])<=2 for r in monitors)
            training.append(dict(phase=phase,arm=arm,seed=seed,steps=steps,completed_episode_steps=count,episodes=len(monitors),execution_fraction=avg('episode_gate_fraction'),mean_relative_bonus=avg('episode_mean_bonus'),mu_range=[min(float(r['mu']) for r in monitors),max(float(r['mu']) for r in monitors)],stiffness_range=[min(float(r['stiffness']) for r in monitors),max(float(r['stiffness']) for r in monitors)],delayed_episode_fraction=mean(int(r['sensor_delay'])==1 for r in monitors),path_capped_episode_fraction=mean(int(r['path_capped'])==1 for r in monitors),wall_s=meta['wall_s']))
    def audit_grid(name,methods):
        folder=OUT/name;complete=json.loads((folder/'complete.json').read_text());assert complete['episodes_sha256']==sha(folder/'episodes.csv')
        rows=typed(read(folder/'episodes.csv'));keys=[(r['seed'],r['speed'],r['path'],r['scenario'],r['method']) for r in rows]
        expected=set(itertools.product(protocol['pilot_seeds'],protocol['speeds'],protocol['paths'],protocol['scenarios'],methods));assert len(rows)==len(set(keys))==len(expected)==complete['episodes'] and set(keys)==expected
        lookup=dict(zip(keys,rows))
        for k,r in lookup.items():
            assert math.isfinite(r['penalized_rmse']) and r['max_rate']<=.3500001 and r['steps']<=r['scheduled_steps']
            if r['survived']:assert r['steps']==r['scheduled_steps']
            if r['scenario']=='latency100' and r['method']!='standalone_full_reference':
                assert r['active_fraction']==0 and r['penalized_rmse']==lookup[k[:4]+('lqr',)]['penalized_rmse']
        return rows
    rows=audit_grid('evaluation',protocol['methods']);assert len(rows)==504
    assert decision['pilot_csv_sha256']==sha(OUT/'evaluation/episodes.csv')
    recomputed=[screening(rows,a) for a in ['B','C','D']]
    assert recomputed==decision['assessments']
    eligible=[x for x in recomputed if x['eligible']];selected=min(eligible,key=lambda x:x['stress_mean'])['arm'] if eligible else None
    assert selected==decision['selected_for_extension']==done['selected_for_extension']
    def subset(method,region=None,seed=None,data=rows):return [r for r in data if r['method']==method and (region is None or r['scenario']==region) and (seed is None or r['seed']==seed)]
    score=lambda rs:mean(r['penalized_rmse'] for r in rs)
    lines=['# Gate-aware / relative-reward pilot results','',
           '**800,000 pilot steps**: four arms × two seeds ×100k. **504 paired development episodes**. Frozen gate and old checkpoints unchanged; final reserved tests and five-seed full training not run.','',
           '| Arm | Training gate | Relative reward | Domain randomization |','|---|---|---|---|',
           '| A | No | No | No |','| B | Yes | No | No |','| C | No | Yes | No |','| D | Yes | Yes | Yes |','',
           'All A–D policies are residual ±0.08-rad policies and are evaluated inside the same frozen performance gate. The standalone full-command reference is a different, frozen1M-step model, never a residual output repurposed as full steering.','',
           '| Region | Method | Survived /12 | Mean penalized RMSE (m) | Gate-active ticks |','|---|---|---:|---:|---:|']
    for region,method in itertools.product(protocol['scenarios'],protocol['methods']):
        rs=subset(method,region);active='—' if method=='standalone_full_reference' else f"{mean(r['active_fraction'] for r in rs):.2%}"
        lines.append(f"| {region} | {method} | {sum(r['survived'] for r in rs)} | {score(rs):.6f} | {active} |")
    lines+=['','## Overall and paired arm comparisons','',
            '| Method | Survived /72 | Mean RMSE score (m) | Change vs LQR | Seed101 change vs A | Seed202 change vs A |','|---|---:|---:|---:|---:|---:|']
    for method in protocol['methods']:
        rs=subset(method);change=score(rs)/score(subset('lqr'))-1
        seed_delta=[score(subset(method,seed=s))/score(subset('A_hybrid',seed=s))-1 for s in protocol['pilot_seeds']]
        lines.append(f"| {method} | {sum(r['survived'] for r in rs)} | {score(rs):.6f} | {change:+.2%} | {seed_delta[0]:+.2%} | {seed_delta[1]:+.2%} |")
    lines+=['','## Training diagnostics','', 'Fractions/bonuses below are weighted by steps in completed episodes; unfinished tails are excluded. For ungated A/C, execution fraction1 means residual pass-through, not supervisor acceptance.','',
            '| Arm | Seed | Completed episodes | Training execution fraction | Mean relative bonus | Friction range | Stiffness scale range | Delayed episodes |','|---|---:|---:|---:|---|---|---:|']
    for r in training:
        if r['phase']!='training':continue
        lines.append(f"| {r['arm']} | {r['seed']} | {r['episodes']} | {r['execution_fraction']:.2%} | {r['mean_relative_bonus']:+.7f} | {r['mu_range']} | {r['stiffness_range']} | {r['delayed_episode_fraction']:.2%} |")
    lines+=['','## Predeclared extension decision','', '| Arm | Overall mean RMSE | Stress mean RMSE | Eligible | Failed checks |','|---|---:|---:|---|---|']
    for r in recomputed:lines.append(f"| {r['arm']} | {r['mean_rmse']:.6f} | {r['stress_mean']:.6f} | {r['eligible']} | {', '.join(k for k,v in r['checks'].items() if not v) or 'none'} |")
    lines+=['',f"Selected for300k extension: **{selected or 'none'}**.",
            '', 'The100k extension screen requires ≥1% overall improvement over A with both seed means better, ≥1% LQR improvement in at least2/3 stress regions, both seed stress means better than LQR, no active region >1% worse than LQR, nominal/survival preservation and exact severe-delay fallback. These are predeclared development spending criteria, not statistical significance.']
    if selected:
        extended=audit_grid('extension-evaluation',['lqr','standalone_full_reference','legacy_gated_reference',selected+'_hybrid'])
        assessment=json.loads((OUT/'extension-decision.json').read_text())['assessment']
        assert assessment==screening(extended+[r for r in rows if r['method']=='A_hybrid'],selected,.05,False)
        lines+=['',f'Only arm{selected} was continued from its saved100k checkpoints to300k at both seeds (400k additional steps). Full-budget review checks passed: **{assessment["eligible"]}**. Full training remains unapproved.','', '| Region | Extended hybrid RMSE | Paired LQR RMSE | Change |','|---|---:|---:|---:|']
        for region in protocol['scenarios']:
            hybrid=score(subset(selected+'_hybrid',region,data=extended));baseline=score(subset('lqr',region,data=extended));lines.append(f'| {region} | {hybrid:.6f} | {baseline:.6f} | {hybrid/baseline-1:+.2%} |')
    else:lines+=['', 'No arm met all promising-pilot criteria. No300k extension or full-budget training was launched; no criteria were relaxed after inspecting results.']
    lines+=['','## Reserved allocation correction','',
            'No reserved evaluation was run. The original proposed base8100000 overlaps36 development IDs under the shared seed-index formula (pilot seed202 versus future seed2). Before any reserved use, `reserved_split.json` replaces that unused allocation with base91000000 and records the explicit disjoint72 development/180 future reserved IDs. Pilot/controller sources and actual development data are unchanged.','',
            '## Interpretation and limits','',
            'B−A isolates training with the frozen gate; C−A isolates the added relative-reward term. D is a combined package including gate, relative reward, domain randomization and randomized-course feasibility screening. A D improvement cannot be attributed to domain randomization alone; this is not a complete factorial ablation.',
            '', 'Relative reward is training-only privileged simulation: two100ms branches start at the same true state/plant parameters, differ only in the first10ms executed command, then use identical true-state nominal LQR continuation. It consumes no sensor RNG, does not alter the real transition and provides exactly zero bonus when the executed command equals LQR. It is a surrogate counterfactual, not measured future benefit or an actor input.',
            '', 'Training is synchronous. The sampled action is transformed by the actual gate before the transition, so PPO receives reward for that action’s gated execution. No newly sampled action is assigned the reward of an older queued action. Deployment service-delay experiments remain a separate frozen-policy test; only sensor delay is randomized during training. The actor keeps the same9 observations and does not observe gate memory or hidden friction/stiffness, so partial observability remains.',
            '', 'Only two short-run training seeds, known geometries and development noise are used. Old full-command and residual references have different seeds and1M budgets. Do not interpret their comparison as an equal-budget architecture test or infer full-command capability from residual results. Failure-penalized scores include a2.5m unexecuted-tail fill; failed episodes remain in denominators. No native transfer, real-time, stability, convergence or real-vehicle safety claim is made.']
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')
    (OUT/'verification.json').write_text(json.dumps(dict(verified=True,reserved_noise_base=reserved['reserved_noise_base'],reserved_ids_disjoint=True,pilot_steps=800000,pilot_episodes=504,training_diagnostics=training,selected_for_extension=selected,extension_additional_steps=400000 if selected else 0,full_training_user_approved=False,reserved_evaluated=False),indent=2)+'\n')
    print(f'Verified8 equal-budget pilots and504 development episodes; extension={selected}')
if __name__=='__main__':main()
