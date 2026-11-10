"""Predeclared actual-worker fault/timing cohort after CPU confirmation."""
from pathlib import Path
import json,subprocess,sys,shutil
from .confirm import ROOT,DATA,SEEDS
from .calibrate import write,sha
from .native import safety


def main():
    gate=safety();out=DATA/'live-v1';out.mkdir(parents=True,exist_ok=False)
    p=json.loads((DATA/'confirmation-v2/plan.json').read_text());jobs=[]
    conditions=[('following','nominal','none'),('curved','ego_blackout','none'),('merge','nominal','crash'),('following','loss','stall')]
    for role in ('old','new'):
        for actor in SEEDS:
            for scenario,network,fault in conditions:
                case=dict(id=len(jobs),stage='actual_worker_fixed_cohort',scenario=scenario,mirror=1,speed=12.,stiffness=.8,
                    lateral=.3,heading=.005,phase=9.,amplitude=1.15,network=network,delay=0.,network_seed=35111000)
                jobs.append(dict(role=role,actor=actor,case=case,ppo_fault=fault,planner_fault='none',policy=str(ROOT/f'results/python-campaign-v2/policies/seed-{actor}')))
    for fault in ('stall','crash'):
        jobs.append(dict(jobs[12],case=dict(jobs[12]['case'],id=len(jobs)),planner_fault=fault))
    assert len(jobs)==26
    files=[ROOT/name for name in p['source_hashes']];files.extend(Path(__file__).parent.glob('*.py'));files.extend(Path(__file__).parent.glob('*.md'))
    files.append(ROOT/'tools/__init__.py')
    hashes={str(f.relative_to(ROOT)):sha(f) for f in sorted(set(files))}
    protocol=dict(jobs=jobs,arm=p['arm'],source_hashes=hashes,python_safety=gate,controller_revision=2,deadline_ms=50.,seconds=6.,
        fault_start_s=1.,no_late_proposal_after_s=1.5,inline_trace=True,fixed_release=True,scope='finite process fault diagnostics; no WCET or general scheduling guarantee')
    write(out/'protocol.json',protocol)
    for name in hashes:
        dest=out/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    results=[]
    for i,job in enumerate(jobs):
        for name,h in hashes.items():assert sha(ROOT/name)==h,('source changed',name)
        spec=out/f'job-{i:02d}.json';write(spec,dict(job=job,arm=p['arm']))
        dest=out/f'{i:02d}-{job["role"]}-{job["actor"]}-{job["case"]["scenario"]}-{job["ppo_fault"]}-{job["planner_fault"]}'
        with (out/(dest.name+'.log')).open('w') as log:
            subprocess.run([sys.executable,'-u','-m','tools.v8_reliability.live_case','--job',str(spec),'--output',str(dest)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        r=json.loads((dest/'summary.json').read_text());results.append(r)
        print('ACTUAL WORKERS',i+1,'/26',job['role'],'fail',r['failed'],'response misses',r['response_misses'],'scheduled cycle misses',r['scheduled_cycle_misses'],flush=True)
    write(out/'summary.json',results);new=[r for r in results if r['role']=='new']
    write(out/'STATUS.json',dict(completed=True,episodes=len(results),current_functional_pass=all(not r['failed'] and r['fault_checks_passed'] for r in new),
        current_timing_pass=all(r['scheduled_cycle_misses']==0 and r['scheduled_response_misses']==0 for r in new),policies_changed=False))


if __name__=='__main__':main()
