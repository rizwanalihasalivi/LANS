"""Post-run descriptive uncertainty; no selection or additional training."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--grid',type=Path,required=True)
    args=parser.parse_args()
    rows=list(csv.DictReader((args.grid/'episodes.csv').open()))
    methods=sorted({r['method'] for r in rows})
    mean=lambda data:statistics.mean(float(r['penalized_lateral_rmse_m']) for r in data)
    report={}
    for method in methods:
        seed_means=[];gains=[];regions={}
        for pair in range(3):
            a=[r for r in rows if int(r['pair'])==pair and r['method']==method]
            b=[r for r in rows if int(r['pair'])==pair and r['method']=='lqr']
            value=mean(a);base=mean(b)
            seed_means.append(value);gains.append(100*(base-value)/base)
        for region in sorted({r['scenario'] for r in rows}):
            a=[r for r in rows if r['method']==method and r['scenario']==region]
            b=[r for r in rows if r['method']=='lqr' and r['scenario']==region]
            regions[region]=dict(rmse_m=mean(a),gain_vs_lqr_pct=100*(mean(b)-mean(a))/mean(b),
                                 survived=sum(r['survived']=='True' for r in a),episodes=len(a))
        avg=statistics.mean(gains);std=statistics.stdev(gains)
        half=4.302652729911275*std/math.sqrt(3)
        report[method]=dict(seed_mean_rmse_m=seed_means,paired_seed_gains_pct=gains,
            mean_paired_gain_pct=avg,sd_paired_gain_pct=std,
            descriptive_t95_interval_pct=[avg-half,avg+half],regions=regions)
    result=dict(unit='three training/noise seed blocks; mirrors and ticks are NOT independent replicates',
                limitation='n=3; descriptive t interval assumes independent approximately normal seed-block gains; no significance or broad population guarantee',methods=report)
    (args.grid/'descriptive-uncertainty.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
