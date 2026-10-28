"""Single-command resumable audit, finite training, full comparison and publication."""
import boot12
import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import torch
from checkpoint12 import atomic_json, digest

ROOT, HERE = boot12.ROOT, boot12.HERE


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    out = ROOT/'docs/research/ppo-audit-v12'; out.mkdir(parents=True, exist_ok=True)
    protocol = json.loads((HERE/'protocol.json').read_text())
    frozen = subprocess.check_output(['git', 'show', protocol['parent_commit']+':docs/research/reviewer-training-v11/evidence-hashes.json'], cwd=ROOT)
    prior = ROOT/'docs/research/reviewer-training-v11'
    assert frozen == (prior/'evidence-hashes.json').read_bytes()
    prior_inputs = json.loads((prior/'manifest.json').read_text())['hashes']
    inputs = dict(prior_inputs)
    for name, expected in prior_inputs.items(): assert digest(ROOT/name) == expected, name
    for name, expected in json.loads(frozen)['sha256'].items():
        assert digest(prior/name) == expected, name
    inputs.update({str(f.relative_to(ROOT)): digest(f) for f in HERE.iterdir() if f.is_file()})
    inputs.update({str((prior/name).relative_to(ROOT)): expected for name, expected in json.loads(frozen)['sha256'].items()
                   if name.endswith(('policy.zip', 'reward-normalization.pkl')) or name.startswith('actors/')})
    manifest = dict(inputs=inputs, parent_evidence_sha256=digest(prior/'evidence-hashes.json'))
    if (out/'manifest.json').exists(): assert json.loads((out/'manifest.json').read_text()) == manifest, 'Frozen source/model inputs changed'
    else: atomic_json(out/'manifest.json', manifest)
    signature = digest(out/'manifest.json')

    def status(stage, state='running'):
        atomic_json(out/'status.json', dict(stage=stage, state=state, signature=signature,
            resume='/workspace/lans-venv/bin/python tools/reviewer_v12/run12.py --publish'))

    def publish(message):
        if not args.publish: return
        files = [str(f.relative_to(ROOT)) for folder in (out, HERE) for f in folder.rglob('*')
                 if f.is_file() and '__pycache__' not in f.parts and '.partial-' not in str(f) and '.tmp-' not in str(f)
                 and f.suffix not in ('.pyc', '.nbi', '.nbc')]
        subprocess.run(['git', 'add', '-f', '--', *files], cwd=ROOT, check=True)
        if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=ROOT).returncode:
            subprocess.run(['git', 'commit', '--quiet', '-m', message], cwd=ROOT, check=True)
        subprocess.run(['git', '-c', 'credential.helper=!gh auth git-credential', 'push', 'origin',
                        'reports/opening-report-2026-10-26'], cwd=ROOT, check=True)

    def run(command, logfile):
        with (out/logfile).open('w') as f:
            subprocess.run([str(x) for x in command], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True)

    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    if not (out/'contracts-passed.json').exists():
        status('contracts')
        suites = [('new', HERE/'test12.py'), ('packets-terminal', ROOT/'tools/reviewer_v10/test10.py'),
                  ('credit', ROOT/'tools/reviewer_v6/test6.py'), ('recovery', ROOT/'tools/reviewer_v8/test8.py'),
                  ('causal-abi', ROOT/'tools/reviewer_v9/test9.py')]
        for name, script in suites: run([sys.executable, script, '-v'], f'contracts-{name}.log')
        atomic_json(out/'contracts-passed.json', dict(suites=[name for name, _ in suites], all_passed=True))
    if not (out/'forecast-numerics.json').exists():
        run([sys.executable, HERE/'numerics12.py', '--output', out/'forecast-numerics.json'], 'numerics.log')
    if not (out/'diagnosis.json').exists():
        run([sys.executable, HERE/'diagnose12.py', '--output', out], 'diagnosis.log')
    if not (out/'inventory.json').exists():
        run([sys.executable, ROOT/'tools/reviewer_v10/inventory10.py', '--output', out/'inventory.json'], 'inventory.log')
    publish('Freeze tested v12 audit fixes and finite two-arm exploration protocol')
    from train12 import train
    for arm in protocol['training']['arms']:
        for pair in range(3):
            folder = out/f'{arm}-{pair}'
            status(f'training:{arm}:{pair}')
            # Loading verifies committed checkpoint hashes even on a completed stage.
            train(pair, arm, folder, signature, publish=publish)
            publish(f'Complete v12 {arm} pair {pair} training endpoint')
    if not (out/'actors/manifest.json').exists():
        status('export')
        from export12 import main as export
        export(out)
        publish('Verify six v12 training exports against single-row Torch inference')
    status('matched-development')
    def evaluate(pair):
        # The episode runner checks and skips each complete trace; no silent partial retry.
        if not (out/f'pair-{pair}/complete.json').exists():
            run([sys.executable, HERE/'study12.py', '--run', out, '--pair', pair], f'pair-{pair}.log')
        return pair
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(evaluate, pair) for pair in range(3)]
        for future in concurrent.futures.as_completed(futures):
            pair = future.result(); publish(f'Save completed v12 matched development group {pair}')
    if not (out/'decision.json').exists():
        status('full-replay')
        # Separate process keeps verifier output persistent and avoids retaining model memory.
        run([sys.executable, '-c',
             "import sys;sys.path.insert(0,'tools/reviewer_v12');from verify12 import main;from pathlib import Path;main(Path('docs/research/ppo-audit-v12'))"], 'verification.log')
    status('report')
    from report12 import main as report
    report(out)
    status('complete', 'complete')
    (out/'RESUME.md').write_text('# Completed v12 audit\n\nRead README.md for all outcomes and limits. '
        'No final controller is promoted. Reserved tests remain unopened.\n\n'
        'Resume/verify: `/workspace/lans-venv/bin/python tools/reviewer_v12/run12.py --publish`\n\n'
        'Training restores a hash-checked atomic10k-step snapshot including Adam, environment, pending packets, normalization and RNG. '
        'In-flight work after that snapshot is replayed. Completed episode traces are checkpointed individually. '
        'The finite budget is exhausted; this command does not start extra training.\n')
    publish('Publish full v12 audit matched outcomes and resumable evidence')
    result = json.loads((out/'decision.json').read_text())
    print(json.dumps(result, indent=2))
    return 0 if all(v['twenty_percent_pass'] for v in result['arms'].values()) else 2


if __name__ == '__main__': sys.exit(main())
