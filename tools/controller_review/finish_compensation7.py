"""Document approximate response-delay compensation and measured limitations."""
import argparse
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import zipfile
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();out=a.run
    load=lambda n:json.loads((out/n).read_text())
    metrics=load('summary.json');verification=load('verification.json');runtime=load('runtime-verification.json');smoke=load('kit-smoke/summary.json')
    assert (out/'kit-smoke/verification.json').exists() and load('regression-verification.json')['passed']
    rows=list(csv.DictReader((out/'episodes.csv').open()));survived=sum(r['survived']=='True' for r in rows)
    accuracy=[]
    for row in rows:
        if row['source']!='compensated':continue
        with gzip.open(out/'traces'/row['trace'],'rt') as f:trace=list(csv.DictReader(f))
        requests={round(float(r['observation_time_s'])*100):r for r in trace if r['submitted']=='True'};seen=set()
        for r in trace:
            seq=int(r['packet_seq'])
            if seq<0 or seq in seen:continue
            seen.add(seq)
            if not 0<=float(r['packet_age_s'])<.05:continue
            original=requests[round(float(r['packet_observed_s'])*100)]
            query=json.loads(original['query_json']);meta=json.loads(original['query_metadata_json']);raw=meta['raw_observation']
            accuracy.append(dict(age_s=float(r['packet_age_s']),horizon_s=meta['used_horizon_s'],
                raw_lateral_error_m=3*(raw[0]-float(r['obs0'])),forecast_lateral_error_m=3*(query[0]-float(r['obs0'])),
                raw_heading_error_rad=.3*(raw[1]-float(r['obs1'])),forecast_heading_error_rad=.3*(query[1]-float(r['obs1']))))
    rmse=lambda key:math.sqrt(statistics.mean(r[key]**2 for r in accuracy))
    prediction=dict(eligible_first_deliveries=len(accuracy),raw_lateral_input_rmse_m=rmse('raw_lateral_error_m'),forecast_lateral_input_rmse_m=rmse('forecast_lateral_error_m'),
        raw_heading_input_rmse_rad=rmse('raw_heading_error_rad'),forecast_heading_input_rmse_rad=rmse('forecast_heading_error_rad'),
        mean_absolute_horizon_error_ms=1000*statistics.mean(abs(r['age_s']-r['horizon_s']) for r in accuracy),
        scope='Post-hoc calibration on compensated trajectories; noisy observer estimates are comparison targets, not ground truth or an independent efficacy experiment. No parameters fitted.')
    (out/'prediction-calibration.json').write_text(json.dumps(prediction,indent=2)+'\n')
    lines=['# Explicit neural-response latency compensation in LANS','',
        '27 October 2026 (Asia/Shanghai). Experimental addition; previous frozen studies remain unchanged.','',
        '## Implemented mechanism','',
        'The supervisor now owns an explicit model-based input compensator. At an available PPO query, it forecasts the latest estimated vehicle/actuator state over the anticipated observation-to-response delay and gives the resulting physical features to PPO. On receipt, the ordinary supervisor still evaluates that residual against the latest current-state LQR baseline. The existing default profile is unchanged; this feature is selected explicitly with `delay_compensated`.',
        r'$$\hat d_i=0.75\hat d_{i-1}+0.25\min(0.04,T_{\mathrm{recv},i}-T_{\mathrm{obs},i}),\qquad \hat d_0=0.01\ \mathrm{s}.$$',
        'The estimate updates only once for each strictly increasing completed-response sequence. Held packets do not age the estimate repeatedly. It does not read the current configured service delay, pending completion or a future observation. The measured response age includes inference/dispatch/IPC/polling effects; it is distinct from neural inference duration alone.',
        r'$$\hat\xi(t+\hat d\mid t)=F_{\mathrm{nom}}(\hat\xi(t),\delta_a(t),\pi_{\mathrm{LQR}},\mathcal{R}_t,\hat d),\qquad \Delta\delta=\pi_{\mathrm{PPO}}(o^{\mathrm{pred}}_t).$$',
        'The forecast uses the nominal bicycle model, present measured speed/gain and reference-curvature preview, with LQR continuation. Euler steps are at most10ms, prediction is capped40ms, actuator time constant is50ms, rate limit0.35rad/s and steering-angle limit0.5rad. The route preview shifts by speed times prediction horizon. Known policy history is retained; channels15/16/17/19 remain zero. If the forecast leaves the declared lateral/heading envelope, the actual raw query is used and that reason is logged.',
        'The model interface is separately declared as `latency_compensated_query_v7`. The diagnostic copies frozen v5 NumPy actors without changing their weights. Those weights were not retrained on predicted-state inputs, so distribution shift remains an explicit limitation. Runtime rejects mixing legacy/history and compensated interfaces.',
        'This changes the policy input, unlike freshness-only rejection. Original observation timestamps are never refreshed, and the50ms stale cutoff is unchanged. Compensation cannot rescue arbitrarily old packets, reduce physical inference duration, cancel sensor/transport delay, or establish1,000ms delayed LQR-feedback tolerance. The existing latest-state cost gate, filter, cap and gradual recovery are unchanged; the earlier proposed multi-weight argmin/first-step-only rollout is not silently substituted.','',
        '## Controlled development evidence','',
        f'Eight compensation contracts and seven legacy history/packet checks pass. The fixed diagnostic contains **{verification["episodes"]} episodes**, **{verification["transitions"]:,} replayed transitions**, **{verification["submitted_actor_queries"]:,} submitted actor decisions** and **{survived}/{len(rows)} survivors**. It compares LQR, raw-query PPO and compensated-query PPO at20m/s on one known mirrored path, using three actors/noise groups and10/20/40/100ms logical service. No training, tuning, reserved evaluation or promotion occurred.','',
        '| Logical service | Raw PPO lateral RMSE m | Compensated RMSE m | Tracking gain vs raw | Heading change vs raw | Rate RMS change vs raw |','|---|---:|---:|---:|---:|---:|']
    gains={}
    for service,batch in metrics.items():
        raw=batch['raw'];comp=batch['compensated'];gain=100*(1-comp['rmse_m']/raw['rmse_m']);gains[service]=gain
        lines.append(f'| {1000*float(service):.0f}ms | {raw["rmse_m"]:.6f} | {comp["rmse_m"]:.6f} | {gain:+.3f}% | {100*(comp["heading_rmse_rad"]/raw["heading_rmse_rad"]-1):+.3f}% | {100*(comp["rate_rms_rad_s"]/raw["rate_rms_rad_s"]-1):+.3f}% |')
    lines+=['',f'All **{verification["severe_delay_exact_lqr_pairs"]}** 100ms-delay raw/compensated-versus-LQR trajectory pairs are exactly equal: compensation does not bypass freshness rejection. Positive table values indicate lower lateral RMSE; negative values indicate harm. This narrow comparison does not establish the earlier full student/fixed-baseline selection criteria or general superiority.',
        'At40ms logical service neither neural variant had any nonzero learned authority. A40ms-old proposal expires at50ms before the unchanged three-good-control-tick recovery can finish; intervening stale decisions reset recovery. Therefore zero difference at40ms is baseline-only operation, not evidence of successful40ms assisted compensation. The recovery/freshness interaction is preserved and reported rather than bypassed to create a gain.',
        f'At {prediction["eligible_first_deliveries"]} eligible first deliveries on compensated trajectories, raw-versus-current lateral-input RMSE was {prediction["raw_lateral_input_rmse_m"]:.6f}m and forecast-versus-current RMSE was {prediction["forecast_lateral_input_rmse_m"]:.6f}m. Mean absolute forecast-horizon error was {prediction["mean_absolute_horizon_error_ms"]:.3f}ms. These are post-hoc noisy-estimate calibration measurements, not true-state error bounds or a causal proof of tracking improvement.','',
        '## Real-worker integration','',
        f'Three actors ran all five actual worker cases for1second each: **{runtime["ticks"]} ticks**, **{runtime["all_issued_queries_replayed"]} issued forecast queries**, and **{runtime["completed_latency_updates_replayed"]} observable completed-response updates** were replayed. Original deadlines recorded **{runtime["deadline_misses"]} misses**. Input forecasts, known history, source/model hashes, actor outputs, fusion/gate decisions and original stale timestamps were checked. Actual post-inference waits are separate from offline total logical service; their delay distributions are not assumed equal.',
        'This is a short software integration test, not100Hz qualification, native Webots confirmation, actual laptop execution or physical sensor/actuator validation. Previous strict real-time failures remain unresolved. A model forecast over estimated delay is approximate compensation; it cannot guarantee cancellation under model mismatch, unexpected stalls, measurement noise or a busy local control process.','',
        f'The exported Torch-free Python3.10 kit also passed an independent clean-environment packaging replay: {sum(e["ticks"] for e in smoke["episodes"])} ticks, {sum(e["deadline_misses"] for e in smoke["episodes"])} deadline misses, functional fallback {smoke["functional_pass"]}. This separate short smoke is not pooled with the three-actor integration campaign or presented as actual Windows/macOS execution.',
        '## Run and integration','',
        '`python tools/reviewer_v7/run7.py --publish` resumes the fixed verified diagnostic without retuning or overwriting partial outcomes. Use the generated actor directory with `python tools/controller_review/laptop_full_controller.py --profile delay_compensated --models docs/research/reviewer-delay-compensation-v7/actor --output laptop-results-compensated` for a separate diagnostic. Existing output folders must not be overwritten.',
        'The new experimental laptop ZIP uses the same profile and explicit model declaration. Extract it before running RUN_WINDOWS.cmd or `bash RUN_MAC.command`. This does not make a selected/deployment controller. Keep raw results even if prediction harms performance.',
        'The diagram can show a Model-based Delay Compensator inside the supervisor, taking past completed-response timing and current estimated state/reference, and supplying forecast physical features to the Observation Builder/PPO. The admission gate must retain its separate latest-state input.','',
        'The honest report wording is: **LANS includes experimental causal model-based compensation for anticipated neural-response latency, together with latest-state predictive admission, unchanged stale-proposal rejection and LQR fallback.** Physical command-delay cancellation and guaranteed real-time operation are not claimed.']
    text='\n\n'.join(lines)
    # Keep Markdown table rows adjacent while making prose readable.
    text=text.replace('|\n\n|','|\n|')
    parts=re.split(r'(`[^`]*`|\$\$.*?\$\$)',text,flags=re.S)
    for i,part in enumerate(parts):
        if part.startswith(('`','$$')):continue
        part=re.sub(r'(?<=[A-UW-Za-uw-z])(?=\d)',' ',part)
        parts[i]=re.sub(r'(?<=\d)(?=[A-UW-Za-uw-z])',' ',part)
    text=''.join(parts)
    (out/'README.md').write_text(text.rstrip()+'\n')
    status=dict(explicit_model_based_input_compensation_implemented=True,default_profile_unchanged=True,forecast_horizon_cap_ms=40,stale_cutoff_ms=50,
        compensation_contracts=8,legacy_regression_checks=7,episodes=verification['episodes'],survivors=survived,tracking_gain_vs_raw_by_service_pct=gains,
        runtime_ticks=runtime['ticks'],runtime_deadline_misses=runtime['deadline_misses'],new_training_steps=0,kit_functional_fallback_pass=smoke['functional_pass'],
        full_selection_assessed=False,full_selection_pass=False,reserved_unopened=True,actual_laptop_run=False,physical_delay_cancellation=False,guaranteed_realtime=False)
    (out/'completion-status.json').write_text(json.dumps(status,indent=2)+'\n')
    os.environ.setdefault('XDG_CACHE_HOME','/tmp/lans-v7-font-cache');Path(os.environ['XDG_CACHE_HOME']).mkdir(exist_ok=True)
    for suffix in ('docx','pdf'):
        cmd=['pandoc',str(out/'README.md'),'-o',str(out/f'delay-compensation.{suffix}')]
        if suffix=='pdf':cmd+=['--pdf-engine=xelatex','-V','mainfont=DejaVu Serif','-V','geometry:margin=22mm','-V','fontsize=10pt']
        subprocess.run(cmd,check=True)
    with zipfile.ZipFile(out/'LANS_Delay_Compensation_Reports.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ('README.md','delay-compensation.docx','delay-compensation.pdf','summary.json','verification.json','runtime-verification.json','completion-status.json','prediction-calibration.json'):
            z.write(out/name,name)
    checks={}
    for f in out.glob('*.zip'):
        with zipfile.ZipFile(f) as z:assert z.testzip() is None
        checks[f.name]=hashlib.sha256(f.read_bytes()).hexdigest()
    (out/'artifact-quality.json').write_text(json.dumps(dict(crc_pass=True,sha256=checks),indent=2)+'\n');print(json.dumps(status,indent=2))

if __name__=='__main__':main()
