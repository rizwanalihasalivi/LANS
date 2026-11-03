"""Archive raw diagnostics and audit records; never export thesis assets."""
from pathlib import Path
import argparse,hashlib,json,shutil,zipfile

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent/'evidence'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    lines=(OUT/'SHA256SUMS').read_text().splitlines();assert len(lines)==1
    expected,name=lines[0].split(maxsplit=1);target=OUT/name
    assert digest(target)==expected
    with zipfile.ZipFile(target) as z:
        manifest=json.loads(z.read('EVIDENCE_MANIFEST.json'))['files']
        assert len(z.namelist())==len(set(z.namelist()))
        assert set(z.namelist())==set(manifest)|{'EVIDENCE_MANIFEST.json'}
        assert z.testzip() is None
        for member,record in manifest.items():
            assert not Path(member).is_absolute() and '..' not in Path(member).parts
            data=z.read(member)
            assert len(data)==record['size'] and hashlib.sha256(data).hexdigest()==record['sha256']
    print('Outer SHA256, all',len(manifest),'member hashes/sizes and ZIP CRCs PASS',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    if args.verify:verify();return
    from importlib.metadata import version
    roots=[ROOT/'results/thirty-percent-headroom',ROOT/'results/thirty-percent-conic']
    OUT.mkdir(exist_ok=True);logs=roots[0]/'execution-logs';logs.mkdir(exist_ok=True)
    for path in Path('/workspace/cloud-setup').glob('thirty-percent-*.log'):
        shutil.copyfile(path,logs/path.name)
    versions={name:version(name) for name in ['numpy','scipy','numba','llvmlite','osqp','clarabel']}
    (roots[0]/'runtime_versions.json').write_text(json.dumps(versions,indent=2))
    shutil.copyfile(Path('/workspace/cloud-setup/thirty-percent-verification.log'),roots[0]/'verification.log')
    files=sorted({p for r in roots for p in r.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.nbi','.nbc')})
    assert not any(p.suffix.lower() in ('.pdf','.png','.svg','.csv','.docx','.pptx') for p in files)
    manifest={str(p.relative_to(ROOT)):dict(size=p.stat().st_size,sha256=digest(p)) for p in files}
    target=OUT/'raw-thirty-percent-diagnostics.zip';assert not target.exists()
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,str(p.relative_to(ROOT)))
        z.writestr('EVIDENCE_MANIFEST.json',json.dumps(dict(version=1,files=manifest),indent=2)+'\n')
    assert target.stat().st_size<50*1024**2
    (OUT/'SHA256SUMS').write_text(digest(target)+'  '+target.name+'\n')
    print(len(files),'raw/provenance members,',round(target.stat().st_size/1024**2,2),'MiB',flush=True)
    verify()


if __name__=='__main__':main()
