"""Independent scalar dynamics/FIFO/wire/metric audit of full Python episodes.

The reused auditor imports no controller or simulation-plant implementation.
Coverage is checked against the recorded plan, including every failed run.
"""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import json
from tools.v8_reliability.verify import episode,sha


def check(job):return episode(job,legacy=True)


def main():
    root=Path(__file__).resolve().parents[2]/'results/v8-four-gates';reports=[]
    for name in ('longitudinal-development-v1','pareto-calibration-v1'):
        folder=root/name;plan=json.loads((folder/'plan.json').read_text());sources=plan.get('sources',plan.get('source_hashes',{}))
        for n,h in sources.items():assert sha(folder/'source'/n)==h,(name,n,'frozen source')
        summaries=list(folder.glob('*/summary.json'));assert len(summaries)==plan['expected_records'];jobs=[]
        for p in summaries:
            s=json.loads(p.read_text());jobs.append((p.parent,s['case'],s['mode'],s.get('actor',0),name,None))
        if name.startswith('longitudinal'):
            expected={(c['id'],0.,m,a) for c in plan['cases'] for m in ('lqr','hybrid') for a in ((42,43,44) if m=='hybrid' else (0,))}
            expected|={(c['id'],f,m,a) for c in plan['cases'] for f in plan['frequencies'] for m in ('lqr','optimized','adaptive','hybrid') for a in ((42,43,44) if m=='hybrid' else (0,))}
            records=[json.loads(p.read_text()) for p in summaries];actual={(s['case']['id'],s['frequency'],s['mode'],s['actor']) for s in records};assert actual==expected and len(actual)==len(records)
        else:
            expected={(c['id'],'reference','lqr') for c in plan['cases']}|{(c['id'],arm,m) for c in plan['cases'] for arm in plan['arms'] for m in ('optimized','adaptive')}
            records=[json.loads(p.read_text()) for p in summaries];actual={(s['case']['id'],s['arm'],s['mode']) for s in records};assert actual==expected and len(actual)==len(records)
        with ProcessPoolExecutor(max_workers=4) as pool:results=list(pool.map(check,jobs))
        report=dict(passed=True,episodes=len(results),ticks=sum(r['ticks'] for r in results),plan_sha256=sha(folder/'plan.json'),checks='independent scalar RK4, initial/NPC state regeneration, network arrivals/freshness, actual command FIFO, physical bounds, complete coverage and whole-run metrics',scope='exposed development only, no new final validation or universal safety proof')
        (folder/'independent-verification.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report);print(name,json.dumps(report),flush=True)
    (root/'development-independent-audit.json').write_text(json.dumps(reports,indent=2)+'\n')


if __name__=='__main__':main()
