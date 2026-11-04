"""Build the reviewed-scope thesis and result ledger from gated final evidence."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).parent


def read(p):return json.loads(Path(p).read_text())


def certificates():
    groups={}
    for family,suffix in [('Python','python'),('Webots','native')]:
        revision='v4'
        data=[]
        for stage,part in [('development','dev'),('validation','validation')]:
            root=ROOT/f'results/settling-cert-{suffix}-{part}-{revision}'
            s=read(root/'summary.json')[stage];assert s['passed']
            data.extend(s['results'])
        assert all(z['passed'] and not z['uncertified_pair_intervals'] for z in data)
        groups[family]=dict(episodes=len(data),intervals=sum(z['intervals'] for z in data),
            pair_intervals=sum(z['pair_intervals'] for z in data),
            minimum_clearance_lower_m=min(z['minimum_euclidean_clearance_lower_m'] for z in data))
        if family=='Webots':
            actors=[v for z in data for v in z['native_refinement'].values()]
            groups[family].update(motion_samples=sum(z['motion_samples'] for z in actors),
                max_sampled_planar_speed_m_s=max(z['max_sampled_planar_speed_m_s'] for z in actors),
                max_sampled_coordinate_accel_m_s2=max(z['max_sampled_coordinate_accel_m_s2'] for z in actors),
                max_sampled_yaw_rad_s=max(z['max_sampled_yaw_rad_s'] for z in actors),
                max_sampled_bridge_deviation_m=max(z['max_sampled_bridge_deviation_m'] for z in actors),
                max_requested_measured_accel_difference_m_s2=max(z['max_requested_vs_measured_accel_difference_m_s2'] for z in actors))
    return groups


def build(output):
    regression=read(ROOT/'results/settling-original150-regression-v3/regression.json')
    assert regression['passed'] and regression['classification']=='EXPOSED_OLD_FAILURE_REGRESSION_NOT_FRESH'
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    checks=read(ROOT/'results/settling-verification-final-v6/checks.json')
    assert checks['passed'] and checks['checks'][-1]['label']=='final-report'
    for label in ['negative-controls','unreachable-python','unreachable-native','exported-smt-replay']:
        assert any(x['label']==label and x['returncode']==0 for x in checks['checks'])
    report=ROOT/'results/settling-report-final-v6';overall=read(report/'report.json')
    families={'Python':ROOT/'results/settling-v4','Webots':ROOT/'results/settling-native-v4'}
    cohorts={name:{stage:read(root/stage/'summary.json') for stage in ('development','validation')} for name,root in families.items()}
    assert all(s['passed'] and all(r['passed'] for r in s['results']) for stages in cohorts.values() for s in stages.values())
    proof=certificates()
    native=proof['Webots']
    figures=output/'figures';figures.mkdir()
    for p in report.glob('*'):
        if p.suffix in ('.png','.pdf'):shutil.copyfile(p,figures/p.name)
    old=(ROOT/'docs/thesis/lans-conditional-safety-v1/LANS_Simulation_Conditional_Safety_Thesis.md').read_text()
    related=old.split('# Related work and positioning\n',1)[1].split('# LANS architecture and evidence boundaries',1)[0].strip()
    longitudinal=old.split('# Conditional safety formulation\n',1)[1].split('# Experimental method',1)[0].strip()
    longitudinal=re.sub(r'^(#+) ',r'#\1 ',longitudinal,flags=re.M)
    references=old.split('# References {-}\n',1)[1].strip()
    p,w=overall['Python'],overall['Webots']
    abstract=(f"The final fresh cohorts pass {p['episodes']}/{p['episodes']} Python and "
        f"{w['episodes']}/{w['episodes']} native Webots episodes across eight profiles. "
        f"The worst final-five-second spacing RMS is {p['tail_spacing_rms_max_m']:.6f} m "
        f"in Python and {w['tail_spacing_rms_max_m']:.6f} m in Webots, with no censored "
        "two-second stable head returns. Separate unreachable cases remain ordinary "
        "recovery failures with expected braking. Failed earlier cohorts are preserved.")
    lines=[]
    for name in ('Python','Webots'):
        z=overall[name];g=proof[name]
        lines.append(f"{name}: **{z['episodes']}/{z['episodes']} fresh runs pass**, with zero sampled collisions, "
            f"zero freshness/requested-bound/lane violations and {z['censored_stable_return']} censored stable returns. "
            f"Worst tail spacing RMS is **{z['tail_spacing_rms_max_m']:.6f} m**, maximum absolute tail error "
            f"{z['tail_max_abs_error_m']:.6f} m, and maximum confirmed-settling onset delay after cut-out "
            f"{z['settling_delay_max_s']:.2f} s. Whole-window correct-target spacing RMS can reach "
            f"{z['whole_window_conditional_rms_max_m']:.3f} m and stopped duration "
            f"{z['maximum_stopped_s']:.2f} s; these transient measures are retained. "
            f"The worst whole-run unconditional headway RMS is {z['whole_window_unconditional_head_rms_max_m']:.3f} m, "
            f"and the worst post-cut-out unconditional headway RMS is {z['post_exit_unconditional_head_rms_max_m']:.3f} m. "
            f"Maximum post-cut-out nominal head gap is {z['post_exit_max_nominal_head_gap_m']:.3f} m. "
            f"Across development and validation, all {g['episodes']} traces and {g['pair_intervals']:,} "
            f"actor-pair intervals have a continuous conditional certificate. The minimum "
            f"conservative Euclidean clearance lower bound is {g['minimum_clearance_lower_m']:.6f} m.")
    lines.append("The verifier retains the first valid separating axis. Its minimum clearance lower bound "
        "is not an actual nearest-body distance estimate or the strongest bound over all axes.")
    lines.append(f"Native qualification includes {native['motion_samples']:,} motion samples. Maximum sampled "
        f"coordinate acceleration is {native['max_sampled_coordinate_accel_m_s2']:.6f} m/s², "
        f"yaw rate {native['max_sampled_yaw_rad_s']:.6f} rad/s, planar speed "
        f"{native['max_sampled_planar_speed_m_s']:.6f} m/s and recorded bridge deviation "
        f"{native['max_sampled_bridge_deviation_m']:.6f} m. Requested-versus-measured acceleration "
        f"discrepancy reaches {native['max_requested_measured_accel_difference_m_s2']:.6f} m/s². "
        "Thus a requested braking bound is not substituted for actual native response. "
        "Finite motion checks support, but do not prove, the continuous derivative premises.")
    lines.append("All independent aggregate/source/wire/pacing/guard-phase audits and regenerated Python inputs pass. "
        "Six exported 2-D SMT obligations replay as UNSAT; the omitted-bridge control is SAT. "
        "All five semantic corruption controls are rejected after rehashing. Both final unreachable "
        "diagnostics pass their expected fail-safe checks and retain ordinary recovery FALSE.")
    lines.append("The unreachable Python diagnostic brakes from 12 m/s. The native unreachable fixture "
        "starts at rest and inhibits launch; it is a cold-start fail-safe check, not a moving stopping "
        "experiment. Moving native information loss is exercised separately by the ordinary blackout profiles.")
    reg=regression['new_70s_result'];prefix=regression['original_35s_prefix']
    lines.append("The specifically exposed original 150 m failure, noisy/non-connected traffic at 12 m/s "
        f"and seed 2003, also passes a separate known-failure regression. Its new 70 s tail RMS is "
        f"{reg['tail_spacing_rms_m']:.6f} m and stable-return onset delay is {reg['stable_return_2s_s']:.2f} s. "
        f"Within the original first 35 s it has {round(prefix['longest_correct_run_s']/.05)} consecutive "
        f"correct fresh head samples ({prefix['longest_correct_run_s']:.2f} s by the declared 20 Hz count). "
        "Its independent audit and continuous all-actor "
        f"certificate ({regression['continuous_certificate']['pair_intervals']:,} pair intervals) pass. "
        "This exposed seed is regression evidence, excluded from fresh denominators. The older 35 s "
        "failure remains unchanged; the architecture and horizon differ, so no matched causal "
        "percentage is claimed.")
    result='\n\n'.join(lines)
    tables=[]
    for name,stages in cohorts.items():
        tables += [f'## {name} fresh profile coverage','',
            '| Profile | Runs | Worst tail RMS (m) | Tail max error (m) | Max onset delay (s) |',
            '| --- | ---: | ---: | ---: | ---: |']
        for profile in read(families[name]/'plan.json')['cases']:
            group=[z for z in stages['validation']['results'] if z['case']==profile]
            tables.append(f"| {profile.replace('_',' ')} | {len(group)} | {max(z['tail_spacing_rms_m'] for z in group):.6f} | {max(z['tail_spacing_max_abs_m'] for z in group):.6f} | {max(z['settling_delay_2s_s'] for z in group):.2f} |")
        tables.append('')
    cohort_text=[]
    for name,root in families.items():
        plan=read(root/'plan.json');d=cohorts[name]['development']['results'];v=cohorts[name]['validation']['results']
        exposed=("The earlier exposed 7069 failure is explicitly development data in the replacement Python campaign."
            if name=='Python' else "The exposed native 8011 and 12037 failures are explicitly development data; the 16001-series confirmation inputs were unopened during refinement.")
        cohort_text.append(f"{name}: {len(d)} development and {len(v)} fresh validation episodes. "
            f"Development seeds: {', '.join(map(str,plan['development_seeds']))}. Fresh validation seeds: "
            f"{', '.join(map(str,plan['validation_seeds']))}. {exposed}")
    failure=("An always-narrow exploratory guard collided during unobserved cut-in; all eight early Python "
        "probes failed. The first complete frozen development grid passed 71/72, exposing lost relay/exit "
        "association. Priority original-byte forwarding, fresh cooperative anchors and measured membership "
        "addressed those failures. The next frozen candidate passed 72/72 Python development and 16/16 native "
        "development but only 239/240 fresh Python runs: combined/16/7069 lost all useful head paths after "
        "a brief return. It had no collision but failed recovery/progress; native validation stayed closed.\n\n"
        "A 4 m/s-only pacing probe then reproduced combined/16/6121 path loss. The corresponding development "
        "campaign was aborted with 21 completed cases and an explicit ABORTED marker; it is not a complete "
        "passing cohort. Analysis found unnecessary adjacent-traffic stops after the in-lane predecessor "
        "was already admitted. Three distinct fresh unblocked observations after an observed cut-in now "
        "establish lane-aware following while initial approach remains conservative. Six source-frozen "
        "probes, including both exposed combined failures, passed before the replacement full grid. "
        "No 9001-series final validation seed was opened during these common-controller amendments.\n\n"
        "The next native campaign passed 16 development runs, then was aborted after 42 fresh records: "
        "41 passes and one conservative vehicle-envelope overlap in noisy/non-connected/8/8011. "
        "Requested -6 m/s² was physically realized at about 2.8 m/s² because the unchanged Car velocity "
        "motor ramp uses time0To100=10 s. Applying friction braking in SPEED mode alone failed that "
        "case; a TORQUE-mode probe resolved it but failed three other recovery/pose cases. All probes "
        "and the partial native source/data are preserved.\n\n"
        "The accepted native-only refinement plans earlier braking with a 2.5 m/s² allowance and 0.8 s "
        "reserve from fresh observed guard objects. It preserves the stable SPEED-mode plant, adds a "
        "0.3 s brake-release hold and logs/replays nominal commands, native overrides and API readback "
        "separately. The accepted adapter uses stable SPEED-mode motor stopping with friction "
        "intensity zero; mixing locked friction brakes with the velocity servo failed a curved "
        "combined probe. Pinned R2025a Radar source also confirmed that partially visible targets "
        "have azimuth clipped to the physical aperture edge. The adapter rejects the ambiguous "
        "0.33–0.35 rad fringe, preserving unknown/never-clear semantics and matching the Python "
        "central aperture. Friction, mass, geometry and the original vehicle ramp are unchanged. The common "
        "Python source and its 240 fresh results remain unchanged. Native development now covers both "
        "8/12 m/s at seeds 6203, exposed 8011 and exposed 12037 (48 runs), followed by entirely new 16001-series seeds.\n\n"
        "The resulting native-v3 campaign passed 32 development and 79/80 fresh trials. "
        "Combined/12/12037 develops steering divergence near 18.5–18.75 m/s, then leaves the lane; "
        "it is retained as an actual failed confirmation. The replacement caps native recovery "
        "setpoints at 16 m/s and qualifies observed planar speed at most 16.5 m/s, preserving a "
        "catch-up margin over the 8/12 m/s head cruise. Heading/lane and all other gates remain "
        "unchanged. This declares a native steering operating envelope, not a stability theorem "
        "at arbitrary speed. The new fresh seeds are unopened 16001-series inputs.\n\n"
        "All complete failed grids, partial development, raw probes and exact frozen sources where available "
        "remain archived. Exploratory probes without a contemporaneous source freeze are labelled with "
        "that provenance limitation. Earlier 150 m 35/36 evidence remains unchanged and is not relabelled.")
    pacing=("The head uses only its own state and actually received member beacons. Beyond a 60 m "
        "reserve gap it lowers its goal by at most 4 m/s; unavailable member beacons use the same bounded "
        "reduction. The head must return to cruise in the final-window gate. This is finite-scenario "
        "connectivity support, not a universal link-retention invariant. The direct range remains 150 m "
        "in Python links, native Emitter fields and runtime configuration.")
    reproduction=("The final execution roots are `results/settling-v4` and `results/settling-native-v4`. "
        "Every plan identifies exact execution source hashes and the archived source closure. "
        "The release source includes independent audit, input regeneration, certification, reporting, "
        "manuscript and packaging helpers. Frozen execution snapshots and later analysis sources are "
        "identified separately. Complete ZIP shards are below 32 MiB each and include original control/"
        "wire observations, 10 ms motion, generated native worlds/controllers, certificates, failures "
        "and this editable manuscript. Outer SHA-256, member SHA-256 and ZIP CRC checks cover the package.\n\n"
        "Use Python 3.10.22, NumPy 1.23.5, SciPy 1.10.1 and z3-solver 4.13.3.0; Webots R2025a "
        "uses pinned runtime and PROTO hashes. Follow the settling README with new output roots. "
        "Do not overwrite or resume an existing campaign. Full commands and captured verification outputs "
        "are in `settling-verification-final-v6`. The older one-dimensional thesis and proof stay preserved "
        "in `docs/thesis/lans-conditional-safety-v1` and `integrations/connected_v2v/conditional_safety`.\n\n"
        "The PDF and Word documents are rendered from the same Markdown. Equations remain editable in Word. "
        "No institution, degree, student number, approval signature or hardware evidence is invented.")
    values=dict(ABSTRACT_RESULTS=abstract,RELATED_WORK=related,LONGITUDINAL_MODEL=longitudinal,
        PACING_DESCRIPTION=pacing,COHORT_DESCRIPTION='\n\n'.join(cohort_text),RESULTS=result,
        RESULTS_TABLE='\n'.join(tables),FAILURE_HISTORY=failure,REPRODUCIBILITY=reproduction,REFERENCES=references)
    text=(HERE/'MANUSCRIPT.md').read_text()
    for key,value in values.items():text=text.replace('@'+key+'@',value)
    assert not re.search(r'@[A-Z_]+@',text)
    source=output/'LANS_V2V_Formation_Conditional_Safety_Thesis.md';source.write_text(text)
    common=['pandoc',source.name,'--standalone','--toc','--number-sections']
    subprocess.run([*common,'--pdf-engine=xelatex','-V','geometry:margin=22mm','-V','mainfont:DejaVu Serif',
        '-V','sansfont:DejaVu Sans','-V','monofont:DejaVu Sans Mono','-o',source.with_suffix('.pdf').name],cwd=output,check=True)
    subprocess.run([*common,'-o',source.with_suffix('.docx').name],cwd=output,check=True)
    (output/'README.md').write_text('''# Updated simulation thesis: formation recovery and conditional safety

- [PDF research draft](LANS_V2V_Formation_Conditional_Safety_Thesis.pdf)
- [Editable Word draft](LANS_V2V_Formation_Conditional_Safety_Thesis.docx)
- [Shared Markdown source](LANS_V2V_Formation_Conditional_Safety_Thesis.md)
- [Result ledger](../../../integrations/connected_v2v/settling/RESULTS.md)
- [2-D theorem and exact certificate contract](../../../integrations/connected_v2v/settling/THEORY2D.md)
- [Recovery operating limits](../../../integrations/connected_v2v/settling/OPERATING_ENVELOPE.md)

The earlier longitudinal thesis/evidence are preserved. This draft integrates the
new formation fixes, new seeds, raw native motion and broader conditional finite
trace certificates. The 1-D prospective theorem and 2-D a posteriori result have
distinct scopes. All failed histories remain visible; final benchmarking is held.
Prepared for technical/supervisor review, without invented institutional details.
''')
    ledger='# Final formation recovery and conditional 2-D trace evidence\n\n'+result+'\n\n'+'\n'.join(tables)
    ledger+='\n## Failed history retained\n\n'+failure+'\n\n## Exact scope\n\n'+pacing+'\n\n'
    ledger+='The 2-D result is a posteriori finite continuous trajectory certification under the stated contract; '
    ledger+='it is not prospective full-controller invariance or real-world safety certification. '
    ledger+='Final comparative benchmarking remains on hold.\n'
    (HERE/'RESULTS.md').write_text(ledger)
    (output/'verified-metrics.json').write_text(json.dumps(dict(fresh=overall,certificates=proof,original150_regression=regression),indent=2)+'\n')
    return dict(thesis=str(output),fresh=overall,certificates=proof,original150_regression_passed=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(build(a.output),indent=2))
