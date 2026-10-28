"""Guarded cloud resume entry: pinned packages, single runner, frozen v12 pipeline."""
import argparse
import fcntl
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT/'docs/research/ppo-audit-v12'


def check_environment():
    expected = json.loads((RUN/'software-environment.json').read_text())
    if sys.version != expected['python'] or platform.machine() != expected['architecture']:
        raise RuntimeError('Restore the recorded Python and CPU architecture before exact checkpoint resume')
    for name, version in expected['packages'].items():
        actual = importlib.metadata.version(name)
        if actual != version:
            raise RuntimeError(f'Restore pinned package {name}=={version}; found {actual}')


def verify_completed():
    manifest = json.loads((RUN/'manifest.json').read_text())
    for name, expected in manifest['inputs'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected, name
    seal = json.loads((RUN/'evidence-hashes.json').read_text())
    for name, expected in seal['sha256'].items():
        assert hashlib.sha256((RUN/name).read_bytes()).hexdigest() == expected, name
    print(f'Verified {len(manifest["inputs"])} frozen inputs and {len(seal["sha256"])} evidence files.')


def repair_verification_if_ready():
    ready = all((RUN/f'pair-{pair}/complete.json').exists() for pair in range(3))
    if ready and not (RUN/'decision.json').exists():
        with (RUN/'verification-corrected.log').open('w') as f:
            subprocess.run([sys.executable, str(ROOT/'tools/controller_review/verify_development12.py')],
                           cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True)
        return True
    return False


def annotate_report():
    file = RUN/'README.md'
    marker = '\n## Supplemental audit and guarded resume\n'
    body = file.read_text().split(marker)[0]
    supplemental = '''

The initial frozen verifier stopped on NumPy boolean subtraction; `verification.log` preserves that failure.
The corrected verifier compares boolean/integer fields exactly and keeps the same1e-11floating tolerance.
All original episodes, models and acceptance criteria are preserved. See `verifier-repair.json` and `verification-corrected.log`.

Actual checkpoint verification replays steps10,000–20,000 in a separate process and exactly matches actor/critic,
Adam, full environment/queue, normalization and Python/NumPy/Torch RNG. This is verification work, not an extra selected endpoint.
See `resume-replay.json`. Detailed source review is in `semantic-review.md`; software requirements are in `software-environment.json`.

The preferred cloud resume command checks software versions and prevents concurrent guarded runners:

```bash
/workspace/lans-venv/bin/python tools/controller_review/resume_ppo_audit12.py --publish
```

Use `--verify-only` to check completed source/evidence hashes without training or evaluation.
The finite training budget remains exhausted. Work since the last committed10k-step snapshot may be replayed after interruption.
'''
    branch_file = RUN/'prediction-branches.json'
    if branch_file.exists():
        diagnostic = json.loads(branch_file.read_text())
        supplemental += '\nA separate posthoc v11 branch audit checks one packet’s planned assistance until expiry followed by LQR continuation. '
        supplemental += 'Its nonlinear software plant, estimator and future recorded noise differ from the nominal predictor. '
        supplemental += 'These are conditional diagnostic samples, not population error rates or a deployable oracle.\n\n'
        supplemental += '| State group | Samples | Physical cost benefit >0.1% | Physical cost harm >0.1% |\n|---|---:|---:|---:|\n'
        for name, stats in diagnostic['groups'].items():
            supplemental += f'| {name} | {stats["samples"]} | {stats["physical_benefit_above_01pct"]} | {stats["physical_harm_above_01pct"]} |\n'
        supplemental += '\nThis supports investigating prediction/estimation mismatch jointly; it does not isolate either cause or justify bypassing the supervisor.\n'
    file.write_text(body+marker+supplemental)
    (RUN/'RESUME.md').write_text('# Completed v12 audit\n\n'
        'Read README.md and semantic-review.md for outcomes and limitations. No controller is promoted; reserved tests remain unopened.\n\n'
        'Preferred cloud command: `/workspace/lans-venv/bin/python tools/controller_review/resume_ppo_audit12.py --publish`\n\n'
        'This checks the pinned software, serializes guarded runs, restores verified checkpoints and completed episodes, '
        'uses the corrected typed verifier and preserves failed trials. Add `--verify-only` for hash verification. '
        'The finite300k-step budget is exhausted; no extra training starts.\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    check_environment()
    lock_name = 'lans-v12-'+hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]+'.lock'
    with (Path('/tmp')/lock_name).open('a+') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError('The guarded v12 pipeline is already running; inspect status.json')
        if args.verify_only:
            verify_completed()
            return 0
        # The frozen initial verifier attempted NumPy boolean subtraction.
        # Preserve it and its failure log; the corrected verifier below changes
        # only typed equality, never raw episodes, models, tolerances or criteria.
        repair_verification_if_ready()
        command = [sys.executable, str(ROOT/'tools/reviewer_v12/run12.py')]
        if args.publish: command.append('--publish')
        result = subprocess.run(command, cwd=ROOT).returncode
        # A first uninterrupted run may reach the retained historical verifier
        # after the initial ready check; repair that known failure in this command.
        log = RUN/'verification.log'
        known_failure = log.exists() and 'numpy boolean subtract' in log.read_text()
        if result == 1 and known_failure and repair_verification_if_ready():
            result = subprocess.run(command, cwd=ROOT).returncode
        if result not in (0, 2): return result
        verify_completed()
        annotate_report()
        if args.publish:
            helpers = ['resume_ppo_audit12.py', 'verify_development12.py', 'verify_checkpoint12.py', 'audit_prediction12.py']
            files = [str(ROOT/'tools/controller_review'/name) for name in helpers]
            files += [str(RUN/name) for name in ('README.md', 'RESUME.md', 'semantic-review.md')]
            subprocess.run(['git', 'add', '--', *files], cwd=ROOT, check=True)
            if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=ROOT).returncode:
                subprocess.run(['git', 'commit', '--quiet', '-m', 'Document typed verifier repair and guarded cloud resume without changing experiment evidence'], cwd=ROOT, check=True)
            subprocess.run(['git', '-c', 'credential.helper=!gh auth git-credential', 'push', 'origin', 'reports/opening-report-2026-10-26'], cwd=ROOT, check=True)
        return result


if __name__ == '__main__': sys.exit(main())
