"""Package complete final cohorts and retained development failures without overwrites."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[3]


def tree(path,prefix):
    return [(p,prefix+'/'+str(p.relative_to(path))) for p in sorted(path.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']


def pack(output,label,files):
    archive=None;index=0;hashes=[]
    def finish():
        nonlocal archive,hashes
        if archive is not None:
            archive.writestr('SHA256SUMS','\n'.join(hashes)+'\n');archive.close();archive=None;hashes=[]
    try:
        for source,target in files:
            if archive is None or archive.fp.tell()>=20*1024**2:
                finish();index+=1;dest=output/f'{label}-{index:02d}.zip'
                archive=zipfile.ZipFile(dest,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6)
            raw=source.read_bytes();archive.writestr(target,raw);hashes.append(hashlib.sha256(raw).hexdigest()+'  '+target)
        finish()
    finally:finish()
    print(label,index,'archive(s)',flush=True)


def cohorts(root,prefix):
    summaries={stage:json.loads((root/stage/'summary.json').read_text()) for stage in ('development','validation')}
    cases=sorted({r['case'] for r in summaries['validation']['results']})
    for case in cases:
        files=[]
        for stage,summary in summaries.items():
            for r in summary['results']:
                if r['case']!=case:continue
                name=f"{r['case']}-{r['speed']:g}-{r['seed']}"
                files+=tree(root/stage/name,prefix+'/'+stage+'/'+name)
        yield case,files


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--python',required=True);p.add_argument('--native',required=True);p.add_argument('--report',required=True)
    p.add_argument('--diagnostic');p.add_argument('--output',required=True);p.add_argument('--part',choices=('python','native','diagnostic','metadata','history','supplement','all'),default='all');a=p.parse_args()
    output=Path(a.output);output.mkdir(parents=True,exist_ok=True)
    python,native,report=Path(a.python),Path(a.native),Path(a.report)
    if a.part in ('python','all'):
        for case,files in cohorts(python,'python-final'):pack(output,'python-'+case,files)
    if a.part in ('native','all'):
        for case,files in cohorts(native,'native-final'):pack(output,'native-'+case,files)
    if a.part in ('diagnostic','all') and a.diagnostic:
        for case,files in cohorts(Path(a.diagnostic),'native-150-diagnostic'):pack(output,'diagnostic150-'+case,files)
    if a.part in ('history','all'):
        files=[]
        for name in ['robustness-v1','robustness-v2','robustness-v3','robustness-v4','robustness-v5','robustness-native-v1']:
            root=ROOT/'results'/name
            for meta in ('plan.json','PROTOCOL.md'):
                if (root/meta).exists():files.append((root/meta,'history/'+name+'/'+meta))
            if (root/'source').exists():files+=tree(root/'source','history/'+name+'/source')
            summary=root/'development/summary.json'
            if summary.exists():
                files.append((summary,'history/'+name+'/development/summary.json'))
                for r in json.loads(summary.read_text())['results']:
                    if r['passed']:continue
                    case=f"{r['case']}-{r['speed']:g}-{r['seed']}"
                    files+=tree(root/'development'/case,'history/'+name+'/development/'+case)
        probe=ROOT/'results/robustness-probe-v1'
        if probe.exists():files+=tree(probe,'history/robustness-probe-v1')
        pack(output,'development-history',files)
    if a.part in ('metadata','all'):
        files=[]
        for root,prefix in [(python,'python-final'),(native,'native-final')]:
            for meta in ('plan.json','PROTOCOL.md'):
                if (root/meta).exists():files.append((root/meta,prefix+'/'+meta))
            files+=tree(root/'source',prefix+'/source')
            for stage in ('development','validation'):files.append((root/stage/'summary.json',prefix+'/'+stage+'/summary.json'))
        if a.diagnostic:
            root=Path(a.diagnostic);prefix='native-150-diagnostic'
            files.append((root/'plan.json',prefix+'/plan.json'));files+=tree(root/'source',prefix+'/source')
            for stage in ('development','validation'):files.append((root/stage/'summary.json',prefix+'/'+stage+'/summary.json'))
        files+=tree(report,'report')
        module=Path(__file__).parent
        files += [(f,'review-source/integrations/connected_v2v/robustness/'+f.name) for f in sorted(module.iterdir()) if f.is_file() and f.suffix in ('.py','.md')]
        records=Path('/workspace/lans-setup/robustness-record')
        if records.exists():files+=tree(records,'verification')
        for name in ('install-autonomy.sh','env.sh','installed-versions.txt'):
            path=Path('/workspace/lans-setup')/name
            if path.exists():files.append((path,'environment/'+name))
        for name in ('runtime-sha256.txt','install-private.sh','run-webots.sh','worlds/vehicle_validation.wbt'):
            path=ROOT/'integrations/webots'/name;files.append((path,'environment/webots/'+name))
        pack(output,'metadata',files)
    if a.part in ('supplement','all'):
        name='integrations/connected_v2v/autonomy/native_vehicle.py'
        raw=(ROOT/name).read_bytes();digest=hashlib.sha256(raw).hexdigest()
        prior=ROOT/'integrations/connected_v2v/autonomy/evidence/autonomy-native-final.zip'
        with zipfile.ZipFile(prior) as z:plan_bytes=z.read('native-final/plan.json')
        assert json.loads(plan_bytes)['sources'][name]==digest,'Shared converter changed from its earlier freeze'
        record=Path('/workspace/lans-setup/robustness-supplement');record.mkdir(exist_ok=True)
        (record/'prior-native-plan.json').write_bytes(plan_bytes)
        (record/'dependency.json').write_text(json.dumps(dict(path=name,sha256=digest,
            pinned_by='earlier native-final/plan.json in the already published autonomy-native-final.zip',
            prior_archive_sha256=hashlib.sha256(prior.read_bytes()).hexdigest(),
            note='The shared converter was omitted from the new explicit file list; it was already frozen and remains byte-identical. Original experiment manifests are not rewritten.'),indent=2)+'\n')
        (record/'README.md').write_text('# Reproducibility supplement\n\nThe shared native GPS/body-velocity converter was present throughout execution and pinned by the earlier autonomy native source freeze. It was omitted from the newer explicit dependency list. This archive supplies the byte-identical pre-study file in each extracted source tree. Existing experiment manifests and outcomes are unchanged. dependency.json and prior-native-plan.json show the prior pin. Full Git checkouts already contain the file.\n')
        files=tree(record,'reproducibility')
        for prefix in ('python-final','native-final','native-150-diagnostic'):
            files.append((ROOT/name,prefix+'/source/'+name))
        pack(output,'reproducibility-supplement',files)
    zips=sorted(output.glob('*.zip'))
    assert all(z.stat().st_size<32*1024**2 for z in zips),'Archive shard exceeds 32 MiB'
    (output/'SHA256SUMS').write_text(''.join(hashlib.sha256(z.read_bytes()).hexdigest()+'  '+z.name+'\n' for z in zips))
    lines=['# Evidence archive index','',
           'Extract all final Python/native shards plus metadata into the same directory. Each ZIP has its own per-file SHA256SUMS; the outer checksum file covers ZIP bytes. No runtime binaries are vendored.','',
           'History shards retain all prior cohort summaries/source freezes and failed-trial raw data. Complete successful preliminary raw data also remains in the prepared local environment; full final cohorts (all seeds) are in the final shards.','',
           '| Archive | Size (MiB) |','| --- | --- |']
    lines += [f'| [{z.name}]({z.name}) | {z.stat().st_size/1024**2:.2f} |' for z in zips]
    (output/'INDEX.md').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':main()
