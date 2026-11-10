"""Independently audit both training-only calibration inventories and traces."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import json
from .verify import episode,sha
from .confirm import DATA


def one(job):return episode(job,legacy=True)


def main():
    reports=[]
    for kind,count in [('calibration-v1',704),('cbf-calibration-v1',192)]:
        root=DATA/kind;p=json.loads((root/'plan.json').read_text());jobs=[]
        if kind=='calibration-v1':
            for name,h in p['sources'].items():assert sha(root/'source'/name)==h
            arms=['common-lqr','v8','cached-sync','async-q110-g1075','async-q105-g1075','async-q105-g105']
            for arm in arms:
                for mode in ('lqr',) if arm=='common-lqr' else ('optimized','adaptive'):
                    for c in p['cases']:jobs.append((root/f'{arm}-{mode}-{c["id"]:03d}',c,mode,None,None,None))
        else:
            for name,h in p['source_sha256'].items():assert sha(root/Path(name).name)==h
            for w in p['omegas']:
                for c in p['cases']:
                    path=root/f'{w:g}-{c["id"]:03d}';assert json.loads((path/'summary.json').read_text())['omega']==w
                    jobs.append((path,c,'lqr',None,None,None))
        assert len(jobs)==count and {j[0]/'summary.json' for j in jobs}==set(root.glob('*/summary.json'))
        actual=[json.loads((j[0]/'summary.json').read_text()) for j in jobs]
        order=lambda r:(r.get('arm',''),r.get('omega',0),r['case']['id'],r['mode'])
        assert sorted(actual,key=order)==sorted(json.loads((root/'summary.json').read_text()),key=order)
        with ProcessPoolExecutor(max_workers=4) as pool:results=list(pool.map(one,jobs))
        report=dict(passed=True,episodes=count,ticks=sum(r['ticks'] for r in results),
            checks='independent scalar RK4, actual command FIFO, physical bounds, regenerated packet arrivals/source ages, initial/NPC dynamics and full metrics; exact calibration coverage')
        (root/'independent-verification.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report)
    print(json.dumps(reports),flush=True)


if __name__=='__main__':main()
