"""Build evidence-linked follow-up report without changing frozen studies."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args();out=args.run
    metrics=json.loads((out/'summary.json').read_text());decision=json.loads((out/'decision.json').read_text())
    actors=json.loads((out/'actor-verification.json').read_text());base=metrics['lqr/none']
    episodes=list(csv.DictReader((out/'episodes.csv').open()))
    timing={name:json.loads((out/f'timing/{name}/summary.json').read_text()) for name in ('sleep','absolute')}
    for name in timing:assert json.loads((out/f'timing/{name}/verification.json').read_text())['raw_timestamp_and_model_replay_checks_pass']
    smoke=json.loads((out/'kit-smoke/summary.json').read_text());assert (out/'kit-smoke/verification.json').exists()
    lines=['# LANS reviewer follow-up: verified development evidence','',
        '27 October2026 (Asia/Shanghai). Architecture: fresh-state LQR baseline plus causal PPO residual, freshness rejection, and supervisory authority. This is not full-command PPO/LQR switching. Prior failed experiments remain unchanged in reviewer-causal-v1. This document is a research update, not a declaration of submission or vehicle readiness.','',
        '## What was completed','',
        f'- Frozen864-episode follow-up:3 paired PPO/student seeds,20m/s,2development paths,exact left/right mirrors,4conditions,18methods. All{sum(v["survived"] for v in metrics.values())}/864 episodes survived. Fresh development noise; no new training or outcome-driven tuning.',
        f'- Independently recomputed raw metrics, causal low-pass recurrence, actuator bounds, fusion and{decision["severe_exact_pairs"]} exact severe-delay/LQR trajectory pairs.',
        f'- Replayed{actors["submitted_queries"]["ppo"]} PPO and{actors["submitted_queries"]["student"]} submitted queries from recorded observations; zero action disagreements. All frozen input hashes and removed future/oracle channels checked.',
        '- Added same-profile student and both fixed±0.04rad controls to separate PPO learning from supervisory gain/filter effects.',
        '- Implemented a disclosed nominal specialization of Wabersich–Zeilinger Eq5/Algorithm1; complete solver failures and fallback counts retained.',
        '- Ran predeclared randomized timer A/B with original10ms deadlines, actual PPO worker, observer/LQR, isolated generated worker contention and lower worker priorities. Independently replayed raw plant/observer/model/timestamps.',
        '- Packaged full-controller Python3.10 laptop SIL kit with portable NumPy PPO, five fault cases, raw CSVs, independent verifier and Windows/macOS launchers. Clean minimal Linux dependency environment smoke-tested; actual target OS execution pending.','',
        '## Matched development results','',
        'Gains are averages of episode RMSE on this fresh development grid. These are not confidence bounds or unseen-test generalization. Different grids cannot be compared as paired improvements. Steering column is actuator-rate RMS relative to matched LQR.','',
        '| Method | Tracking gain vs LQR | Heading change vs LQR | Steering-rate change vs LQR | Survival |',
        '|---|---:|---:|---:|---:|']
    for name,m in metrics.items():
        lines.append(f'| {name} | {m["gain_vs_lqr_pct"]:+.3f}% | {100*(m["heading_rmse_rad"]/base["heading_rmse_rad"]-1):+.2f}% | {100*(m["rate_rms_rad_s"]/base["rate_rms_rad_s"]-1):+.2f}% | {m["survived"]}/{m["episodes"]} |')
    lines+=['','## Diagnosis and selection','',
        'The original age-gain PPO improves lateral tracking but strongly increases steering activity. The predefined0.1s low-pass and0.25authority cap reduce that activity, while still failing the5% steering trade-off criterion. The same-gain supervised student remains better than PPO in mean lateral RMSE, including two of three paired seeds for age_filtered. Thus the additional value of PPO fine-tuning is not established.',
        'Replacing raw command-jump cost with predicted physical actuator-rate cost alone admits almost no useful assistance. Observable curvature preview recovers a small tracking gain with modest heading/rate changes, but remains below the frozen1% tracking-gain threshold and does not consistently beat the student. This local20-step model/objective remains a bottleneck; these results do not isolate a single causal reason or prove a new cost will succeed.','',
        '| Profile/source | Applied nonzero-weight ticks / total |', '|---|---:|']
    for name in metrics:
        profile,source=name.split('/');rr=[r for r in episodes if r['profile']==profile and r['source']==source]
        lines.append(f'| {name} | {sum(int(r["active"]) for r in rr)}/{sum(int(r["steps"]) for r in rr)} |')
    lines+=['','Eligibility requires at least1% gain over LQR, same-profile student and both constants; positive student-relative gains for all three seeds; no survival loss; nominal no more than2% worse than LQR; heading and rate no more than5% worse than LQR.','',
        f'**Selected profile: {decision["selected"]}. Reserved confirmation remains unopened.** No criteria were relaxed after seeing results. No further training, native winner confirmation or unseen-path claim is justified by this screen.','',
        '## Published-method comparison and claim boundary','',
        'Primary source: Wabersich and Zeilinger, arXiv1812.05506v4, §4.1 Eq5 and Algorithm1, supplied by the author. The nominal quadratic program minimizes first-command deviation from the learned proposal, respects disclosed model-state/input limits, and uses a constant-curvature terminal equilibrium with shrinking-horizon recovery. The same noisy observer, nonlinear software plant, actuator limits, paths and delay cases were used for the matched experiment.',
        'This is a nominal linear specialization, not the authors’ implementation or a reproduction of their uncertainty-aware Algorithm2. Exact-model, state-knowledge and constant-curvature assumptions do not hold on this test plant. Consequently the paper’s safety theorem cannot be transferred. If the full and shortened programs fail, the fresh-state LQR fallback is explicitly uncertified. Do not interpret this comparison as superiority over the complete published method.','',
        f'Nominal PSF handled{metrics["nominal_psf/ppo"]["psf_calls"]} command requests and logged{metrics["nominal_psf/ppo"]["psf_fallbacks"]} uncertified LQR fallback events. A request may solve both full and shortened programs. Its tracking gain is{metrics["nominal_psf/ppo"]["gain_vs_lqr_pct"]:.3f}%; its actuator-rate change is{100*(metrics["nominal_psf/ppo"]["rate_rms_rad_s"]/base["rate_rms_rad_s"]-1):.2f}%.',
        'Closest related areas remain predictive safety filtering, Simplex/runtime assurance, delayed-observation shielding and delay-aware MPC. LANS cannot claim novelty merely from combining LQR, PPO and thresholds or naming a supervisor neuro-symbolic. Explicit predicates and predictions are implemented engineering mechanisms; a broad claim of unique symbolic reasoning or formal safety is unsupported. Supplied primary texts support the scoped comparison; full venue/DOI/reference-list verification and an authors-code matched benchmark remain incomplete.','',
        '## Original-deadline timing A/B','',
        '| Timer profile | Missed10ms deadlines | Functional replay | Nonzero correction ticks |', '|---|---:|---|---:|']
    for name,m in timing.items():lines.append(f'| {name} | {m["deadline_misses"]}/{m["ticks"]} | {m["functional_pass"]} | {sum(e["nonzero_correction_ticks"] for e in m["episodes"])} |')
    lines+=['',
        'Both profiles use the predefined age_filtered residual diagnostic and old25k PPO exports. Parent runs on one core; worker/nice10 and two generated stressors/nice19 run on the other. Native profile uses CLOCK_MONOTONIC absolute sleep plus at most100µs spin, preserving every original target and10ms deadline. Same noise per seed and randomized profile order. No OS isolation, privileged real-time scheduling or host contention exclusion exists.',
        '**Any observed miss fails strict timing.** Finite zero misses would establish only observed timing in this setting, not WCET. Fixed-step plant survival and functional LQR fallback do not prove continuously evolving real-time plant safety during host stalls. No100Hz or vehicle-readiness guarantee is made.','',
        '## What remains and why','',
        '| Work item | Status |', '|---|---|',
        '| Gate/objective mismatch investigation | Completed fixed follow-up; useful balanced PPO winner not established |',
        '| Learning additional value | Tested with same-gain controls; not established |',
        '| Local10ms requirement | See raw A/B table; unresolved if any miss; no hard-real-time guarantee |',
        '| Reserved/unseen confirmation | Intentionally not opened because development screen failed |',
        '| Published comparison | Nominal Eq5/Algorithm1 specialization complete; robust authors-code reproduction and full bibliographic metadata verification remain |',
        '| Laptop rerun | Full-controller kit ready and Linux smoke verified; actual Windows/macOS data required |',
        '| Physical sensor/communication/actuator validation | Requires connected target hardware/vehicle; unavailable in this cloud |',
        '| Paper/report | Evidence update complete; positive-performance submission claims still unsupported |','',
        'Next research decision: either report the engineering/failure-analysis study honestly, or freeze a new teacher-headroom/learning objective study before new training. Repeatedly tuning this development grid cannot replace untouched confirmation. Hardware validation requires the user to run the kit and return results; physical readiness additionally requires actual sensors, communications and actuators.','',
        '## Reproduction and artifacts','',
        '`python tools/controller_review/run_followup_work.py --publish` resumes completed stages, runs outstanding frozen software stages, verifies outputs and pushes milestones. It never executes the user laptop, opens reserved tests on failure, trains new policies or marks physical validation complete.','',
        'See summary.json, decision.json, actor-verification.json, episodes.csv and raw pair-*/traces. Timing source/protocol/raw traces and verification are under timing/. The full laptop ZIP and kit-smoke/ raw verification are included. Original reviewer-causal-v1 evidence is preserved.']
    (out/'final-research-update.md').write_text('\n'.join(lines)+'\n')
    status=dict(episodes=decision['episodes'],selected=decision['selected'],learning_additional_value_established=False,
        observed_strict_timing_pass={n:m['timing_pass'] for n,m in timing.items()},reserved='unopened',
        actual_laptop_validation=False,physical_vehicle_validation=False,submission_ready_positive_performance_claim=False)
    (out/'completion-status.json').write_text(json.dumps(status,indent=2)+'\n')
    for suffix in ('docx','pdf'):
        cmd=['pandoc',str(out/'final-research-update.md'),'--from=markdown+tex_math_single_backslash','-o',str(out/f'final-research-update.{suffix}')]
        if suffix=='pdf':cmd+=['--pdf-engine=xelatex','-V','mainfont=DejaVu Serif','-V','geometry:margin=22mm']
        subprocess.run(cmd,check=True)
    with zipfile.ZipFile(out/'LANS_Followup_Reports.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ('final-research-update.md','final-research-update.docx','final-research-update.pdf','completion-status.json','summary.json','decision.json','actor-verification.json','episodes.csv'):
            z.write(out/name,name)
    print(json.dumps(status,indent=2))


if __name__=='__main__':main()
