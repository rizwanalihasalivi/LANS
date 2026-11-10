"""Bind all numerical audits and retain complete raw evidence in bounded ZIPs.

Reuses the tested, standard-library-only byte sealer/restore implementation.
Verification means recorded-data consistency; unsuccessful outcome gates remain
unsuccessful inside the sealed reports.
"""
from pathlib import Path
import argparse,json,platform,shutil,subprocess
from importlib.metadata import version
from tools.unified_control_v9.package import seal,verify,restore,inventory,digest,write_json

ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'results/lans-reliability-v10';OUT=Path(__file__).parent/'evidence'
STAGES={'calibration-v1':704,'cbf-calibration-v1':192,'confirmation-v1':2309,'v2-exposed-development':54,'confirmation-v2':1240,'native-smoke-v1':2,'live-v1':26,'native-validation-v1':28}


def snapshot():
    target=DATA/'final-source';target.mkdir(exist_ok=False)
    files=[*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.md'),*Path(__file__).parent.glob('requirements*.txt'),
        Path(__file__).parent/'RESULTS.json',ROOT/'tools/unified_control_v9/package.py',ROOT/'tools/__init__.py']
    for source in sorted(files):
        d=target/source.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,d)
    models={}
    for actor in (42,43,44):
        folder=ROOT/f'results/python-campaign-v2/policies/seed-{actor}'
        for source in folder.iterdir():
            if source.is_file() and source.suffix in ('.zip','.json'):
                d=DATA/'original-policies'/folder.name/source.name;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,d)
        models[actor]=digest(folder/'policy.zip')
    scripts=DATA/'diagnostic-runners';scripts.mkdir(exist_ok=True)
    for name in ('lans_crossing_reachability_probe.py','lans_v10_restore_diagnostics.py'):
        p=Path('/tmp')/name
        if p.exists():shutil.copyfile(p,scripts/name)
    write_json(DATA/'execution_manifest.json',dict(python=platform.python_version(),platform=platform.platform(),
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        versions={name:version(name) for name in ('numpy','scipy','numba','llvmlite','osqp','clarabel','torch','stable-baselines3','gymnasium')},
        original_policy_sha256=models,policies_changed=False,training_steps=0,
        technical_source_hashes={str(p.relative_to(ROOT)):digest(p) for p in files},
        scope='Complete finite training-only calibration, frozen six-second confirmation, fault/timing diagnostics and twelve-second single-car Webots transfer; no drafts/figures/tables or full-traffic/WCET/universal safety claim.'))


def complete_audit():
    stages={}
    for folder,expected in STAGES.items():
        path=DATA/folder/'independent-verification.json';r=json.loads(path.read_text())
        assert r['passed'] and r['episodes']==expected,(folder,r)
        stages[folder]=dict(status='VERIFIED',episodes=expected,ticks=r['ticks'],report_sha256=digest(path))
    status=json.loads((DATA/'confirmation-v1/STATUS.json').read_text());assert status['complete'] and status['episodes']==2309
    status=json.loads((DATA/'confirmation-v2/STATUS.json').read_text());assert status['completed'] and status['episodes']==1240
    for folder in ('live-v1','native-validation-v1'):
        s=json.loads((DATA/folder/'STATUS.json').read_text());assert s['completed'] and s['episodes']==STAGES[folder]
    paths,_=inventory(DATA,ROOT);hashes={str(p.relative_to(ROOT)):digest(p) for p in paths}
    assert str((DATA/'verification.json').relative_to(ROOT)) not in hashes,'Preserve existing numerical audit'
    report=dict(stages=stages,input_hashes=hashes,verifier_sha256=digest(Path(__file__)),
        all_requested_stages_verified=True,scope='Independent reconstruction and byte consistency; outcome gates are separately reported and are not overridden by this verification.')
    path=DATA/'verification.json';write_json(path,report)
    return dict(path=str(path.relative_to(ROOT)),sha256=digest(path),**{k:report[k] for k in ('stages','input_hashes','verifier_sha256','all_requested_stages_verified')})


def main():
    p=argparse.ArgumentParser(description=__doc__);a=p.add_mutually_exclusive_group();a.add_argument('--verify',action='store_true');a.add_argument('--restore',type=Path)
    p.add_argument('--evidence',type=Path,default=OUT);args=p.parse_args()
    if args.verify:verify(args.evidence)
    elif args.restore is not None:restore(args.evidence,args.restore)
    else:
        assert not args.evidence.exists(),'Preserve previous sealed/partial evidence'
        snapshot();audit=complete_audit();result=seal(DATA,args.evidence,ROOT,audit)
        write_json(Path(__file__).parent/'EVIDENCE_VERIFICATION.json',dict(result,
            seal_sha256=digest(args.evidence/'SEAL.json'),sha256sums_sha256=digest(args.evidence/'SHA256SUMS')))


if __name__=='__main__':main()
