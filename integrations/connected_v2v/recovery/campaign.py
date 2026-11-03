"""One frozen finite study, cached episodes, explicit conditional confirmation."""
import argparse
import itertools
import json
from pathlib import Path
import shutil
import numpy as np
from integrations.connected_v2v.demo import digest, write
from .controller import METHODS
from .study import SCENARIOS, run_episode
from .verify import replay

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = dict(version='connected-recovery-v2', seconds=20., speeds=[8.,12.,16.],
                development_seeds=[4101,4102,4103], confirmation_seeds=[5101,5102,5103],
                confirmation_shift_s=.15, methods=list(METHODS), scenarios=list(SCENARIOS),
                independent_seeds=3, bootstrap_draws=5000, bootstrap_seed=81501,
                gates=dict(blackout_gain_percent=50., blackout_lower_ci_positive=True,
                           radar_acc_rms_ratio_max=1.05, nominal_legacy_rms_ratio_max=1.10,
                           nominal_absolute_allowance_m=.01, min_progress_ratio=.99,
                           jerk_ratio_max=1.05, jerk_absolute_allowance=.1,
                           collisions=0,corridor=0,stale_source=0,bound_violations=0),
                selection='one candidate; no tuning, best-seed/checkpoint selection or extra training',
                perception='ideal target association, bounded range/rate error, delayed local sensing',
                membership='common scripted cut-in/cut-out assignment, not autonomous identity discovery')


def source_files():
    return sorted({*Path(__file__).parent.glob('*.py'), Path(__file__).with_name('PROTOCOL.md'),
                   *(ROOT/'integrations/connected_v2v').glob('*.py'),
                   *(ROOT/'integrations/unified_lans').glob('*.py'),
                   ROOT/'controllers/lqr_controller.py', ROOT/'models/bicycle_model.py'})


def prepare(path):
    path=Path(path);path.mkdir(parents=True,exist_ok=False)
    hashes={str(p.relative_to(ROOT)):digest(p) for p in source_files()}
    write(path/'protocol.json',dict(protocol=PROTOCOL,sources=hashes))
    for name in hashes:
        target=path/'source'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,target)
    print('FROZEN',digest(path/'protocol.json'),flush=True)


def check(path):
    path=Path(path);record=json.loads((path/'protocol.json').read_text())
    assert record['protocol']==PROTOCOL,'Protocol changed; preserve this run'
    for name,expected in record['sources'].items():
        assert digest(ROOT/name)==expected,('Frozen source changed',name)
    return path


def assess(rows):
    groups={}
    for row in rows:
        groups.setdefault((row['seed'],row['speed'],row['scenario']),{})[row['method']]=row
    assert len(rows)==216 and len(groups)==72 and all(set(g)==set(METHODS) for g in groups.values()),'Incomplete matched grid'
    candidate=[g['fusion'] for g in groups.values()]
    radar=[g['radar_acc'] for g in groups.values()]
    legacy=[g['v2v_only'] for g in groups.values()]
    blackout=[g for key,g in groups.items() if key[2]=='v2v_blackout']
    base=np.mean([g['v2v_only']['spacing_rms_m'] for g in blackout])
    improved=np.mean([g['fusion']['spacing_rms_m'] for g in blackout])
    gain=float(100*(1-improved/base))
    seeds=sorted({r['seed'] for r in rows})
    cluster=[]
    for seed in seeds:
        selected=[g for key,g in groups.items() if key[0]==seed and key[2]=='v2v_blackout']
        cluster.append([np.mean([g['v2v_only']['spacing_rms_m'] for g in selected]),
                        np.mean([g['fusion']['spacing_rms_m'] for g in selected])])
    cluster=np.array(cluster);random=np.random.default_rng(PROTOCOL['bootstrap_seed'])
    samples=cluster[random.integers(0,len(cluster),(PROTOCOL['bootstrap_draws'],len(cluster)))]
    gains=100*(1-samples[:,:,1].mean(axis=1)/samples[:,:,0].mean(axis=1))
    interval=[float(v) for v in np.quantile(gains,[.025,.975])]
    limits=PROTOCOL['gates']
    checks=dict(blackout_gain=gain>=limits['blackout_gain_percent'],blackout_ci=interval[0]>0,
                radar_acc_noninferiority=np.mean([r['spacing_rms_m'] for r in candidate])<=limits['radar_acc_rms_ratio_max']*np.mean([r['spacing_rms_m'] for r in radar]),
                nominal_nonregression=all(g['fusion']['spacing_rms_m']<=limits['nominal_legacy_rms_ratio_max']*g['v2v_only']['spacing_rms_m']+limits['nominal_absolute_allowance_m'] for key,g in groups.items() if key[2]=='nominal'),
                no_collisions=all(r['collision_pair_ticks']==0 for r in candidate),
                no_corridor=all(r['corridor_ticks']==0 for r in candidate),
                fresh_sources=all(r['stale_source_ticks']==0 for r in candidate),
                actuator_bounds=all(r['bound_violations']==0 for r in candidate),
                progress=all(g['fusion']['progress_m'][name]>=limits['min_progress_ratio']*g['v2v_only']['progress_m'][name] for g in groups.values() for name in ['follower-1','follower-2']),
                jerk=np.mean([r['jerk_rms_m_s3'] for r in candidate])<=limits['jerk_ratio_max']*np.mean([r['jerk_rms_m_s3'] for r in legacy])+limits['jerk_absolute_allowance'])
    checks={name:bool(value) for name,value in checks.items()}
    table={method:dict(spacing_rms_m=float(np.mean([r['spacing_rms_m'] for r in rows if r['method']==method])),
                       jerk_rms_m_s3=float(np.mean([r['jerk_rms_m_s3'] for r in rows if r['method']==method])),
                       collision_pair_ticks=sum(r['collision_pair_ticks'] for r in rows if r['method']==method),
                       min_gap_m=min(r['min_gap_m'] for r in rows if r['method']==method)) for method in METHODS}
    return dict(passed=all(checks.values()),checks=checks,blackout_gain_percent=gain,
                blackout_gain_ci95=interval,independent_seed_clusters=3,means=table,
                reserved_main_controller='NOT_RUN',native='CONDITIONAL_NOT_RUN')


def run(path,stage):
    path=check(path)
    if stage=='confirmation':
        assert json.loads((path/'development/gate.json').read_text())['passed'],'Development failed; confirmation remains closed'
    destination=path/stage;destination.mkdir(exist_ok=True)
    seeds=PROTOCOL[stage+'_seeds'];shift=PROTOCOL['confirmation_shift_s'] if stage=='confirmation' else 0.
    results=[]
    for seed,speed,scenario in itertools.product(seeds,PROTOCOL['speeds'],SCENARIOS):
        for method in METHODS:
            output=destination/f'{seed}-{int(speed)}-{scenario}-{method}'
            if (output/'summary.json').exists():
                assert replay(output)['passed']
                result=json.loads((output/'summary.json').read_text())
            else:
                result=run_episode(output,scenario,method,speed,seed,seconds=PROTOCOL['seconds'],shift=shift)
            results.append(result)
        print(stage,seed,speed,scenario,'complete',flush=True)
    write(destination/'summary.json',results)
    gate=assess(results);write(destination/'gate.json',gate)
    print(json.dumps(gate,indent=2),flush=True)
    return gate


def verify(path,stage):
    path=check(path);destination=path/stage
    rows=json.loads((destination/'summary.json').read_text())
    ticks=0
    for r in rows:
        folder=destination/f'{r["seed"]}-{int(r["speed"])}-{r["scenario"]}-{r["method"]}'
        assert json.loads((folder/'summary.json').read_text())==r
        ticks+=replay(folder)['ticks']
    assert assess(rows)==json.loads((destination/'gate.json').read_text())
    return dict(passed=True,episodes=len(rows),vehicle_ticks=ticks,
                scope='all receiver/control/physics replays and gate recomputation')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','development','confirmation','verify'])
    p.add_argument('--output',required=True)
    p.add_argument('--stage',choices=['development','confirmation'],default='development')
    a=p.parse_args()
    if a.action=='prepare':prepare(a.output)
    elif a.action=='verify':print(json.dumps(verify(a.output,a.stage),indent=2))
    else:run(a.output,a.action)


if __name__=='__main__':main()
