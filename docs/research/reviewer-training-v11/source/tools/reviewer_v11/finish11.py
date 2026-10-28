"""Training evidence report: retain outcomes regardless of the 20% target."""
import boot11
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();out=a.run;load=lambda n:json.loads((out/n).read_text());d=load('decision.json');s=load('summary.json');base=s['lqr'];training=[load(f'training-{i}/complete.json') for i in range(3)]
    for name,digest in load('manifest.json')['hashes'].items():assert hashlib.sha256((boot11.ROOT/name).read_bytes()).hexdigest()==digest,name
    raw=[f for group in ('training-0','training-1','training-2','actors','runtime-actors','pair-0','pair-1','pair-2','timing') for f in (out/group).rglob('*') if f.is_file() and 'source' not in f.relative_to(out/group).parts and f.suffix in ('.npz','.json','.csv','.zip','.pkl')]
    raw += [out/n for n in ('manifest.json','decision.json','summary.json','episodes.csv','tests-passed.json')]
    hashes={str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest() for f in raw};seal=out/'evidence-hashes.json'
    if seal.exists():assert hashes==load('evidence-hashes.json')['sha256'],'Verified evidence changed'
    else:seal.write_text(json.dumps(dict(sha256=hashes,scope='Continued-training initialization/endpoints/optimizer/reward statistics and independently replayed full development raw data; derived reports separate'),indent=2)+'\n')
    rows=['# LANS: actual PPO training after the audit fixes','',
      '27 October2026. The user explicitly requested training after the failed causal-planner headroom diagnostic. This new finite protocol proceeds despite that heuristic failure; historical outcomes and criteria remain unchanged. The20% target is measured, not guaranteed.','',
      '## What was actually trained','',
      'Three new RNG seeds continue the corresponding previous causal-history PPO checkpoints for exactly100,000 additional environment steps each:300,000 NEW steps total. Actor, critic, Adam optimizer and reward-normalization statistics are retained; source preservation is contract-tested and initial checkpoints/normalizers are saved. The rollout buffer/environment/RNG are fresh. Original supervised and previous PPO training budgets are additional. Only the three final endpoints are compared: no best-checkpoint cherry-picking, per-seed mixing or post-result extensions.',
      'Training uses the corrected v10 terminal next-observation interface, strict packet/identity checks and nominal RK4 predictor with average actual actuator-rate cost. Source/model input dependencies are pinned to the prior immutable evidence. The causal20-channel input ABI, physical reward, submitted-request actor credit, fixed-step GAE, all-transition critic,50ms stale cutoff, residual bound0.08rad, filter0.3s, cap0.25, recovery/ramp/margin and actuator limits remain unchanged. No future response/service information is provided to the actor.',
      'The training distribution covers15/20/25m/s, two known paths, exactmirrors and nominal/tire/20/40/100ms conditions. Its noise namespace is new and separate from the fresh development namespace. Severe-delay transitions can have zero policy authority; they are retained rather than removed to inflate tracking gains. No reserved path is opened.','',
      '| Pair | New RNG seed | Additional steps | Submitted requests | Active assistance ticks | Wall seconds |','|---|---:|---:|---:|---:|---:|']
    for t in training:rows.append(f'| {t["pair"]} | {t["seed"]} | {t["additional_steps"]} | {t["submitted"]} | {t["active"]} | {t["wall_seconds"]:.1f} |')
    rows+=['','## Fresh matched evaluation','',
      f'The predeclared full development grid has {d["episodes"]} episodes:15/25m/s x2knownpaths x2mirrors x5scenarios x7sources x3actor/noise groups. Every source uses the same corrected supervisor, sensing, actuator limits and matched exogenous conditions. Student and oldPPO weights remain frozen; the newPPO is the continued endpoint. The causal nominal planner and both fixed corrections are nonlearned controls. A full robust published vehicle baseline/MPC is not included, so superiority over all published controllers cannot be claimed.',
      f'Independent single-observation inference and full input/history/compensation/packet/recovery/physical/reward replay verify {d["transitions"]:,} transitions and {d["submitted_actor_decisions"]:,} neural decisions. Planner proposals are independently regenerated from available information; {d["exact_100ms_lqr_pairs"]} severe-delay/LQR trajectory pairs match exactly. All input source/model hashes and exports are checked.','',
      '| Source | Tracking gain vs LQR | Heading change | Steering-rate RMS change | Survival |','|---|---:|---:|---:|---:|']
    for name,m in s.items():rows.append(f'| {name} | {m["gain_vs_lqr_pct"]:+.3f}% | {100*(m["heading_rmse_rad"]/base["heading_rmse_rad"]-1):+.3f}% | {100*(m["rate_rms_rad_s"]/base["rate_rms_rad_s"]-1):+.3f}% | {m["survived"]}/{m["episodes"]} |')
    rows+=['', '## New PPO contribution and20% target','']
    for ref,gain in d['ppo_gain_vs_comparators_pct'].items():rows.append(f'- NewPPO tracking gain vs {ref}: **{gain:+.4f}%**.')
    rows+=['',f'20% development screen: **{d["twenty_percent_development_pass"]}**. Failed checks: '+('; '.join(d['reasons']) or 'none')+'.',
      'The screen requires at least20% lower mean penalized episode tracking RMSE than EVERY listed comparator, positive paired gain in all three groups, no survival loss, nominal tracking no more than2% worse than LQR and overall heading/actuator-rate RMS no more than5% higher. Exact ratio comparisons avoid floating-point misclassification at the20% boundary. Aggregate metrics do not guarantee every individual speed/path cell improves.',
      'The matched old/new PPO comparison measures the result of additional training under the corrected environment. It does not isolate the individual causal effects of terminal-observation repair, predictor integration, continued optimizer/reward statistics or RNG changes. Prior0.379%/1.488% diagnostic values came from a narrower grid with other noise; do not compare those aggregates as if only training changed.',
      'Limited authority, sparse accepted proposals and a strong LQR/student/planner remain structural constraints. A failed target is not converted into a pass by deleting delayed conditions, weakening baselines, extending training until a score crosses a line or choosing different best seeds. No universal impossibility claim follows from this finite study.',
      '', '## Timing, confirmation and scope','',
      'Winner-specific original-deadline timing is conditional on the20% selection screen. If the screen fails, no current-model timing success is claimed. Previous v9 zero-miss timing and the v10 one-miss smoke are historical experiments, not certification of these new actors. All reserved/native Webots confirmation, actual laptop execution and physical sensor/communication/actuator validation remain separate evidence requirements. No deployment, global stability, universal novelty, energy or49-fold speedup claim is made.']
    if (out/'timing/summary.json').exists():rows+=['',str(load('timing/summary.json')['profiles'])]
    rows+=['','## Resume','', '```bash','python tools/reviewer_v11/run11.py --publish','```','',
      'The command checks provenance/contracts, continues the three finite runs, exports actors, executes the fixed matched matrix, independently replays raw data, seals evidence and builds Word/PDF reports. Completed and partial outputs are preserved. Exit2 means the20% empirical requirement remains unmet. No further training starts automatically.']
    (out/'README.md').write_text('\n\n'.join(rows).replace('|\n\n|','|\n|')+'\n')
    for suffix in ('docx','pdf'):
        cmd=['pandoc',str(out/'README.md'),'-o',str(out/f'training-update.{suffix}')]
        if suffix=='pdf':cmd+=['--pdf-engine=xelatex','-V','mainfont=DejaVu Serif','-V','geometry:margin=22mm','-V','fontsize=10pt']
        subprocess.run(cmd,check=True)
    with zipfile.ZipFile(out/'LANS_New_PPO_Training_Reports.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ('README.md','training-update.docx','training-update.pdf','summary.json','decision.json','manifest.json','evidence-hashes.json','tests-passed.json','tests.log','actors/manifest.json'):z.write(out/name,name)
    with zipfile.ZipFile(out/'LANS_New_PPO_Training_Reports.zip') as z:assert z.testzip() is None
    print(json.dumps(d,indent=2))
if __name__=='__main__':main()
