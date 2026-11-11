"""Archive all sequence-PPO evidence after numerical replay, without sampling."""
from pathlib import Path
import argparse,json,shutil,platform
from importlib.metadata import version
from tools.unified_control_v9.package import seal,verify,restore
from integrations.unified_lans.inference import sha
from .learning import ROOT,DATA
from .probe import dump

OUT=Path(__file__).parent/'evidence'


def main():
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group()
    group.add_argument('--verify',action='store_true');group.add_argument('--restore',type=Path)
    args=parser.parse_args()
    if args.verify:verify(OUT);return
    if args.restore is not None:restore(OUT,args.restore);return
    report=json.loads((DATA/'verification.json').read_text())
    assert report['passed'] and report['all_requested_stages_verified']
    assert report['stages']==dict(training_steps=196608,probe_episodes=192,evaluation_episodes=1080)
    assert sum(r['steps'] for r in report['training'])==196608 and len(report['training'])==6
    assert report['evaluation_episodes']==1080
    assert report['verifier_sha256']==sha(Path(__file__).parent/'verify_learning.py')
    for name,digest in report['input_hashes'].items():assert sha(ROOT/name)==digest,('Input changed since audit',name)
    test_log=Path('/workspace/cloud-setup/ppo-plan-v11-combined-tests.log')
    assert '17 passed' in test_log.read_text(),'Complete the focused checks before packaging'
    logs=DATA/'execution-logs';logs.mkdir(exist_ok=True)
    for path in Path('/workspace/cloud-setup').glob('ppo-plan-v11*.log'):
        if 'package' not in path.name:shutil.copyfile(path,logs/path.name)
    final=DATA/'final-source';final.mkdir(exist_ok=False)
    files=sorted([*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.md')])
    for path in files:
        dest=final/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    dump(DATA/'execution_manifest.json',dict(python=platform.python_version(),versions={n:version(n) for n in
        ('numpy','scipy','torch','stable-baselines3','gymnasium','numba','clarabel')},
        baseline_commit='5eb8ff4cfd808c80090e8ac95649bf53ce3ebbb6',
        final_source_hashes={str(path.relative_to(ROOT)):sha(path) for path in files},
        scope='PPO-only isolated worktree: 192 training-only probe episodes, 196608 actual on-policy transitions with fully replayed analytical reward shadows, 1080 prospective comparison episodes, all seeds and checkpoints, initial BC controls and failed-attempt logs.',
        limitations='Numerical audit success does not imply the ten-percent performance criterion passed. No native transfer or runtime deadline validation for this new sequence policy. External source-pinned v8/v10 dependencies require their original evidence bundles. No presentation artifacts generated.'))
    audit={k:report[k] for k in ('stages','input_hashes','verifier_sha256','all_requested_stages_verified')}
    audit.update(path=str((DATA/'verification.json').relative_to(ROOT)),sha256=sha(DATA/'verification.json'))
    seal(DATA,OUT,ROOT,audit)


if __name__=='__main__':main()
