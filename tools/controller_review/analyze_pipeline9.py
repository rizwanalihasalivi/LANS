"""Post-hoc descriptive attribution, not a new tuning/selection objective."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import numpy as np

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();rows=list(csv.DictReader((a.run/'episodes.csv').open()));groups={}
    for r in rows:
        if r['source'] not in ('student_comp','old_comp','legacy_history','causal_history'):continue
        key=r['source']+'/'+r['scenario'];g=groups.setdefault(key,dict(ticks=0,active=0,submitted=0,reason=Counter(),proposals=Counter(),authority_sum=0.,fresh_ticks=0))
        with np.load(a.run/f'pair-{r["pair"]}/traces'/r['trace'],allow_pickle=False) as d:
            g['ticks']+=len(d['command']);g['active']+=int(np.count_nonzero(d['weight']));g['submitted']+=int(d['submitted'].sum());g['authority_sum']+=float(d['weight'].sum());g['reason'].update(d['reason'].tolist())
            g['fresh_ticks']+=int(np.count_nonzero((d['packet_age_s']>=0)&(d['packet_age_s']<.05)))
            g['proposals'].update(map(str,d['proposed_residual'][d['submitted'].astype(bool)].tolist()))
    for g in groups.values():g['active_fraction']=g['active']/g['ticks'];g['mean_authority']=g['authority_sum']/g['ticks'];g['reason']=dict(g['reason']);g['proposals']=dict(g['proposals'])
    result=dict(scope='Descriptive development traces only; no new parameter selection, oracle actions or reserved data',groups=groups)
    (a.run/'admission-analysis.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
