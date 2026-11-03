"""Seal raw experiments and logs; do not create manuscript/figure/table artifacts."""
from pathlib import Path
import hashlib,json,zipfile,shutil

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'results/proposal-completion-v6'
OUT=Path(__file__).parent/'evidence'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root):
    return [p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts
            and p.suffix not in ('.pyc','.nbc','.nbi')]


def main():
    assert len(json.loads((DATA/'live-functional/summary.json').read_text()))==9
    # A rejected optimization remains rejected; missing timing is not fabricated.
    assert (DATA/'backend-equivalence/REJECTED_STATUS.json').is_file() or (DATA/'live-functional-fast/summary.json').is_file()
    assert (DATA/'analysis/component_results.json').is_file() and (DATA/'analysis/prediction_ranking.json').is_file()
    assert (DATA/'verification.log').is_file()
    OUT.mkdir(exist_ok=True);logs=DATA/'execution-logs';logs.mkdir(exist_ok=True)
    for p in Path('/workspace/cloud-setup').glob('proposal-v6-*.log'):
        target=logs/p.name
        assert not target.exists() or target.read_bytes()==p.read_bytes()
        shutil.copyfile(p,target)
    parallel=DATA/'parallel-execution';extras=[];aliases=[]
    for directory in (parallel/'working').iterdir():
        completion=json.loads((directory/'completion.json').read_text());kind=completion['job'][0]
        canonical=DATA/('confirmation' if kind=='formal' else 'ablations')
        for p in files(directory):
            target=canonical/p.relative_to(directory)
            if target.exists() and digest(p)==digest(target):
                aliases.append(dict(original=str(p.relative_to(ROOT)),canonical=str(target.relative_to(ROOT)),sha256=digest(p),size=p.stat().st_size))
            else:extras.append(p)
    (parallel/'deduplicated_aliases.json').write_text(json.dumps(aliases,indent=2))
    groups={
        'training-calibration.zip':files(DATA/'calibration'),
        'formal-python-campaign.zip':files(DATA/'confirmation'),
        'component-raw-results.zip':files(DATA/'ablations')+files(DATA/'analysis'),
        'functional-and-execution.zip':files(DATA/'live-functional')+files(DATA/'live-functional-fast')+files(DATA/'backend-equivalence')+files(DATA/'backend-equivalence-attempt-1')+files(DATA/'backend-equivalence-attempt-2')+files(DATA/'backend-equivalence-diagnosis')+files(logs)+[DATA/'verification.log']+extras+
            [p for p in parallel.iterdir() if p.is_file()],
    }
    sums=[]
    for name,members in groups.items():
        target=OUT/name;assert not target.exists(),target
        members=sorted(set(members));manifest={str(p.relative_to(ROOT)):dict(size=p.stat().st_size,sha256=digest(p)) for p in members}
        with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p in members:z.write(p,str(p.relative_to(ROOT)))
            z.writestr('EVIDENCE_MANIFEST.json',json.dumps(dict(version=1,files=manifest),indent=2)+'\n')
        assert target.stat().st_size<50*1024**2,('split archive before Git upload',target)
        sums.append(digest(target)+'  '+name)
        print(name,len(members),'members',round(target.stat().st_size/1024**2,2),'MiB',flush=True)
    (OUT/'SHA256SUMS').write_text('\n'.join(sums)+'\n')
    print('Identical parallel intermediates retained by',len(aliases),'content-verified aliases; not counted as extra trials',flush=True)


if __name__=='__main__':main()
