"""Seal raw experiments and execution logs; verify every archive member."""
from pathlib import Path
import argparse,hashlib,json,platform,shutil,zipfile
from importlib.metadata import version

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'results/causal-v8'
OUT=Path(__file__).parent/'evidence'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root):
    return [p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts
            and p.suffix not in ('.pyc','.nbc','.nbi')]


def verify():
    lines=(OUT/'SHA256SUMS').read_text().splitlines();assert len(lines)==3
    total=0
    for line in lines:
        expected,name=line.split(maxsplit=1);target=OUT/name
        assert digest(target)==expected and target.stat().st_size<50*1024**2
        with zipfile.ZipFile(target) as archive:
            manifest=json.loads(archive.read('EVIDENCE_MANIFEST.json'))['files']
            assert len(archive.namelist())==len(set(archive.namelist()))
            assert set(archive.namelist())==set(manifest)|{'EVIDENCE_MANIFEST.json'}
            assert archive.testzip() is None
            for member,record in manifest.items():
                assert not Path(member).is_absolute() and '..' not in Path(member).parts
                data=archive.read(member)
                assert len(data)==record['size'] and hashlib.sha256(data).hexdigest()==record['sha256']
            total+=len(manifest)
        print(name,'outer SHA256,',len(manifest),'member hashes/sizes and ZIP CRCs PASS',flush=True)
    print('VERIFIED',total,'archived members across three archives',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    if args.verify:verify();return
    verification=Path('/workspace/cloud-setup/causal-v8-verification.log')
    assert 'VERIFIED: 1431 simulation episodes and 9 functional checks' in verification.read_text()
    tests=Path('/workspace/cloud-setup/causal-v8-focused-tests.log')
    assert '100 passed' in tests.read_text()
    assert (DATA/'confirmation/requested_target.json').is_file()
    OUT.mkdir(exist_ok=True);logs=DATA/'execution-logs';logs.mkdir(exist_ok=True)
    for path in Path('/workspace/cloud-setup').glob('causal-v8-*.log'):
        if 'package' not in path.name:shutil.copyfile(path,logs/path.name)
    shutil.copyfile(verification,DATA/'verification.log')
    info=dict(python=platform.python_version(),versions={name:version(name) for name in
        ['numpy','scipy','numba','llvmlite','osqp','clarabel','torch','stable-baselines3','gymnasium']},
        analysis_source_hashes={str(p.relative_to(ROOT)):digest(p) for p in
            [Path(__file__),Path(__file__).parent/'campaign.py',Path(__file__).parent/'verify.py']},
        scope='1431 new simulation episodes (576 calibration, 848 prospective, 7 known-case regressions), and 9 functional checks. No discarded outcomes.')
    (DATA/'execution_manifest.json').write_text(json.dumps(info,indent=2)+'\n')
    groups={
        'training-calibration.zip':files(DATA/'calibration'),
        'prospective-comparison.zip':files(DATA/'confirmation'),
        'regression-and-functional.zip':files(DATA/'conflict-regression')+files(DATA/'live-functional')+
            files(logs)+[p for p in DATA.iterdir() if p.is_file()],
    }
    sums=[]
    for name,members in groups.items():
        target=OUT/name;assert not target.exists(),target
        members=sorted(set(members))
        assert not any(p.suffix.lower() in ('.pdf','.png','.svg','.csv','.docx','.pptx') for p in members)
        manifest={str(p.relative_to(ROOT)):dict(size=p.stat().st_size,sha256=digest(p)) for p in members}
        with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
            for path in members:archive.write(path,str(path.relative_to(ROOT)))
            archive.writestr('EVIDENCE_MANIFEST.json',json.dumps(dict(version=1,files=manifest),indent=2)+'\n')
        assert target.stat().st_size<50*1024**2
        sums.append(digest(target)+'  '+name)
        print(name,len(members),'members',round(target.stat().st_size/1024**2,2),'MiB',flush=True)
    (OUT/'SHA256SUMS').write_text('\n'.join(sums)+'\n')
    verify()


if __name__=='__main__':main()
