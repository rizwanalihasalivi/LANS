"""Lossless, bounded ZIP evidence bundles with exact inventory verification."""
from pathlib import Path
import argparse,hashlib,json,zipfile,zlib,shutil,subprocess

ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'results/v8-four-gates';OUT=Path(__file__).parent/'evidence'
MAX_BYTES=8*1024*1024
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def verify():
    manifest=json.loads((OUT/'manifest.json').read_text());assert manifest['files'] and manifest['archives']
    assert set(manifest['archives'])=={p.name for p in OUT.glob('raw-*.zip')}
    found={};total=0
    for name,record in manifest['archives'].items():
        p=OUT/name;assert sha(p)==record['sha256'] and p.stat().st_size==record['bytes']<=MAX_BYTES
        with zipfile.ZipFile(p) as archive:
            assert archive.testzip() is None
            for info in archive.infolist():
                path=Path(info.filename);assert not path.is_absolute() and '..' not in path.parts
                assert info.filename not in found and info.filename in manifest['files']
                data=archive.read(info);expected=manifest['files'][info.filename]
                assert len(data)==expected['bytes'] and hashlib.sha256(data).hexdigest()==expected['sha256']
                assert expected['archive']==name;found[info.filename]=True;total+=len(data)
    assert set(found)==set(manifest['files']) and total==manifest['raw_bytes']
    result=dict(passed=True,archives=len(manifest['archives']),files=len(found),raw_bytes=total,archive_bytes=sum(p['bytes'] for p in manifest['archives'].values()),scope='byte/coverage/CRC verification, not scientific gate acceptance')
    (OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True);return result


def create():
    assert DATA.exists() and not OUT.exists();OUT.mkdir()
    logs=DATA/'execution-logs';logs.mkdir(exist_ok=False)
    for p in Path('/workspace/lans-setup').glob('four-gates-*.log'):shutil.copyfile(p,logs/p.name)
    policies=DATA/'used-original-policies';policies.mkdir(exist_ok=False)
    for seed in (42,43,44):
        source=ROOT/f'results/python-campaign-v2/policies/seed-{seed}'
        target=policies/str(seed);target.mkdir()
        for name in ('policy.zip','manifest.json'):shutil.copyfile(source/name,target/name)
    files=sorted(p for p in DATA.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    assert len(files)>100 and not any(p.is_symlink() for p in files)
    manifest=dict(base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),files={},archives={},raw_bytes=0,all_four_issues_resolved=False,scope='all development attempts, failures, invalid/interrupted attempts, source snapshots, logs and original policies; no claim of new final validation')
    part=0;archive=None;estimated=0
    def finish():
        nonlocal archive
        if archive is not None:
            name=Path(archive.filename).name;archive.close();p=OUT/name
            assert p.stat().st_size<=MAX_BYTES;manifest['archives'][name]=dict(bytes=p.stat().st_size,sha256=sha(p));archive=None
    for p in files:
        data=p.read_bytes();name=str(p.relative_to(ROOT));size=len(zlib.compress(data,6))+len(name.encode())*2+256
        assert size<MAX_BYTES,(name,size)
        if archive is None or estimated+size>MAX_BYTES:
            finish();part+=1;archive=zipfile.ZipFile(OUT/f'raw-{part:03d}.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6);estimated=128
        archive.writestr(name,data);estimated+=size
        manifest['files'][name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),archive=Path(archive.filename).name);manifest['raw_bytes']+=len(data)
    finish();(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');verify()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    verify() if args.verify else create()
