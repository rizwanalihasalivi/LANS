"""Fixed paired actual-worker diagnostics, once after CPU simulation jobs."""
from pathlib import Path
import json,subprocess,sys,shutil
from integrations.unified_lans.inference import sha

ROOT=Path(__file__).resolve().parents[2]


def main():
    root=ROOT/'results/publication-v9/live-functional';root.mkdir(parents=True,exist_ok=False)
    jobs=[(role,seed,scenario,network,fault,'none') for role in ['old','new'] for seed in [42,43,44]
        for scenario,network,fault in [('following','nominal','none'),('curved','ego_blackout','none'),('merge','nominal','crash')]]
    jobs.extend([('new',42,'following','nominal','none',fault) for fault in ['stall','crash']]);assert len(jobs)==20
    frozen=json.loads((ROOT/'results/publication-v9/confirmation/protocol.json').read_text())
    hashes=dict(frozen['source_hashes'])
    for name in ['live.py','live_case.py','RUNTIME_PROTOCOL.md']:
        path=Path(__file__).parent/name;hashes[str(path.relative_to(ROOT))]=sha(path)
    for name,h in hashes.items():
        assert sha(ROOT/name)==h,('Source changed after evaluation',name)
        dest=root/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    (root/'protocol.json').write_text(json.dumps(dict(jobs=jobs,role='FINITE_FUNCTIONAL_NOT_WCET',seconds=6.,deadline_ms=50.,source_hashes=hashes,
        selection_sha256=sha(ROOT/'results/publication-v9/calibration/selection.json'),script_sha256=sha(Path(__file__))),indent=2))
    records=[]
    for role,seed,scenario,network,fault,planner_fault in jobs:
        for name,h in hashes.items():assert sha(ROOT/name)==h,('Source changed during live run',name)
        directory=root/f'{role}-{seed}-{scenario}-{planner_fault}'
        policy=ROOT/f'results/{"python-campaign-v2" if role=="old" else "publication-v9"}/policies/seed-{seed}'
        command=[sys.executable,'-u','-m','tools.unified_control_v9.live_case','--output',str(directory),'--policy',str(policy),
            '--role',role,'--scenario',scenario,'--network',network,'--fault',fault,'--planner-fault',planner_fault]
        completed=subprocess.run(command,check=False,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        (root/(directory.name+'.log')).write_text(completed.stdout)
        if completed.returncode:raise RuntimeError(('Preserved failed live execution',directory,completed.returncode))
        record=json.loads((directory/'summary.json').read_text());record.update(role=role,seed=seed,scenario=scenario,planner_fault=planner_fault,directory=directory.name)
        records.append(record);print('LIVE CHECK',len(records),'/20',role,seed,scenario,planner_fault,'misses',record['response_misses'],flush=True)
    (root/'summary.json').write_text(json.dumps(records,indent=2))


if __name__=='__main__':main()
