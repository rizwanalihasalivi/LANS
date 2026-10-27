"""One-command three-actor target-laptop campaign with independent raw replay."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--models',type=Path,default=ROOT/'actor');p.add_argument('--seconds',type=float,default=13.)
    p.add_argument('--profile',choices=['fresh_history'],default='fresh_history');a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    models=a.models.resolve();env=os.environ.copy()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):env[key]='1'
    results=[]
    for seed in (701,802,903):
        folder=out/f'seed-{seed}'
        subprocess.run([sys.executable,str(ROOT/'tools/controller_review/laptop_full_controller.py'),'--models',str(models),'--profile',a.profile,'--seed',str(seed),'--seconds',str(a.seconds),'--output',str(folder)],env=env,check=True)
        subprocess.run([sys.executable,str(ROOT/'tools/controller_review/verify_full_laptop.py'),'--run',str(folder),'--models',str(models)],env=env,check=True)
        summary=json.loads((folder/'summary.json').read_text());assert (folder/'verification.json').exists()
        results.append(dict(seed=seed,summary=summary,nominal_assistance_observed=any(r['case']=='nominal' and r['nonzero_correction_ticks']>0 for r in summary['episodes'])))
    result=dict(scope='Actual machine executing this command; fixed-step software plant only, no physical sensors/actuator or Webots',
        runtime=dict(python=sys.version,platform=platform.platform(),machine=platform.machine(),logical_cpus=os.cpu_count(),dependencies={k:importlib.metadata.version(k) for k in ('numpy','scipy','numba','gymnasium')}),
        profile=a.profile,actor_manifest_sha256=hashlib.sha256((models/'manifest.json').read_bytes()).hexdigest(),
        ticks=sum(e['ticks'] for r in results for e in r['summary']['episodes']),deadline_misses=sum(e['deadline_misses'] for r in results for e in r['summary']['episodes']),
        functional_fallback_pass=all(r['summary']['functional_pass'] for r in results),observed_strict_timing_pass=all(r['summary']['observed_timing_pass'] for r in results),
        nominal_assistance_all_seeds=all(r['nominal_assistance_observed'] for r in results),guaranteed_hard_realtime=False,seeds=results)
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    with zipfile.ZipFile(out/'Results.zip','w',zipfile.ZIP_DEFLATED) as z:
        for f in out.rglob('*'):
            if f.is_file() and f.suffix in ('.json','.csv'):z.write(f,str(f.relative_to(out)))
    with zipfile.ZipFile(out/'Results.zip') as z:assert z.testzip() is None
    print('Saved',out/'Results.zip',flush=True)

if __name__=='__main__':main()
