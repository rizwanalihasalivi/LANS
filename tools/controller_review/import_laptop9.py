"""Treat supplied laptop files as untrusted data and replay against frozen actors."""
import argparse
import csv
import hashlib
import json
from pathlib import Path,PurePosixPath
import shutil
import subprocess
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--results',type=Path,required=True);a=p.parse_args();out=a.run/'target-laptop';out.mkdir(exist_ok=False)
    if a.results.is_file():
        with zipfile.ZipFile(a.results) as z:
            items=z.infolist();assert len(items)<1000 and sum(i.file_size for i in items)<200_000_000
            for item in items:
                path=PurePosixPath(item.filename);assert not path.is_absolute() and '..' not in path.parts and '\\' not in item.filename
                assert (item.external_attr>>16)&0o170000!=0o120000
                if item.is_dir():continue
                assert path.suffix in ('.csv','.json')
                dest=out.joinpath(*path.parts);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(item))
    else:
        for f in a.results.rglob('*'):
            if f.is_file() and f.suffix in ('.json','.csv'):
                assert not f.is_symlink();dest=out/f.relative_to(a.results);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
    summary=json.loads((out/'summary.json').read_text());protocol=json.loads((out/'protocol.json').read_text());decision=json.loads((a.run/'decision.json').read_text());models=a.run/'runtime-actors'/(decision['selected'] or 'legacy_history')
    assert protocol['model_manifest_sha256']==hashlib.sha256((models/'manifest.json').read_bytes()).hexdigest()
    bundle=a.run/'LANS_Causal_Python310_Kit/bundle-manifest.json';assert protocol['bundle_sha256']==hashlib.sha256(bundle.read_bytes()).hexdigest()
    assert protocol['seconds']==13 and protocol['budget_guard'] is True and protocol['seeds']==[701,802,903]
    platform=summary['runtime']['platform'];assert platform.startswith(('Windows','macOS','Darwin')),'Expected participant Windows/macOS target, not cloud Linux smoke'
    misses=0;ticks=0
    for seed in protocol['seeds']:
        folder=out/f'seed-{seed}';episodes=json.loads((folder/'summary.json').read_text())['episodes'];assert len(episodes)==5
        for episode in episodes:
            rows=list(csv.DictReader((folder/(episode['case']+'-ticks.csv')).open()));assert len(rows)==1300
            ticks+=len(rows);misses+=sum(int(r['apply_ns'])>int(r['target_ns'])+10000000 for r in rows)
    subprocess.run([sys.executable,str(ROOT/'tools/controller_review/verify_timing9.py'),'--run',str(out),'--target','--models',str(models)],check=True)
    result=dict(ticks=ticks,deadline_misses=misses,observed_strict_timing_pass=misses==0,platform=platform,source='Participant supplied raw data, independently replayed; no hardware attestation',physical_validation=False)
    (out/'import-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
