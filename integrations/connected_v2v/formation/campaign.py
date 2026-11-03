"""Frozen paired formation study; one analytical candidate and conditional gates."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import itertools
import json
import math
from pathlib import Path
import shutil
import numpy as np
from integrations.connected_v2v.demo import digest, write
from integrations.connected_v2v.recovery import study as v2_study, verify as v2_verify
from .adapter import configured
from .controller import VARIANTS
from .metrics import compute

ROOT=Path(__file__).resolve().parents[3]
PROTOCOL=dict(version='formation-v3',seconds=30.,speeds=[8.,12.,16.],
    development_seeds=[6101,6102,6103],confirmation_seeds=[7101,7102,7103],
    confirmation_shift_s=.15,variants=list(VARIANTS),scenarios=list(v2_study.SCENARIOS),
    bootstrap_seed=99171,bootstrap_draws=5000,workers=3,
    candidate=dict(omega=.8,kp=.8**2,kv=1.6-1.2*.8**2,headway_s=1.2,gap_m=6.,overspeed_m_s=8.),
    gates=dict(settling_gain_percent=20.,settling_ci_lower_positive=True,first20_target_rms_ratio=1.05,
        nominal_rms_ratio=1.1,nominal_absolute_allowance_m=.01,min_progress_ratio=.99,
        command_jerk_ratio=1.05,command_jerk_absolute_allowance=.1),
    selection='one analytical candidate; all seeds retained; no search or extra training')


def files():
    return sorted({*Path(__file__).parent.glob('*.py'),Path(__file__).with_name('PROTOCOL.md'),
        *(ROOT/'integrations/connected_v2v/recovery').glob('*.py'),
        *(ROOT/'integrations/connected_v2v').glob('*.py'),
        *(ROOT/'integrations/unified_lans').glob('*.py'),
        ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py'})


def prepare(path):
    path=Path(path);path.mkdir(parents=True,exist_ok=False)
    hashes={str(p.relative_to(ROOT)):digest(p) for p in files()}
    write(path/'protocol.json',dict(protocol=PROTOCOL,sources=hashes))
    for name in hashes:
        dest=path/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    print('FROZEN',digest(path/'protocol.json'),flush=True)


def check(path):
    path=Path(path);record=json.loads((path/'protocol.json').read_text())
    assert record['protocol']==PROTOCOL,'Protocol changed; preserve this study'
    for name,value in record['sources'].items():assert digest(ROOT/name)==value,('Frozen source changed',name)
    return path


def task(args):
    root,path,scenario,variant,speed,seed,shift=args
    check(root);path=Path(path)
    with configured(variant):
        if (path/'summary.json').exists():
            assert v2_verify.replay(path)['passed']
            summary=json.loads((path/'summary.json').read_text())
        else:
            summary=v2_study.run_episode(path,scenario,variant,speed,seed,seconds=PROTOCOL['seconds'],shift=shift)
    metrics=compute(path)
    for name in ['spacing_rms_m','jerk_rms_m_s3','min_gap_m']:
        assert math.isclose(metrics[name],summary[name],rel_tol=0,abs_tol=1e-10),('Independent score mismatch',name)
    result=dict(scenario=scenario,variant=variant,speed=speed,seed=seed,
                raw_sha256=summary['raw_sha256'],case_sha256=summary['case_sha256'],**metrics)
    write(path/'formation.json',result)
    return result


def assess(rows):
    groups={}
    for row in rows:groups.setdefault((row['seed'],row['speed'],row['scenario']),{})[row['variant']]=row
    assert len(rows)==144 and len(groups)==72 and all(set(g)==set(VARIANTS) for g in groups.values()),'Incomplete paired grid'
    limits=PROTOCOL['gates'];candidate=[g['damped'] for g in groups.values()];baseline=[g['baseline'] for g in groups.values()]
    checks={};recovery={}
    for scenario,event in [('dual_blackout','dual'),('cut_in','cut_out')]:
        selected=[(key,g) for key,g in groups.items() if key[2]==scenario]
        base=np.mean([g['baseline']['settling'][event]['duration_s'] for _,g in selected])
        new=np.mean([g['damped']['settling'][event]['duration_s'] for _,g in selected])
        gain=float(100*(1-new/base))
        seeds=sorted({key[0] for key,_ in selected});cluster=[]
        for seed in seeds:
            subset=[g for key,g in selected if key[0]==seed]
            cluster.append([np.mean([g[v]['settling'][event]['duration_s'] for g in subset]) for v in VARIANTS])
        cluster=np.array(cluster);rng=np.random.default_rng(PROTOCOL['bootstrap_seed'])
        samples=cluster[rng.integers(0,len(cluster),(PROTOCOL['bootstrap_draws'],len(cluster)))]
        distribution=100*(1-samples[:,:,1].mean(axis=1)/samples[:,:,0].mean(axis=1))
        interval=[float(v) for v in np.quantile(distribution,[.025,.975])]
        uncensored=all(not g['damped']['settling'][event]['censored'] for _,g in selected)
        checks[event+'_settling']=gain>=limits['settling_gain_percent'] and interval[0]>0 and uncensored
        recovery[event]=dict(baseline_s=float(base),damped_s=float(new),gain_percent=gain,ci95=interval,
            baseline_censored=sum(g['baseline']['settling'][event]['censored'] for _,g in selected),
            damped_censored=sum(g['damped']['settling'][event]['censored'] for _,g in selected))
    checks['first20_target_nonregression']=all(g['damped']['first20_spacing_rms_m']<=limits['first20_target_rms_ratio']*g['baseline']['first20_spacing_rms_m'] for key,g in groups.items() if key[2] in ('dual_blackout','cut_in'))
    checks['nominal_nonregression']=all(g['damped']['first20_spacing_rms_m']<=limits['nominal_rms_ratio']*g['baseline']['first20_spacing_rms_m']+limits['nominal_absolute_allowance_m'] for key,g in groups.items() if key[2]=='nominal')
    for key in ['collision_pair_ticks','corridor_ticks','stale_source_ticks','blind_brake_violations','actuator_violations','speed_violations']:
        checks['zero_'+key]=all(r[key]==0 for r in candidate)
    checks['progress']=all(g['damped'][metric][name]>=limits['min_progress_ratio']*g['baseline'][metric][name] for g in groups.values() for metric in ['first20_progress_m','progress_m'] for name in ['follower-1','follower-2'])
    checks['jerk']=np.mean([r['jerk_rms_m_s3'] for r in candidate])<=limits['command_jerk_ratio']*np.mean([r['jerk_rms_m_s3'] for r in baseline])+limits['command_jerk_absolute_allowance']
    checks={key:bool(value) for key,value in checks.items()}
    return dict(passed=all(checks.values()),checks=checks,recovery=recovery,independent_seed_clusters=3,
                first20_mean_rms_m={v:float(np.mean([r['first20_spacing_rms_m'] for r in rows if r['variant']==v])) for v in VARIANTS},
                command_jerk_mean={v:float(np.mean([r['jerk_rms_m_s3'] for r in rows if r['variant']==v])) for v in VARIANTS},
                native='CONDITIONAL_NOT_RUN',main_ppo_reserved='NOT_RUN')


def run(root,stage):
    root=check(root)
    if stage=='confirmation':assert json.loads((root/'development/gate.json').read_text())['passed'],'Development failed; confirmation remains closed'
    dest=root/stage;dest.mkdir(exist_ok=False)
    shift=PROTOCOL['confirmation_shift_s'] if stage=='confirmation' else 0.
    with ProcessPoolExecutor(max_workers=PROTOCOL['workers']) as pool:
        if stage=='development':
            futures=[pool.submit(task,(root,root/f'execution-proof/{i}','nominal','baseline',8.,6101,0.)) for i in range(2)]
            a,b=[f.result() for f in futures];assert a==b,'Parallel raw/metric repeatability failed'
            write(root/'execution-proof/proof.json',dict(passed=True,raw_sha256=a['raw_sha256'],exact_repeats=2))
        futures=[]
        for seed,speed,scenario,variant in itertools.product(PROTOCOL[stage+'_seeds'],PROTOCOL['speeds'],PROTOCOL['scenarios'],VARIANTS):
            path=dest/f'{seed}-{int(speed)}-{scenario}-{variant}'
            futures.append(pool.submit(task,(root,path,scenario,variant,speed,seed,shift)))
        rows=[]
        for future in as_completed(futures):
            rows.append(future.result())
            if len(rows)%12==0:print(stage,len(rows),'of',len(futures),'audited episodes',flush=True)
    rows.sort(key=lambda r:(r['seed'],r['speed'],PROTOCOL['scenarios'].index(r['scenario']),VARIANTS.index(r['variant'])))
    write(dest/'summary.json',rows);gate=assess(rows);write(dest/'gate.json',gate)
    print(json.dumps(gate,indent=2),flush=True)
    return gate


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','development','confirmation']);p.add_argument('--output',required=True);a=p.parse_args()
    if a.action=='prepare':prepare(a.output)
    else:run(a.output,a.action)


if __name__=='__main__':main()
