"""Self-contained data archives with exact member inventory and verification."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


LIMIT=31*1024*1024


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pack(root,report,thesis,output):
    root,report,thesis,output=map(Path,(root,report,thesis,output))
    output.mkdir(parents=True,exist_ok=False)
    plan=json.loads((root/'plan.json').read_text());groups={}
    for profile in plan['profiles']:
        files=[]
        for stage in ('development','validation'):
            for case in sorted((root/stage).glob(profile+'-*')):
                if case.is_dir():files += [(p,str(p.relative_to(root))) for p in sorted(case.rglob('*')) if p.is_file()]
        groups['reference-'+profile]=files
    meta=[(p,str(p.relative_to(root))) for p in sorted(root.rglob('*')) if p.is_file()
        and not any(p.is_relative_to(root/s) and p.parent!=root/s for s in ('development','validation'))]
    for base,prefix in ((report,'report'),(thesis,'thesis')):
        meta += [(p,prefix+'/'+str(p.relative_to(base))) for p in sorted(base.rglob('*')) if p.is_file()]
    package=Path(__file__).parent
    meta += [(p,'release-source/'+str(p.relative_to(package))) for p in sorted(package.iterdir())
        if p.is_file() and p.suffix in ('.py','.md','.txt')]
    groups['metadata-source-thesis']=meta
    inventory=[]
    for label,files in groups.items():
        pending=[];total=0;part=1
        def save(items,index):
            name=f'{label}-{index:02d}.zip';path=output/name
            manifest={name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p,name in items}
            assert len(manifest)==len(items),'duplicate archive member'
            with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
                for p,name in items:z.write(p,name)
                z.writestr('MEMBER-SHA256.json',json.dumps(manifest,sort_keys=True,indent=2)+'\n')
            if path.stat().st_size>=32*1024*1024:raise RuntimeError('archive too large: '+str(path))
            inventory.append((path.name,path.stat().st_size,sha(path),len(items)))
        for p,name in files:
            size=p.stat().st_size
            if pending and total+size>LIMIT:
                save(pending,part);part+=1;pending=[];total=0
            pending.append((p,name));total+=size
        if pending:save(pending,part)
    (output/'SHA256SUMS').write_text(''.join(f'{digest}  {name}\n' for name,size,digest,n in inventory))
    lines=['# Complete conditional-safety evidence','',
        'Extract ALL ZIPs into one empty directory. Archives contain the full 72 development',
        'and 240 fresh reference trajectories, exact execution source, plan, proof SMT-LIB,',
        'audits/negative diagnostics, release/report sources and the thesis draft.',
        'Existing 2-D/Webots evidence remains separately versioned in robustness/evidence.',
        '', '| Archive | Bytes | Members |','| --- | ---: | ---: |']
    lines += [f'| {name} | {size} | {n} |' for name,size,digest,n in inventory]
    lines += ['', 'SHA256SUMS covers outer archives; MEMBER-SHA256.json covers every ordinary member.',
        'The frozen `source` is the actual experiment snapshot; `release-source` adds later',
        'reporting/manuscript/packaging helpers. No experiment source hash was rewritten.']
    (output/'INDEX.md').write_text('\n'.join(lines)+'\n')
    return dict(archives=len(inventory),bytes=sum(z[1] for z in inventory))


def verify(output,extract=None):
    output=Path(output);result=[]
    destination=Path(extract) if extract else None
    if destination:destination.mkdir(parents=True,exist_ok=False)
    all_members=set()
    for line in (output/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ');path=output/name;assert sha(path)==digest
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            manifest=json.loads(z.read('MEMBER-SHA256.json'))
            assert set(z.namelist())==set(manifest)|{'MEMBER-SHA256.json'}
            for member,expected in manifest.items():
                assert member not in all_members,'overlapping archive member';all_members.add(member)
                assert not Path(member).is_absolute() and '..' not in Path(member).parts
                data=z.read(member)
                assert len(data)==expected['bytes'] and hashlib.sha256(data).hexdigest()==expected['sha256']
                if destination:
                    target=destination/member;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            result.append(dict(archive=name,members=len(manifest),verified=True))
    return dict(passed=True,archives=result,ordinary_members=len(all_members))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=('pack','verify'))
    p.add_argument('--output',required=True);p.add_argument('--root');p.add_argument('--report');p.add_argument('--thesis');p.add_argument('--extract')
    a=p.parse_args()
    result=pack(a.root,a.report,a.thesis,a.output) if a.operation=='pack' else verify(a.output,a.extract)
    print(json.dumps(result,indent=2))
