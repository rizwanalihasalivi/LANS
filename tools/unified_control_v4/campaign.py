"""Strict v4 repair campaign; old failures, fresh development, stress and confirmation."""
import argparse
from dataclasses import asdict,replace
from functools import partial
import json,math,shutil,time
from pathlib import Path
import numpy as np
from integrations.unified_lans.physics import Config,Command,advance,errors
from integrations.unified_lans.inference import load_policy,sha
from integrations.unified_lans.run import clean
from tools.unified_campaign import study
from tools.unified_campaign.campaign import assess as old_gate,PROTOCOL as OLD_PROTOCOL
from .control import Controller,GRID

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'results/corridor-v4/confirmation-campaign'
SEEDS=[42,43,44]
MODES=['lqr','fixed','deterministic','optimized','adaptive','ppo','hybrid']


def write(path,value):
    path=Path(path);tmp=path.with_suffix('.pending');tmp.write_text(json.dumps(clean(value),indent=2,allow_nan=False)+'\n');tmp.replace(path)


def prepare(root):
    selection=ROOT/'results/corridor-v4/calibration/selection.json'
    selected=json.loads(selection.read_text())['selected'];assert selected is not None
    horizon_selection=ROOT/'results/corridor-v4/lookahead-calibration/selection.json'
    horizon=json.loads(horizon_selection.read_text())['selected']['horizon']
    root.mkdir(parents=True,exist_ok=False)
    files=[*Path(__file__).parent.glob('*.py'),*list((ROOT/'integrations/unified_lans').glob('*.py')),
        ROOT/'tools/unified_campaign/study.py',ROOT/'tools/unified_campaign/campaign.py',
        ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    protocol=dict(version=4,seeds=SEEDS,seconds=6.,modes=MODES,config=asdict(Config(horizon=horizon)),
        baseline_penalty=selected['penalty'],calibration_sha256=sha(selection),shared_optimized_grid=GRID,
        horizon_calibration_sha256=sha(horizon_selection),shared_mpc_in_optimized_adaptive_hybrid=True,
        changes=['shared constraint-aware LQR calibration','hard predictive corridor eligibility',
                 'single committed control interval in candidate rollouts','causal stiffness observer and consistent feedback/prediction in hybrid/adaptive',
                 'bounded dead-reckoning braking backup without stale PPO admission','rate/residual constrained QP plan with robust nonlinear admission'],
        original_gate=OLD_PROTOCOL['gate'],bootstrap=OLD_PROTOCOL['bootstrap'],
        evaluation='all three fixed endpoints; no seed/checkpoint selection',new_training_steps=0,
        learning_claim='matched adaptive-only ablation is retained; no pure-PPO superiority assumed',
        source_hashes=hashes,models={str(s):sha(ROOT/f'results/python-campaign-v2/policies/seed-{s}/policy.zip') for s in SEEDS},
        development=dict(namespace=3410000,phase=7.,amplitude=1.15),reserved=dict(namespace=6410000,phase=19.,amplitude=1.25),
        no_threshold_relaxation=True,no_native_until_all_python_gates_pass=True)
    write(root/'protocol.json',protocol)
    for p in files:
        target=root/'source'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    return protocol


def check(root):
    p=json.loads((root/'protocol.json').read_text())
    assert p['original_gate']==OLD_PROTOCOL['gate']
    for name,h in p['source_hashes'].items():assert sha(ROOT/name)==h,('Changed source',name)
    for s,h in p['models'].items():assert sha(ROOT/f'results/python-campaign-v2/policies/seed-{s}/policy.zip')==h
    return p


def cases(stage):
    if stage.startswith('regression'):
        old='development' if stage=='regression-development' else 'robustness'
        rr=json.loads((ROOT/f'results/python-improvement-v3/{old}_summary.json').read_text())
        return list({r['case']['id']:r['case'] for r in rr}.values())
    if stage=='stress':
        result=[]
        for s in range(4):
            for j,profile in enumerate(['delayed','loss','reordered','blackout','ego_blackout','command_delay']):
                c=study.make_case('development',s*8)
                c.update(id=s*6+j,stage='v4_stress',speed=12.,phase=7.,amplitude=1.15,
                    lateral=.3*c['mirror'],heading=.005*c['mirror'],stiffness=.8,
                    network='nominal' if profile=='command_delay' else profile,
                    delay=.1 if profile=='command_delay' else 0.,network_seed=4410000+s*6+j)
                result.append(c)
        return result
    result=[];reserved=stage=='reserved';rng=np.random.default_rng(6410000 if reserved else 3410000)
    for i in range(32):
        c=study.make_case('reserved' if reserved else 'development',i)
        c.update(stage='v4_'+stage,lateral=float(rng.uniform(.15,.45))*c['mirror'],heading=float(rng.uniform(-.015,.015)),
                 phase=19. if reserved else 7.,amplitude=1.25 if reserved else 1.15,
                 network_seed=(6510000 if reserved else 3510000)+i)
        result.append(c)
    return result


def evaluate(root,stage):
    import torch
    torch.set_num_threads(1);p=check(root);dest=root/stage;dest.mkdir(exist_ok=True)
    models={s:load_policy(ROOT/f'results/python-campaign-v2/policies/seed-{s}') for s in SEEDS}
    modes=MODES if stage in ('development','reserved') else ['lqr','optimized','hybrid']
    results=[]
    for case in cases(stage):
        for mode in modes:
            for actor in SEEDS if mode in ('ppo','hybrid') else [0]:
                key=f"{case['id']:03d}-{mode}-{actor}";meta=dest/(key+'.json');raw=dest/(key+'.jsonl')
                if meta.exists():
                    result=json.loads(meta.read_text());assert result['case']==case and sha(raw)==result['raw_sha256']
                    assert result['protocol_sha256']==sha(root/'protocol.json')
                else:
                    assert not raw.exists(),('Preserve interrupted raw evidence',raw)
                    def factory(*args,**kwargs):
                        args=list(args);args[2]=replace(args[2],horizon=p['config']['horizon'])
                        return Controller(*args,penalty=p['baseline_penalty'],adaptive=mode in ('hybrid','adaptive'),mpc=mode in ('optimized','adaptive','hybrid'),**kwargs)
                    study.Pipeline=factory
                    base_mode='deterministic' if mode in ('optimized','adaptive') else mode
                    result,rows=study.run_episode(case,base_mode,models.get(actor),grid=mode in ('optimized','adaptive','hybrid'),seconds=6.)
                    result['mode']=mode
                    raw.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
                    result.update(actor=actor,raw_sha256=sha(raw),protocol_sha256=sha(root/'protocol.json'))
                    write(meta,result)
                results.append(result)
        print(stage,'case',case['id']+1,'complete',flush=True)
    write(root/(stage+'_summary.json'),results)
    audit(root,stage,results)
    return results


def audit(root,stage,results):
    ticks=0;keys=set()
    for r in results:
        key=f"{r['case']['id']:03d}-{r['mode']}-{r['actor']}";assert key not in keys;keys.add(key)
        raw=root/stage/(key+'.jsonl');assert sha(raw)==r['raw_sha256']
        rr=[json.loads(s) for s in raw.read_text().splitlines()];ego=np.array(rr[0]['state_before']);prev=Command();pending=[];last_issued=Command()
        # Geometry uses only the declared fixture, never the evaluated trajectory.
        route=study.StudyRoute(study.initial(r['case']['scenario'])[0].kind,r['case']['mirror'],r['case']['phase'],r['case']['amplitude'])
        for i,row in enumerate(rr):
            assert row['tick']==i and row['time_s']==i*.05
            np.testing.assert_allclose(ego,row['state_before'],atol=1e-12,rtol=0)
            issued=Command(row['issued_steering'],row['issued_accel'])
            assert abs(issued.steering-last_issued.steering)<=.03+1e-10 and abs(issued.steering)<=.5
            assert -6<=issued.accel<=2.5;last_issued=issued
            pending.append((row['time_s']+r['case']['delay'],issued))
            while pending and pending[0][0]<=row['time_s']+1e-9:_,prev=pending.pop(0)
            actual=Command(row['applied_steering'],row['applied_accel']);assert prev==actual
            ego=advance(ego,actual,.05,r['case']['stiffness'])
            np.testing.assert_allclose(ego,row['state_after'],atol=1e-12,rtol=0)
            e,_=errors(ego,route);assert abs(e[0]-row['error'])<1e-12
            if row['source']=='ppo':assert row['proposal_age']<.15 and row['proposal_wall_age']<.15 and not row['ego_backup']
            if row['ego_backup']:
                assert row['source'] in ('backup_lqr','hold_brake') and issued.accel==-6. and row['residual']==0.
            assert .7<=row['stiffness_estimate']<=1.3
        n=r['expected_ticks'];value=math.sqrt((sum(x['error']**2 for x in rr)+(n-len(rr))*2.5**2)/n)
        assert abs(value-r['rmse_m'])<1e-12;ticks+=len(rr)
    write(root/(stage+'_audit.json'),dict(passed=True,episodes=len(results),ticks=ticks,protocol_sha256=sha(root/'protocol.json')))


def summary(root,stage,results):
    hybrids=[r for r in results if r['mode']=='hybrid']
    safety=dict(passed=not any(r['failed'] for r in hybrids),failures=sum(r['failed'] for r in hybrids),
                cases=len(hybrids),collisions=sum(r['collisions']>0 for r in hybrids))
    write(root/(stage+'_safety.json'),safety)
    if stage in ('development','reserved'):
        gate=old_gate(results);write(root/(stage+'_gate.json'),gate)
        print(stage,'GATE',json.dumps(gate),flush=True)
        return gate['passed']
    return safety['passed']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['prepare','regression','development','stress','reserved','all'],default='all')
    parser.add_argument('--output',default=str(RUN));a=parser.parse_args();root=Path(a.output)
    if not root.exists():prepare(root)
    check(root)
    if a.stage=='prepare':return
    stages=['regression-development','regression-stress','development','stress'] if a.stage=='all' else (['regression-development','regression-stress'] if a.stage=='regression' else [a.stage])
    for stage in stages:
        if stage=='reserved':
            assert json.loads((root/'development_gate.json').read_text())['passed']
            assert json.loads((root/'stress_safety.json').read_text())['passed']
        results=evaluate(root,stage);summary(root,stage,results)
    if a.stage=='all':
        passed=json.loads((root/'development_gate.json').read_text())['passed'] and all(json.loads((root/(s+'_safety.json')).read_text())['passed'] for s in ['regression-development','regression-stress','stress'])
        if passed:summary(root,'reserved',evaluate(root,'reserved'))
        write(root/'STATUS.json',dict(development_passed=passed,reserved='completed' if passed else 'NOT_RUN',
            wall_worker='NOT_RUN',webots='NOT_RUN'))


if __name__=='__main__':main()
