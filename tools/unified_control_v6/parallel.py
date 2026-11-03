"""Compute the same frozen cases on four CPU processes, then resume original audits.

Only orchestration changes. Original drivers are paused and resumed; protocols,
case IDs, models, control code, gates and canonical raw files remain authoritative.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
import json, multiprocessing as mp, os, signal, shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'results/proposal-completion-v6'
WORK=DATA/'parallel-execution'
_cases=None
_model=None
_choice=None
_controller=None


def initialize():
    global _cases,_model,_choice,_controller
    import torch
    torch.set_num_threads(1)
    from .campaign import configure,selected
    from tools.unified_control_v4 import campaign as base
    from integrations.unified_lans.inference import load_policy
    configure();_cases=base.cases;_choice,_controller=selected()
    _model=load_policy(ROOT/'results/python-campaign-v2/policies/seed-42')


def compute(job):
    from integrations.unified_lans.inference import sha
    from integrations.unified_lans.run import clean
    kind,stage,case=job;name=f'{kind}-{stage}-{case["id"]:03d}';out=WORK/'working'/name
    original=DATA/('confirmation' if kind=='formal' else 'ablations')
    out.mkdir(parents=True,exist_ok=False);shutil.copyfile(original/'protocol.json',out/'protocol.json')
    source=original/stage if kind=='formal' else original
    target=out/stage if kind=='formal' else out;target.mkdir(exist_ok=True)
    for meta in source.glob(f'{case["id"]:03d}-*.json'):
        raw=meta.with_suffix('.jsonl');record=json.loads(meta.read_text())
        if raw.exists() and sha(raw)==record['raw_sha256']:
            shutil.copyfile(raw,target/raw.name);shutil.copyfile(meta,target/meta.name)
    if kind=='formal':
        from tools.unified_control_v4 import campaign as base
        base.cases=lambda requested:[case]
        results=base.evaluate(out,stage)
    else:
        from .ablation import VARIANTS,run_episode,audit
        results=[]
        for variant in VARIANTS:
            key=f'{case["id"]:03d}-{variant}';meta=out/(key+'.json');raw=out/(key+'.jsonl')
            if meta.exists():
                result=json.loads(meta.read_text());rows=[json.loads(s) for s in raw.read_text().splitlines()]
            else:
                result,rows=run_episode(case,variant,_model,_choice,_controller)
                raw.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
                result.update(raw_sha256=sha(raw),protocol_sha256=sha(out/'protocol.json'))
                meta.write_text(json.dumps(clean(result),indent=2))
            audit(result,rows);results.append(result)
    manifest=dict(job=[kind,stage,case['id']],episodes=len(results),files={str(p.relative_to(out)):sha(p) for p in target.glob(f'{case["id"]:03d}-*') if p.is_file()})
    (out/'completion.json').write_text(json.dumps(manifest,indent=2))
    return name


def parent_processes():
    found=[]
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:args=(path/'cmdline').read_bytes().split(b'\0')
        except (OSError,PermissionError):continue
        if any(module.encode() in args for module in ['tools.unified_control_v6.campaign','tools.unified_control_v6.ablation']):
            found.append(int(path.name))
    assert len(found)==2, ('expected the two original study drivers',found)
    return found


def main():
    from integrations.unified_lans.inference import sha
    from .campaign import configure
    from tools.unified_control_v4 import campaign as base
    from .ablation import cases as ablation_cases,VARIANTS
    parents=parent_processes();WORK.mkdir(exist_ok=False)
    paused=[]
    try:
        for pid in parents:os.kill(pid,signal.SIGSTOP);paused.append(pid)
        configure();jobs=[]
        for stage in ['regression-development','regression-stress','development','stress']:
            for case in base.cases(stage):
                expected=11 if stage=='development' else 5
                if len(list((DATA/'confirmation'/stage).glob(f'{case["id"]:03d}-*.json')))<expected:
                    jobs.append(('formal',stage,case))
        for case in ablation_cases():
            if len(list((DATA/'ablations').glob(f'{case["id"]:03d}-*.json')))<len(VARIANTS):jobs.append(('ablation','components',case))
        protocol=dict(workers=4,parent_pids=parents,source_sha256=sha(Path(__file__)),
            formal_protocol_sha256=sha(DATA/'confirmation/protocol.json'),ablation_protocol_sha256=sha(DATA/'ablations/protocol.json'),
            jobs=[[kind,stage,c['id']] for kind,stage,c in jobs],
            reason='identical frozen case computations, four available CPU cores; no controller/gate/data-selection change')
        (WORK/'protocol.json').write_text(json.dumps(protocol,indent=2));shutil.copyfile(__file__,WORK/'parallel.py')
        completed=[]
        with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn'),initializer=initialize) as pool:
            futures=[pool.submit(compute,j) for j in jobs]
            for future in as_completed(futures):
                completed.append(future.result())
                if len(completed)%5==0:print('PARALLEL CASES',len(completed),'/',len(jobs),flush=True)
        copied=[];overlap=[]
        for name in completed:
            directory=WORK/'working'/name;manifest=json.loads((directory/'completion.json').read_text())
            kind,stage,_=manifest['job'];dest=DATA/('confirmation' if kind=='formal' else 'ablations')
            for member,h in manifest['files'].items():
                src=directory/member;target=dest/member;assert sha(src)==h
                if target.exists():
                    overlap.append(dict(source=str(src.relative_to(ROOT)),canonical=str(target.relative_to(ROOT)),identical=sha(target)==h))
                    continue
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target);copied.append(str(target.relative_to(ROOT)))
        (WORK/'completion.json').write_text(json.dumps(dict(completed=completed,copied=copied,overlaps=overlap),indent=2))
        print('MERGED',len(copied),'files; original drivers resume their full coverage/audits/gates',flush=True)
    finally:
        for pid in paused:
            try:os.kill(pid,signal.SIGCONT)
            except ProcessLookupError:pass


if __name__=='__main__':main()
