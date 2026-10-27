"""Evidence report: preserve failures, expose assumptions and external blockers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[2]
def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();out=a.run
    load=lambda name:json.loads((out/name).read_text())
    decision=load('decision.json');metrics=load('summary.json');timing=load('timing/summary.json');verification=load('timing/verification.json')
    robust=load('robust-scalar-contract/verification.json');diagnosis=load('failure-diagnosis.json');bib=load('bibliography-audit.json')
    assert decision['source_and_model_hashes_verified'] and verification['original_deadlines_verified'] and robust['terminal_invariance_verified']
    base=metrics['lqr'];labels={'lqr':'LQR','negative':'Fixed −0.04','positive':'Fixed +0.04','student':'Same-supervisor student','v3ppo':'Frozen v3 PPO','all_actions':'Additional PPO: all actions','submitted_only':'Additional PPO: submitted only'}
    total=sum(load(f'{arm}-{pair}/complete.json')['steps'] for arm in ('all_actions','submitted_only') for pair in range(3))
    gains={arm:100*(1-metrics[arm]['rmse_m']/metrics['student']['rmse_m']) for arm in ('all_actions','submitted_only')}
    ready=decision['selected'] is not None and timing['observed_timing_pass']
    lines=['# LANS reviewer-issue investigation: submitted-action credit and timing','',
        '27 October 2026. Finite development evidence; no claim that every requested requirement passed.','',
        '## Diagnosis and intervention','',
        'Scope remains the original residual LANS architecture: LQR baseline plus a bounded categorical PPO correction approved by the predictive freshness/cost supervisor. It is not full-command PPO/LQR switching. A 1,000ms delayed PPO worker with fresh local sensing is not 1,000ms delayed LQR feedback. The actor chooses one of −0.08, −0.04, 0, +0.04, +0.08 radians; measured neural inference, injected post-inference service wait, packet age and local-loop response time are distinct quantities.',
        'The preceding 1,500-tick smoke had 274 original-deadline misses. Of these, '+str(sum(r['already_late_at_release'] for r in diagnosis['timing'].values()))+' were already at least 10 ms late on release. Both wall-processing and thread-CPU spikes were recorded. These measurements identify multiple contributions; they do not establish a unique OS/cgroup cause or excuse any miss. Historical unrecorded throttling cannot be assigned to an individual episode.',
        'Fixed-tick PPO previously sampled actions even when its worker queue was busy. Recorded delay-100ms development cases discarded about 90% of samples; delay-20ms cases discarded about 50%. Such actions do not affect the plant but still contribute actor surrogate, entropy and KL terms. This motivates a variance/credit-assignment ablation, not a claim that the original expected policy gradient was necessarily biased.',
        'A separately frozen two-arm study starts both arms from the same paired v5 no-history endpoint, including critic and optimizer. Each arm receives exactly 100,000 additional transitions for each of three seeds, with fresh training and development noise namespaces. The all-actions arm retains every actor sample; submitted-only masks actor loss, advantage normalization, entropy and KL to actual submitted requests. Fixed-tick GAE, all-transition critic loss, deployed controller, reward, actuator limits and all acceptance margins are unchanged. Environment budgets match; effective actor sample counts differ and are reported below.',
        r'$$L_\pi=-\frac{\sum_i m_i\min(r_i A_i,\operatorname{clip}(r_i,1-\epsilon,1+\epsilon)A_i)}{\sum_i m_i},\quad m_i=\mathbf{1}\{\text{request submitted}\}.$$',
        'Actor/entropy/KL means and advantage normalization use valid samples. This also changes actor-loss scaling relative to the unchanged all-transition critic when the valid fraction is below one, so the intervention is not an isolated proof about variance alone. In a minibatch with no valid requests, only the critic is updated. The all-actions control sets every mask to one.',
        r'$$r_t=-\left(\frac{e_y}{0.5}\right)^2-0.2\left(\frac{e_\varphi}{0.1}\right)^2-0.2\left(\frac{\dot\delta_a}{0.35}\right)^2-0.005\left(\frac{\delta_{\rm cmd}}{0.5}\right)^2-10\,\mathbf{1}\{\text{failure}\}.$$',
        'The input remains causal_filter_history_v5. Coordinate 14 is known filter history and its actor weights remain exactly zero in both arms; future-completion/output/service coordinates remain zero. This is not another history-feature search. Both arms inherit v3 100k and v5 100k PPO training plus original supervised pretraining. Additional optimization cannot be attributed solely to masking.',
        'Four implementation contracts passed: all-valid update is bitwise identical to reference PPO, no-valid sample preserves actor parameters while updating critic, discarded advantages/log probabilities do not affect the actor update, and different busy-worker actions produce identical physical transitions. The generated surrogate uses checked edits to SB3 2.0.0 training code; no reserved data were used.','',
        '## Frozen fresh development comparison','',f'Completed **{total:,} additional training transitions** and **{decision["episodes"]} episodes**. These are known-path development conditions, not unseen-path confirmation.','',
        '| Controller | Lateral RMSE m | Gain vs LQR | Heading change | Actuator-rate change | Survival |','|---|---:|---:|---:|---:|---:|']
    for source,label in labels.items():
        m=metrics[source];lines.append(f'| {label} | {m["rmse_m"]:.6f} | {m["gain_vs_lqr_pct"]:+.3f}% | {100*(m["heading_rmse_rad"]/base["heading_rmse_rad"]-1):+.2f}% | {100*(m["rate_rms_rad_s"]/base["rate_rms_rad_s"]-1):+.2f}% | {m["survived"]}/{m["episodes"]} |')
    lines+=['','| Arm / pair | Environment transitions | Submitted actions | Actor credit samples |','|---|---:|---:|---:|']
    for arm in ('all_actions','submitted_only'):
        for pair in range(3):
            m=load(f'{arm}-{pair}/complete.json');lines.append(f'| {arm} / {pair} | {m["steps"]} | {m["submitted"]} | {m["actor_credit_samples"]} |')
    lines+=['',f'Student-relative tracking gains: all-actions **{gains["all_actions"]:.3f}%**; submitted-only **{gains["submitted_only"]:.3f}%**. The original requirement is at least 1%, with the complete balanced/fixed-baseline/per-pair screen also required. Selected arm: **{decision["selected"]}**.','']
    for arm in ('all_actions','submitted_only'):
        s=decision['screens'][arm];lines.append('- '+arm+': '+('; '.join(s['reasons']) or 'all development criteria passed')+'. Three paired student gains: '+', '.join(f'{v:.3f}%' for v in s['paired_group_gains_vs_student_pct'])+'.')
    lines+=['',f'Independent replay verified **{decision["transitions"]:,} transitions**, **{sum(decision["submitted_queries_replayed"].values()):,} submitted actor decisions**, every observation coordinate, actual rewards, observer/plant states, gate/filter decisions and commands. All {decision["severe_exact_pairs"]} 100ms-delay/LQR trajectory pairs matched exactly. No per-seed arm mixing or endpoint extension was used.','',
        '## Original 10 ms timing','',
        f'The separate serialized campaign recorded **{timing["deadline_misses"]}/{timing["ticks"]} controller deadline misses**, with functional fallback **{timing["functional_pass"]}** and observed strict timing **{timing["observed_timing_pass"]}**. The native C heartbeat recorded **{sum(r["deadline_misses"] for r in timing["heartbeat"])}/{sum(r["ticks"] for r in timing["heartbeat"])} misses**. All three actor seeds and five actual worker cases were tested, with full warmup, pinned control/helper CPUs, lower helper priority and no concurrent research jobs. Source/model hashes, original unshifted 10ms targets, all causal gate observations, packet actions, fault injection and software-plant trajectories were independently replayed.',
        'Timing model provenance is in timing/protocol.json. If no new controller qualifies, this remains a platform diagnostic with the unchanged v5 actor, not selected-controller validation. Scheduler behavior remains a platform requirement; lower average inference time does not establish a 100Hz response guarantee. Zero finite misses, if observed, would also not constitute WCET certification.',
        'The local LQR, observer, IPC and supervisor still share one process. Independence from the PPO worker is not independence from local scheduling or computation stalls. Deadline fallback is recorded at a software commit marker, not at an actuator. The fixed-step plant pauses while the host stalls; survival does not establish physical continuous-time safety. No deadline is shifted, skipped or forgiven.','',
        'The portable entry point now explicitly sets one BLAS/OpenMP thread before numerical imports. Two subprocess checks with conflicting inherited thread settings verify that policy and also establish that the previous common boot already enforced the BLAS limit indirectly. This is import-order hardening, not evidence that excess BLAS threads caused the previous 274 misses or that a new speedup was achieved.','',
        '## Robust published-filter contract and bibliography','',
        f'A separate implementation of the uniform-error specialization of Wabersich/Zeilinger arXiv:1812.05506v4 Eq.(6), Eq.(9–10), Algorithm 2 was completed for an explicitly declared scalar bounded-error/full-state plant. All **{robust["transitions"]} transitions** satisfy declared state/input bounds, and **{robust["independent_lp_projections"]} inputs** match independently solved LP optimal-input intervals. Full-horizon, shrinking-horizon and terminal branches are exercised; uncertified initial states are rejected.',
        r'$$x_{k+1}=0.8x_k+0.2u_k+w_k,\quad |w_k|\le0.01,\quad |x_k|\le1,\quad |u_k|\le0.5.$$',
        'The terminal interval is |x|≤0.2 with u=−x. Incremental V=e² contracts by rho=0.36 under pi=v−e; tightening epsilon=0.06 dominates the declared normalized disturbance bounds. The exact assumptions, solver tolerances and traces are preserved. This is an independent scalar algorithm specialization, not the authors’ code/examples or a matched nonlinear LANS vehicle reproduction. It does not supply a validated vehicle error/confidence set, noisy-state certificate or vehicle terminal safe set.',
        f'All **{len(bib["entries"])} original bibliography entries** were structurally reviewed. The five uploaded primary papers support five version-specific references already preserved. Entries 18/26 conflict in venue metadata and need deduplication/correction using the supplied Kalaria version; entries 23/24 duplicate a title with different author attribution. Several ECU/GPU/WCET assertions cite sources that do not directly substantiate those exact claims. Full primary-source verification of every remaining entry is pending; unsupported claims are not retained as established facts.','',
        '## Completion boundaries','',
        f'Combined development-selection and observed-timing gate: **{ready}**. Reserved data remain unopened unless both gates pass and a corresponding confirmation protocol is frozen. No current native Webots or unseen-path result is manufactured. Prior native interface checks are not confirmation of these new policies.',
        'Still required: full scientific selection if failed; target-specific original10ms timing; actual Windows/macOS laptop execution; gated reserved/native confirmation; matched robust vehicle comparator and remaining primary-source citations; connected physical sensor/communication/actuator measurements for vehicle readiness. The available cloud has no connection to the user laptop or a vehicle, so those measurements cannot be honestly marked complete.',
        'The report is an evidence draft, not a submission-ready superiority/safety paper. Claims of global convergence, neuro-symbolic novelty, vehicle readiness, energy advantage, total blind-distance improvement or 49-fold speedup remain unsupported. Repeated development campaigns and cumulative training budget must be disclosed; these finite means are not a population guarantee.',
        'Resume software work with `python tools/controller_review/run_credit_work.py --publish`. Frozen failures remain preserved; the command does not lower thresholds or manufacture hardware results.']
    (out/'final-update.md').write_text('\n'.join(lines)+'\n')
    status=dict(additional_training_steps=total,episodes=decision['episodes'],selected=decision['selected'],student_relative_gain_pct=gains,
        full_selection_pass=decision['selected'] is not None,strict_timing_pass=timing['observed_timing_pass'],timing_misses=timing['deadline_misses'],timing_ticks=timing['ticks'],
        functional_fallback_pass=timing['functional_pass'],reserved_unopened=True,actual_laptop_run=False,physical_vehicle_validation=False,
        robust_scalar_algorithm_contract=True,matched_robust_vehicle_reproduction=False,all32_references_structurally_reviewed=True,all32_primary_verified=False,submission_ready=False)
    (out/'completion-status.json').write_text(json.dumps(status,indent=2)+'\n')
    os.environ.setdefault('XDG_CACHE_HOME','/tmp/lans-v6-font-cache');Path(os.environ['XDG_CACHE_HOME']).mkdir(exist_ok=True)
    for suffix in ('docx','pdf'):
        cmd=['pandoc',str(out/'final-update.md'),'-o',str(out/f'final-update.{suffix}')]
        if suffix=='pdf':cmd+=['--pdf-engine=xelatex','-V','mainfont=DejaVu Serif','-V','geometry:margin=22mm','-V','fontsize=10pt']
        subprocess.run(cmd,check=True)
    with zipfile.ZipFile(out/'LANS_Credit_Reports.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ('final-update.md','final-update.docx','final-update.pdf','completion-status.json','summary.json','decision.json','episodes.csv','failure-diagnosis.json','bibliography-audit.md','posthoc-analysis.md','posthoc-analysis.json'):
            z.write(out/name,name)
    with zipfile.ZipFile(out/'LANS_Credit_Reports.zip') as z:assert z.testzip() is None
    (out/'artifact-quality.json').write_text(json.dumps(dict(archive_crc_pass=True,report_zip_sha256=hashlib.sha256((out/'LANS_Credit_Reports.zip').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(status,indent=2))

if __name__=='__main__':main()
