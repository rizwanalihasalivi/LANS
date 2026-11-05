"""Source-frozen post-release audit regression campaign; see AUDIT_PROTOCOL.md."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import itertools
import json
from pathlib import Path
import traceback

from .autonomy.study import ROOT, write
from .settling import study, native, audit, verify_inputs
from .settling.scenarios import PROFILES

PHASES = ('python-development', 'native-development', 'python-validation', 'native-validation')


def jobs_for(phase):
    native_run = phase.startswith('native-')
    validation = phase.endswith('-validation')
    seed = (22003 if validation else 12037) if native_run else (21001 if validation else 6121)
    jobs = list(itertools.product(PROFILES, (8., 12.) if native_run else (8., 12., 16.), (seed,)))
    if phase == 'python-development':
        jobs.append(('combined', 16., 7069))
    return jobs


def episode(job):
    output, case, speed, seed, native_run = job
    path = Path(output)
    try:
        if native_run:
            result = native.run_one((output, case, speed, seed))
            if 'error' in result:
                return result
            independent = audit.check_native_episode(path, result)
        else:
            result = study.run_episode(output, case, speed, seed)
            independent = audit.check_python_episode(path, result)
            local, peer, radio = verify_inputs.check(path)
            write(path/'input-audit.json', dict(passed=True, local_scans=local,
                  cooperative_datagrams=peer, radio_deliveries=radio))
        write(path/'independent-audit.json', independent)
        return result
    except Exception:
        path.mkdir(parents=True, exist_ok=True)
        (path/'audit-failure.txt').write_text(traceback.format_exc())
        return dict(passed=False, case=case, speed=speed, seed=seed, error='see audit-failure.txt')


def run(root, phase):
    root = Path(root).resolve()
    if not root.exists():
        if phase != PHASES[0]:
            raise ValueError('start with python-development in a new root')
        root.mkdir(parents=True, exist_ok=False)
        source = Path(__file__).parent
        files = [*study.runtime_files(), *source.rglob('*.py'), source/'AUDIT_PROTOCOL.md']
        # Evidence archives and generated output never contribute executable source.
        files = [p for p in files if 'evidence' not in p.parts and '__pycache__' not in p.parts]
        hashes = study.freeze(root, sorted(set(files)))
        write(root/'plan.json', dict(parent='4843c4f1842d042928a953b3394660fa74690de9',
              phases={p: jobs_for(p) for p in PHASES}, sources=hashes, seconds=70.,
              scope='audit regression cohorts; final comparative benchmarking on hold'))
    plan = json.loads((root/'plan.json').read_text())
    study.verify_sources(plan['sources'])
    for earlier in PHASES[:PHASES.index(phase)]:
        prior = json.loads((root/earlier/'summary.json').read_text())
        if not prior['passed']:
            raise ValueError('earlier phase failed: ' + earlier)
    directory = root/phase
    directory.mkdir(exist_ok=False)
    jobs = [(str(directory/f'{case}-{speed:g}-{seed}'), case, speed, seed, phase.startswith('native-'))
            for case, speed, seed in plan['phases'][phase]]
    results = []
    with ProcessPoolExecutor(max_workers=2 if phase.startswith('native-') else 3) as pool:
        for future in as_completed([pool.submit(episode, job) for job in jobs]):
            result = future.result()
            results.append(result)
            print(json.dumps({k: result[k] for k in ('case', 'speed', 'seed', 'passed')}), flush=True)
    study.verify_sources(plan['sources'])
    results.sort(key=lambda r: (r['case'], r['speed'], r['seed']))
    summary = dict(passed=bool(results) and all(r['passed'] for r in results), results=results)
    write(directory/'summary.json', summary)
    if not summary['passed']:
        raise SystemExit('audit regression failed; all evidence retained')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--phase', choices=PHASES, required=True)
    args = parser.parse_args()
    run(args.output, args.phase)
