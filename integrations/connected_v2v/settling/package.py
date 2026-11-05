"""Archive complete frozen campaigns and retained failures, then verify every byte."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

REPO=Path(__file__).resolve().parents[3]
LIMIT=32*1024*1024
RAW_CHUNK=160*1024*1024


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pack(output,roots,thesis):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    groups={}
    for value in roots:
        root=Path(value).resolve();assert root.is_relative_to(REPO/'results') and root.is_dir()
        files=[(p,str(p.relative_to(REPO))) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo')]
        groups[root.name]=files
    source=Path(__file__).parent
    groups['release-source-thesis']=[(p,'release-source/'+str(p.relative_to(REPO)))
        for p in sorted(source.iterdir()) if p.is_file() and p.suffix in ('.py','.md','.txt')]
    thesis=Path(thesis).resolve()
    groups['release-source-thesis'] += [(p,str(p.relative_to(REPO))) for p in sorted(thesis.rglob('*')) if p.is_file()]
    # Existing setup support is supplementary, not a rewritten execution freeze.
    support=['integrations/webots/run-webots.sh','integrations/webots/install-private.sh',
        'integrations/webots/runtime-sha256.txt','integrations/webots/worlds/vehicle_validation.wbt',
        'docs/thesis/lans-conditional-safety-v1/LANS_Simulation_Conditional_Safety_Thesis.md',
        'docs/research/primary-papers/README.md','docs/research/primary-papers/references.bib']
    groups['release-source-thesis'] += [(REPO/name,'support-source/'+name) for name in support]
    inventory=[]
    def save(label,items):
        name=f'{label}-{len(inventory)+1:03d}.zip';path=output/name
        manifest={n:dict(bytes=p.stat().st_size,sha256=sha(p)) for p,n in items}
        assert len(manifest)==len(items)
        with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p,n in items:z.write(p,n)
            z.writestr('MEMBER-SHA256.json',json.dumps(manifest,sort_keys=True,indent=2)+'\n')
        if path.stat().st_size>=LIMIT:
            path.unlink()
            if len(items)<2:raise RuntimeError('single compressed member exceeds archive limit')
            middle=len(items)//2;save(label,items[:middle]);save(label,items[middle:]);return
        inventory.append(dict(archive=name,bytes=path.stat().st_size,sha256=sha(path),members=len(items)))
    for label,files in groups.items():
        pending=[];size=0
        for p,n in files:
            if pending and size+p.stat().st_size>RAW_CHUNK:
                save(label,pending);pending=[];size=0
            pending.append((p,n));size+=p.stat().st_size
        if pending:save(label,pending)
    (output/'SHA256SUMS').write_text(''.join(f"{x['sha256']}  {x['archive']}\n" for x in inventory))
    (output/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
    lines=['# Complete formation and 2-D trace evidence','',
        'Extract ALL ZIPs into one empty directory. Verify SHA256SUMS and every',
        'MEMBER-SHA256.json with the accompanying package verifier. Archives retain',
        'all raw Python/native control, native 10 ms motion, original wire observations,',
        'generated worlds/controllers, frozen source closures, plans, proof witnesses,',
        'audits, diagnostics, figures and the updated editable thesis.',
        '', 'settling-v4 and settling-native-v4 are the final frozen campaigns.',
        'settling-v1 is the failed first development campaign (71/72), with its exact',
        'frozen execution source. settling-v2 retains its239/240 fresh result and failure;',
        'settling-v3 is aborted partial development. settling-native-v1 retains the',
        'earlier native development only; fresh native data stayed closed at that stage.',
        'settling-native-v2 retains aborted fresh validation:41/42 passed, one overlap.',
        'settling-native-v3 retains79/80 fresh confirmation, one steering/lane failure.',
        'Probe histories are exploratory; where no source was',
        'frozen at execution they do NOT establish exact source-reproducible validation.',
        'Unreachable diagnostics remain ordinary recovery failures, with expected',
        'fail-safe checks reported separately. Old evidence elsewhere is unchanged.',
        '', 'Frozen source directories are the experiment snapshots. release-source adds',
        'later reporting/audit/packaging helpers; their hashes do not replace the',
        'execution-source manifests. Reproduce into NEW output roots.',
        '', '| Archive | Bytes | Members |','| --- | ---: | ---: |']
    lines += [f"| {x['archive']} | {x['bytes']} | {x['members']} |" for x in inventory]
    (output/'INDEX.md').write_text('\n'.join(lines)+'\n')
    return dict(archives=len(inventory),bytes=sum(x['bytes'] for x in inventory))


def verify(output,extract=None):
    output=Path(output);destination=Path(extract) if extract else None
    inventory=json.loads((output/'inventory.json').read_text())
    if not isinstance(inventory,list) or not inventory:
        raise ValueError('nonempty archive inventory required')
    declared={}
    for entry in inventory:
        name=entry['archive']
        if (not isinstance(name,str) or not name.endswith('.zip') or Path(name).name!=name
                or '\\' in name or name in declared):
            raise ValueError('unique local archive filenames required')
        if (type(entry['bytes']) is not int or not 0<entry['bytes']<LIMIT
                or type(entry['members']) is not int or entry['members']<1):
            raise ValueError('positive bounded archive size and member count required')
        declared[name]=entry
    checksums={}
    for line in (output/'SHA256SUMS').read_text().splitlines():
        fields=line.split('  ')
        if len(fields)!=2 or fields[1] in checksums:
            raise ValueError('unique complete archive checksum entries required')
        digest,name=fields;checksums[name]=digest
    if checksums!={name:entry['sha256'] for name,entry in declared.items()}:
        raise ValueError('checksum list differs from archive inventory')
    if {p.name for p in output.glob('*.zip')}!=set(declared):
        raise ValueError('missing or undeclared archive files')
    if destination:destination.mkdir(parents=True,exist_ok=False)
    members=set();archives=0
    for name,entry in declared.items():
        path=output/name
        if sha(path)!=entry['sha256'] or path.stat().st_size!=entry['bytes']:
            raise ValueError('archive digest/size differs from inventory: '+name)
        with zipfile.ZipFile(path) as z:
            if z.testzip() is not None:raise ValueError('archive CRC failure: '+name)
            names=z.namelist()
            if len(names)!=len(set(names)):raise ValueError('duplicate ZIP member')
            manifest=json.loads(z.read('MEMBER-SHA256.json'))
            if (not isinstance(manifest,dict) or not manifest or len(manifest)!=entry['members']
                    or set(names)!=set(manifest)|{'MEMBER-SHA256.json'}):
                raise ValueError('incomplete archive member manifest')
            for member,expected in manifest.items():
                relative=Path(member)
                if (member in members or relative.is_absolute() or '..' in relative.parts
                        or not relative.parts or '\\' in member or relative.as_posix()!=member):
                    raise ValueError('duplicate or unsafe member path')
                members.add(member);data=z.read(member)
                if len(data)!=expected['bytes'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:
                    raise ValueError('member digest/size mismatch: '+member)
                if destination:
                    p=destination/member;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        archives+=1
    return dict(passed=True,archives=archives,ordinary_members=len(members))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=('pack','verify'))
    p.add_argument('--output',required=True);p.add_argument('--root',action='append');p.add_argument('--thesis');p.add_argument('--extract')
    a=p.parse_args();print(json.dumps(pack(a.output,a.root,a.thesis) if a.operation=='pack' else verify(a.output,a.extract),indent=2))
