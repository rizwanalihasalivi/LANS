"""Seal PPO-specific raw evidence using the repository's bounded byte archives."""
from pathlib import Path
import argparse,json,shutil,platform
from importlib.metadata import version
from tools.unified_control_v9.package import seal,verify,restore
from integrations.unified_lans.inference import sha
from .core import ROOT,DATA,dump

OUT=Path(__file__).parent/'evidence'


def main():
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group()
    group.add_argument('--verify',action='store_true');group.add_argument('--restore',type=Path)
    args=parser.parse_args()
    if args.verify:verify(OUT);return
    if args.restore is not None:restore(OUT,args.restore);return
    report=json.loads((DATA/'verification.json').read_text())
    assert report['all_requested_checks_passed'] and report['evaluation']['episodes']==864
    assert sum(p['steps'] for p in report['training'])==49152
    for name,digest in report['input_hashes'].items():assert sha(ROOT/name)==digest,('Input changed since audit',name)
    assert report['verifier_sha256']==sha(Path(__file__).parent/'verify.py')
    logs=DATA/'execution-logs';logs.mkdir(exist_ok=True)
    for path in Path('/workspace/cloud-setup').glob('ppo-benefit-v10*.log'):
        if 'package' not in path.name:shutil.copyfile(path,logs/path.name)
    final=DATA/'final-source';final.mkdir(exist_ok=False)
    for path in [*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.md')]:
        dest=final/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    dump(DATA/'execution_manifest.json',dict(python=platform.python_version(),versions={n:version(n) for n in
        ('numpy','scipy','torch','stable-baselines3','gymnasium','numba','clarabel')},
        source_commit='63c086ff08dafc3e1c2e3cd0b6175c53ad630435',scope='PPO-only independent worktree; all endpoints and failed attempts retained.'))
    audit={k:report[k] for k in ('stages','input_hashes','verifier_sha256','all_requested_stages_verified')}
    audit.update(path=str((DATA/'verification.json').relative_to(ROOT)),sha256=sha(DATA/'verification.json'))
    seal(DATA,OUT,ROOT,audit)


if __name__=='__main__':main()
