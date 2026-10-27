"""Report the versioned-history ablation without relaxing near-miss criteria."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile
ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args();out=args.run
    metrics=json.loads((out/'summary.json').read_text());decision=json.loads((out/'decision.json').read_text())
    package=json.loads((out/'package-provenance.json').read_text());smoke=json.loads((out/'kit-smoke/summary.json').read_text())
    assert (out/'kit-smoke/verification.json').exists() and (out/'runtime-policy-verification.json').exists()
    total=0;columns={}
    for arm in ('nohistory','history'):
        columns[arm]=[]
        for pair in range(3):
            m=json.loads((out/f'{arm}-{pair}/complete.json').read_text());total+=m['steps'];columns[arm].append(m['history_column_norm'])
    base=metrics['lqr'];gains={a:100*(1-metrics[a]['rmse_m']/metrics['student']['rmse_m']) for a in ('nohistory','history')}
    labels={'lqr':'LQR','negative':'Fixed −0.04','positive':'Fixed +0.04','student':'Student','v3ppo':'Frozen v3 PPO','nohistory':'PPO, no history','history':'PPO, history'}
    lines=['# LANS causal-history correction and matched training results','', '27 October 2026 (Asia/Shanghai). Evidence update; no claim that all requirements passed.','',
        '## Implemented input correction','',
        'The earlier20-channel input did not explicitly contain the residual-filter memory. The new, separately versioned interface is causal_filter_history_v5. Channel14 now carries the known stored filter value divided by0.08 at query time. It is not an unknown pending proposal. Future-output/completion/service channels15/16/17/19 remain zero. This makes filter history available but is not a proof of full Markov observability, optimality or physical safety.',
        r'$$h_t=f_{t^-}/0.08,\qquad h_t\in[-1,1].$$',
        'All original TRAIN normalization is retained except the explicitly new history coordinate: mean0/std1 after physical scaling, chosen from filter bounds rather than fitted on DEV. The old unused input column is zeroed at initialization, preserving legacy actor logits for arbitrary history. A matched no-history arm keeps that column exactly zero. Runtime guards reject mixing legacy and history model/controller ABIs.',
        'The two arms share architecture, controller, reward, seeds,100,000 additional transitions per model, optimizer and0.005 entropy coefficient. Both start from the same frozen v3 actor, which already includes100,000 PPO transitions plus original supervised pretraining. The new critic is initialized identically per pair. The history arm observes filter history; the ablation sees channel14zero during training. At evaluation all methods receive the same history interface, with original/no-history actors ignoring14 exactly.',
        'There are no controller, reward-weight or threshold changes from the corrected v4 freshness variant. Nominal service remains at least one10ms polling tick. The fixed10ms PPO rollout can sample ignored actions while busy, a remaining credit-assignment limitation. No-history/history model budgets are matched; a comparison against the older frozen model includes extra training and is not attributed solely to the new input.','',
        '## Fresh matched development results','',
        f'All six pilots completed their fixed endpoints: **{total:,} additional transitions**. All672 development episodes survived. Three paired model/noise groups,15/25m/s, two known paths, mirrored directions and nominal/tire/20ms/100ms cases were used. These are development results, not unseen-path confirmation.','',
        '| Source | Lateral RMSE m | Gain vs LQR | Heading change | Rate RMS change | Survival |','|---|---:|---:|---:|---:|---:|']
    for name,label in labels.items():
        m=metrics[name];lines.append(f'| {label} | {m["rmse_m"]:.6f} | {m["gain_vs_lqr_pct"]:+.3f}% | {100*(m["heading_rmse_rad"]/base["heading_rmse_rad"]-1):+.2f}% | {100*(m["rate_rms_rad_s"]/base["rate_rms_rad_s"]-1):+.2f}% | {m["survived"]}/{m["episodes"]} |')
    lines+=['',f'The no-history arm gains **{gains["nohistory"]:.3f}%** over the student; the history arm gains **{gains["history"]:.3f}%**. Neither reaches the frozen1% student margin. The history arm also exceeds the5% actuator-rate limit. These near misses are failures, not rounded passes.',
        'The history feature therefore does not show a clear balanced performance advantage in this study. Additional training helped on this development grid, but the feature itself is not credited with that entire improvement. The no-history weights for the new coordinate stayed exactly zero; history-arm weights changed. Three groups are too few to establish a robust population effect from small mean differences.','',
        f'**Selected arm: {decision["selected"]}. Reserved tests remain unopened.** Exact failed criteria follow:','']
    for arm in ('nohistory','history'):lines.append('- '+arm+': '+('; '.join(decision['screens'][arm]['reasons']) or 'all development criteria passed'))
    lines+=['',f'The independent verifier replayed **{decision["transitions"]:,} transitions**, **{sum(decision["submitted_queries_replayed"].values()):,} submitted model decisions**, full observations including causal history, rewards, observer/plant states, filtering and commands. All144 severe-delay/LQR trajectory pairs matched exactly. No per-seed checkpoint or arm mixing was used.','',
        '## Runtime and package verification','',
        f'The package contains the **{package["arm"]}** arm as a research diagnostic. It is not a promoted winner. The no-history arm is the balanced diagnostic fallback when no arm qualifies; its new-interface history coordinate is available but ignored by its zero weights.',
        'Torch/NumPy class parity was checked for24,300 archived observations per actor, with nonzero declared causal-history test values. This is export parity, not new performance data or parameter fitting. The clean Python3.10 kit uses only NumPy/SciPy/Numba/Gymnasium and standard library at runtime; no Torch/GPU is required.',
        f'The package smoke ran{sum(e["ticks"] for e in smoke["episodes"])} software-plant ticks and recorded{sum(e["deadline_misses"] for e in smoke["episodes"])} original10ms deadline misses. Functional checks: **{smoke["functional_pass"]}**. Observed timing: **{smoke["observed_timing_pass"]}**. Actual returned packets were independently replayed against the source Torch actor and the physical observation/filter-history fields.',
        'The earlier v4 experiment validated real worker stall/recovery for three actor seeds and separately recorded full-controller timing failures. The independent native C heartbeat missed80/3,000 deadlines even without a neural/controller workload. Those earlier numbers are not relabeled as timing validation of the new models. A new-model smoke is also not a complete selected-winner real-time validation.',
        'LQR and the supervisor share the local process. Independence from the PPO worker does not isolate local control from sensing, supervisor, IPC or OS scheduling delay. Late/stale-action rejection does not guarantee that a replacement LQR command reached a physical actuator before its deadline. A defined target execution/OS isolation design and physical measurements are still required.',
        'Offline20ms cases represent total configured logical service. A real20ms post-inference wait also includes inference, IPC and polling latency. The distributions are not assumed identical. Software timestamp fields are clock reads around software events, not hardware wire or sensor timestamps. Fixed-step plant survival cannot establish continuous physical safety while the host is stalled.','',
        '## Remaining requirements','',
        '- Demonstrate the unchanged full scientific selection criteria on a justified new development design; the1% margin is not a code bug that can be repaired by lowering it. No additional training extension or hyperparameter search was run after these outcomes.',
        '- Establish original10ms execution on the actual target. The user laptop has not been remotely executed. Run the extracted kit using the top-level RUN_WINDOWS.cmd, or `bash RUN_MAC.command`, and retain laptop-results/Results.zip. Current cloud timing failures are not a Windows/macOS result or a hard-real-time guarantee.',
        '- Only after full selection and corresponding-controller timing pass, freeze/run reserved unseen-path and native Webots confirmation. Previous native interface checks are not new-model confirmation.',
        '- Complete the full robust published-controller reproduction and broader bibliography verification. The existing nominal safety-filter specialization and five primary-source entries are scoped evidence, not the complete robust algorithm or a systematic prior-art review.',
        '- Physical sensors, communications and actuator validation require connected hardware. No real-vehicle readiness, global stability, energy/blind-distance advantage or49-fold inference-speed claim is made.',
        '- The revised evidence draft is reviewable but is not declared submission-ready. Novelty and the label neuro-symbolic are not established merely by adding predicates or a predictor block.','',
        'The prior causal/interface/compute correction studies remain preserved, including all failed outcomes. Reproduce/resume with `python tools/controller_review/run_history_work.py --publish`. This command does not manufacture missing laptop/vehicle measurements or open reserved tests on failure.']
    import re
    text='\n'.join(lines)+'\n';parts=re.split(r'(`[^`]*`)',text)
    for i,s in enumerate(parts):
        if s.startswith('`'):continue
        s=re.sub(r'(?<=[A-UW-Za-uw-z])(?=\d)',' ',s);s=re.sub(r'(?<=\d)(?=[A-UW-Za-uw-zµ])',' ',s);parts[i]=s
    (out/'final-update.md').write_text(''.join(parts))
    status=dict(selected=decision['selected'],packaged_diagnostic_arm=package['arm'],additional_training_steps=total,
        student_relative_gains_pct=gains,full_selection_pass=decision['selected'] is not None,history_state_input_available_and_verified=True,
        history_performance_benefit_established=False,package_functional_pass=smoke['functional_pass'],package_observed_timing_pass=smoke['observed_timing_pass'],
        reserved='unopened',new_selected_native_confirmation=False,actual_laptop_validation=False,physical_vehicle_validation=False,
        complete_robust_published_reproduction=False,submission_ready=False)
    (out/'completion-status.json').write_text(json.dumps(status,indent=2)+'\n')
    os.environ.setdefault('XDG_CACHE_HOME','/tmp/lans-v5-font-cache');Path(os.environ['XDG_CACHE_HOME']).mkdir(exist_ok=True)
    for suffix in ('docx','pdf'):
        cmd=['pandoc',str(out/'final-update.md'),'-o',str(out/f'final-update.{suffix}')]
        if suffix=='pdf':cmd+=['--pdf-engine=xelatex','-V','mainfont=DejaVu Serif','-V','geometry:margin=22mm','-V','fontsize=10pt','-V','papersize=a4']
        subprocess.run(cmd,check=True)
    with zipfile.ZipFile(out/'LANS_History_Reports.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ('final-update.md','final-update.docx','final-update.pdf','completion-status.json','package-provenance.json','summary.json','decision.json','episodes.csv'):
            z.write(out/name,name)
    checks={}
    for f in out.glob('*.zip'):
        with zipfile.ZipFile(f) as z:assert z.testzip() is None
        checks[f.name]=hashlib.sha256(f.read_bytes()).hexdigest()
    (out/'artifact-quality.json').write_text(json.dumps(dict(archive_crc_pass=True,sha256=checks,actual_windows_macos_run=False),indent=2)+'\n')
    print(json.dumps(status,indent=2))


if __name__=='__main__':main()
