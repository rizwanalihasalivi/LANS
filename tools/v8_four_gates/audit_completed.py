"""Independent complete-coverage checks for alignment and native development."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import json
from tools.v8_reliability.verify import episode,sha
from tools.v8_reliability.verify_runtime import native


def check(job):return episode(job,legacy=True)


def main():
    root=Path(__file__).resolve().parents[2]/'results/v8-four-gates';reports=[]
    folder=root/'aligned-calibration-v2';plan=json.loads((folder/'plan.json').read_text())
    for n,h in plan['sources'].items():assert sha(folder/'source'/n)==h
    files=list(folder.glob('*/summary.json'));assert len(files)==plan['expected_records']==512
    records=[json.loads(p.read_text()) for p in files];assert {(r['case']['id'],r['arm']) for r in records}=={(c['id'],a) for c in plan['cases'] for a in plan['arms']}
    jobs=[(p.parent,r['case'],r['mode'],0,'aligned',None) for p,r in zip(files,records)]
    with ProcessPoolExecutor(max_workers=4) as pool:results=list(pool.map(check,jobs))
    report=dict(passed=True,cohort=folder.name,episodes=len(results),ticks=sum(r['ticks'] for r in results),scope='independent scalar RK4, wire, FIFO, metrics and complete development coverage')
    (folder/'independent-verification.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report)
    for name in ('native-phase-diagnostics-v1','native-ablation-v1','native-loop-development-v1','native-hotspot-v1','native-scalar-v1','native-scalar-minimized-v1'):
        folder=root/name;files=list(folder.glob('*/summary.json'));expected=2 if name not in ('native-ablation-v1','native-loop-development-v1') else 8 if name=='native-ablation-v1' else 6
        assert len(files)==expected,(name,len(files));planfile=folder/'plan.json'
        if planfile.exists():
            p=json.loads(planfile.read_text())
            for n,h in p.get('source_hashes',p.get('sources',{})).items():assert sha(folder/'source'/n)==h
        ticks=0;functional=True;response_misses=cycles=0
        for p in files:
            s=json.loads(p.read_text());ticks+=native(p.parent,s);functional &= s['completed'] and s['corridor_exceedances']==0 and s['max_measured_rate']<=.6+1e-9
            response_misses+=s['response_misses'];cycles+=s['scheduled_cycle_misses'];meta=p.parent/'loop-metadata.json'
            if meta.exists():
                m=json.loads(meta.read_text())
                if m['compiled_loop']:assert m['measured_native_substeps']==m['expected_native_substeps']==s['ticks']*50
        report=dict(passed=True,cohort=name,episodes=len(files),ticks=ticks,recorded_functional_pass=bool(functional),response_misses=response_misses,scheduled_cycle_misses=cycles,strict_timing_pass=response_misses==cycles==0,scope='independent raw/frame/time/sample-coverage/metric consistency; exposed single-vehicle transfer only; profiling cohorts include instrumentation overhead; no independent rigid-body re-integration or WCET proof')
        (folder/'independent-verification.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report);print(json.dumps(report),flush=True)
    (root/'completed-independent-audit.json').write_text(json.dumps(reports,indent=2)+'\n')


if __name__=='__main__':main()
