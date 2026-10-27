"""Post-outcome attribution; no controller/selection changes or reserved reads."""
import argparse
import csv
import gzip
import json
import statistics
from collections import Counter
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();out=a.run
    assert (out/'decision.json').exists(),'Only analyze after frozen verification'
    rows=list(csv.DictReader((out/'episodes.csv').open()));strata=[];activity={}
    mean=lambda rr,key:statistics.mean(float(r[key]) for r in rr)
    for speed in (15,25):
        for scenario in ('nominal','tire','delay20','delay100'):
            subset=[r for r in rows if int(r['speed'])==speed and r['scenario']==scenario]
            base=[r for r in subset if r['source']=='lqr'];student=[r for r in subset if r['source']=='student']
            for source in ('all_actions','submitted_only'):
                rr=[r for r in subset if r['source']==source]
                strata.append(dict(speed=speed,scenario=scenario,source=source,episodes=len(rr),gain_vs_lqr_pct=100*(1-mean(rr,'rmse_m')/mean(base,'rmse_m')),
                    gain_vs_student_pct=100*(1-mean(rr,'rmse_m')/mean(student,'rmse_m')),heading_change_pct=100*(mean(rr,'heading_rmse_rad')/mean(base,'heading_rmse_rad')-1),rate_change_pct=100*(mean(rr,'rate_rms_rad_s')/mean(base,'rate_rms_rad_s')-1)))
    for source in ('student','v3ppo','all_actions','submitted_only'):
        reasons=Counter();proposals=Counter();ticks=submitted=0
        for pair in range(3):
            for f in (out/f'pair-{pair}/traces').glob(f'*-{source}.csv.gz'):
                with gzip.open(f,'rt') as stream:
                    for r in csv.DictReader(stream):
                        ticks+=1;reasons[r['reason']]+=1
                        if r['submitted']=='True':submitted+=1;proposals[r['proposed_residual']]+=1
        activity[source]=dict(ticks=ticks,submitted=submitted,reasons=dict(reasons),submitted_class_counts=dict(proposals),
            limits='Different controllers visit different physical states; these class histograms are descriptive, not matched-state causal attribution.')
    timing=json.loads((out/'timing/summary.json').read_text());timing_rows=[]
    for seed in (701,802,903):
        folder=out/'timing/fresh_history'/f'seed-{seed}'
        for f in folder.glob('*-ticks.csv'):
            rr=list(csv.DictReader(f.open()));miss=[r for r in rr if r['deadline_miss']=='True']
            timing_rows.append(dict(seed=seed,case=f.stem,ticks=len(rr),misses=len(miss),already_late_at_release=sum(int(r['release_ns'])>=int(r['target_ns'])+10000000 for r in miss),
                max_processing_ms=max(int(r['control_ns']) for r in rr)/1e6,max_thread_cpu_ms=max(int(r['control_cpu_ns']) for r in rr)/1e6))
    result=dict(strata=strata,activity=activity,timing=timing_rows,selection_unchanged=True,
        scope='Post-hoc descriptive development attribution only; no effect-size significance claim with just three paired groups. Mirrored directions are not counted as independent training seeds.')
    (out/'posthoc-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# Descriptive development attribution','',result['scope'],'','| Arm | Speed | Scenario | Gain vs LQR | Gain vs student | Heading change | Rate change |','|---|---:|---|---:|---:|---:|---:|']
    for r in strata:lines.append(f'| {r["source"]} | {r["speed"]} | {r["scenario"]} | {r["gain_vs_lqr_pct"]:+.3f}% | {r["gain_vs_student_pct"]:+.3f}% | {r["heading_change_pct"]:+.2f}% | {r["rate_change_pct"]:+.2f}% |')
    lines+=['','Full gate-reason/class histograms and timing attribution are in posthoc-analysis.json. Nothing in this descriptive breakdown changes the frozen promotion criteria.']
    (out/'posthoc-analysis.md').write_text('\n'.join(lines)+'\n');print('Post-hoc attribution saved; no selection changed.')

if __name__=='__main__':main()
