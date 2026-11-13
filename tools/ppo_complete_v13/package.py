"""Byte-preserving bounded V13 evidence archives, after complete numerical audit.

Performance failure is retained and never prevents honest evidence preservation;
missing or invalid registered evidence does prevent a completed evidence seal.
Offline --verify/--restore use the generic archive verifier, without an ML stack.
"""
from pathlib import Path
import argparse
import json
import platform
import shutil
from importlib.metadata import version

from tools.unified_control_v9.package import seal, verify, restore, digest, inventory, check_audit_inputs

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT/'results/ppo-complete-v13'
OUT = Path(__file__).parent/'evidence'
STAGES = dict(safety=('episodes', 288), teacher=('episodes', 144), dataset=('samples', 8640),
    training=('steps', 196608), validation=('episodes', 864), final=('episodes', 1728),
    runtime=('episodes', 180), native=('episodes', 120))


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def complete_audit(data=DATA, root=ROOT):
    path = data/'verification.json'
    report = read(path)
    assert report['passed'] and report['all_requested_stages_verified'], 'Complete all8 registered numerical audit stages first'
    assert set(report['stages']) == set(STAGES)
    for name, (field, count) in STAGES.items():
        stage = report['stages'][name]
        assert stage['status'] == 'VERIFIED' and stage[field] == count, ('Incomplete stage', name, stage)
    assert report['stages']['training']['shadow_steps'] == 196608
    assert all(check['status'] == 'VERIFIED' for check in report['required_checks'].values())
    assert set(report['required_checks']) == {'focused_tests', 'actuator_calibration', 'completion_qualification_record'}
    assert report['verifier_sha256'] == digest(root/'tools/ppo_complete_v13/verify.py')
    check_audit_inputs(report, root)
    # A correctly audited negative performance result is still complete evidence.
    qualification = read(data/'completion/qualification.json')
    assert report['overall_qualified'] == qualification['overall_qualified']
    assert report['overall_mean_target_qualified'] == qualification['overall_mean_target_qualified']
    return dict(path=str(path.relative_to(root)), sha256=digest(path),
        stages=report['stages'], input_hashes=report['input_hashes'], verifier_sha256=report['verifier_sha256'],
        all_requested_stages_verified=True, overall_qualified=report['overall_qualified'],
        overall_mean_target_qualified=report['overall_mean_target_qualified'],
        all_training_controller_queries_replayed=report['all_training_controller_queries_replayed'])


def retain_file(source, target):
    """Preserve changed earlier log versions instead of overwriting failures."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and digest(target) != digest(source):
        target = target.with_name(target.stem+'-'+digest(source)[:12]+target.suffix)
    if not target.exists():
        shutil.copyfile(source, target)
    assert digest(source) == digest(target)
    return target


def snapshot(data=DATA, root=ROOT, log_root=Path('/workspace/cloud-setup')):
    assert not (data/'final-source').exists(), 'Preserve an existing final snapshot; do not overwrite a prior packaging attempt'
    logs = data/'execution-logs'
    logs.mkdir(exist_ok=True)
    saved_logs = []
    for source in sorted(log_root.glob('*v13*.log')):
        if 'package' in source.name:
            continue  # Packaging output is self-referential, not experimental evidence.
        saved_logs.append(retain_file(source, logs/source.name))
    files = sorted([*root.joinpath('tools/ppo_complete_v13').glob('*.py'),
        *root.joinpath('tools/ppo_complete_v13').glob('*.md'),
        *root.joinpath('tools/ppo_complete_v13/native_assets').glob('*.py'),
        root/'tools/unified_control_v9/package.py'])
    final = data/'final-source'
    final.mkdir()
    for source in files:
        assert source.is_file() and not source.is_symlink()
        target = final/source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    members, skipped = inventory(data, root)
    write(data/'execution_manifest.json', dict(python=platform.python_version(), versions={name: version(name) for name in
        ('numpy', 'scipy', 'numba', 'llvmlite', 'torch', 'stable-baselines3', 'gymnasium', 'clarabel', 'osqp')},
        final_source_hashes={str(p.relative_to(root)): digest(p) for p in files},
        retained_execution_logs={str(p.relative_to(root)): digest(p) for p in saved_logs},
        evidence_files_before_manifest=len(members), skipped=skipped,
        scope='288 opened shared-safety regressions;144 opened teacher episodes;8640 causal teacher frames;196608 actual PPO and shadow steps; '
            '864 validation and1728 untouched-final Python episodes;180 observed-runtime episodes;120 representative physical Webots episodes. '
            'Every actor/checkpoint, source snapshot, proposal/observation/physics trace and retained failed development/native/calibration attempt remains.',
        limitations='Evidence audit success is separate from qualified performance; retain overall_qualified as recorded. '
            'Native coverage is24 prespecified fixtures, not all144 final cases, and observed runtime is not WCET. '
            'Generated caches and symlinks are excluded with metadata; no figures, presentation tables or CSV artifacts. '
            'Historical v10/v11/v12 dependencies remain separately sealed and source/hash pinned; no symlink target is silently copied.'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--verify', action='store_true')
    group.add_argument('--restore', type=Path)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    if args.verify:
        verify(args.out)
        return
    if args.restore is not None:
        restore(args.out, args.restore)
        return
    audit = complete_audit()
    assert not args.out.exists(), 'Refusing to overwrite a previous evidence/packaging attempt'
    snapshot()
    result = seal(DATA, args.out, ROOT, audit)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
