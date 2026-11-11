"""Byte-preserving evidence archives for the registered exploration study."""
from pathlib import Path
import argparse,json,shutil,platform
from importlib.metadata import version
from tools.unified_control_v9.package import seal,verify,restore
from integrations.unified_lans.inference import sha
from tools.ppo_plan_v11.probe import dump
from .train import ROOT,DATA,V11

OUT=Path(__file__).parent/'evidence'


def main():
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group()
    group.add_argument('--verify',action='store_true');group.add_argument('--restore',type=Path)
    args=parser.parse_args()
    if args.verify:verify(OUT);return
    if args.restore is not None:restore(OUT,args.restore);return
    report=json.loads((DATA/'verification.json').read_text())
    assert report['passed'] and report['all_requested_stages_verified']
    assert report['stages']==dict(training_steps=196608,evaluation_episodes=1008)
    assert sum(r['steps'] for r in report['training'])==196608 and len(report['training'])==3
    assert report['verifier_sha256']==sha(Path(__file__).parent/'verify.py')
    for name,digest in report['input_hashes'].items():assert sha(ROOT/name)==digest,('Input changed since audit',name)
    test_log=Path('/workspace/cloud-setup/ppo-explore-v12-final-tests.log')
    assert '21 passed' in test_log.read_text(),'Finish the combined functional checks before packaging'
    logs=DATA/'execution-logs';logs.mkdir(exist_ok=True)
    for path in Path('/workspace/cloud-setup').glob('ppo-explore-v12*.log'):
        if 'package' not in path.name:shutil.copyfile(path,logs/path.name)
    final=DATA/'final-source';final.mkdir(exist_ok=False)
    files=sorted([*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.md')])
    for path in files:
        dest=final/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    dump(DATA/'execution_manifest.json',dict(python=platform.python_version(),versions={n:version(n) for n in
        ('numpy','scipy','torch','stable-baselines3','gymnasium','numba','clarabel')},
        final_source_hashes={str(path.relative_to(ROOT)):sha(path) for path in files},
        v11_dependency_assessment_sha256=sha(V11/'damped-evaluation/assessment.json'),
        scope='196608 genuine wider-exploration PPO transitions and full analytical reward shadows; 1008 new prospective episodes; all three seeds and checkpoints; initial BC, corrected v11 and existing scalar PPO controls; no shared controller changes.',
        limitations='Replay success is distinct from performance promotion. No native transfer or actual deadline certification. Restore the v10/v11 policy evidence dependencies. No presentation artifacts.'))
    audit={k:report[k] for k in ('stages','input_hashes','verifier_sha256','all_requested_stages_verified')}
    audit.update(path=str((DATA/'verification.json').relative_to(ROOT)),sha256=sha(DATA/'verification.json'))
    seal(DATA,OUT,ROOT,audit)


if __name__=='__main__':main()
