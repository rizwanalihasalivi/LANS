"""Prospective matched confirmation with unchanged frozen PPO policies."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import json,multiprocessing as mp,shutil
import numpy as np
from integrations.unified_lans.inference import load_policy
from integrations.unified_lans.run import clean
from tools.unified_campaign.study import make_case
from tools.unified_control_v8.campaign import cases as v8_cases
from tools.unified_control_v8.control import Controller as V8
from tools.unified_control_v9.learning import run_episode
from .calibrate import ARMS,sha,write
from .control import Controller,Synchronous
from .cbf_reference import Controller as CBF
from .regressions import CASES

ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'results/lans-reliability-v10'
OUT=DATA/'confirmation-v1';SEEDS=(42,43,44)
MODES=('lqr','fixed','deterministic','optimized','adaptive','hybrid','v8_common','v8_original','v8_adaptive','cbf')
ACTOR_MODES=('hybrid','v8_common','v8_original')
MODELS={}


def cases(stage):
    if stage=='v8_reserved':
        return [dict(c,cluster_network='nominal') for c in v8_cases('reserved')]
    if stage=='known_crossing':
        return [dict(c,id=i,original_case_id=c['id'],stage='exposed_training_regression',cluster_network='nominal') for i,c in enumerate(CASES)]
    if stage=='stress':
        return [dict(c,stage='v8_reliability_stress',network_seed=34011000+i,
                     cluster_network='impaired') for i,c in enumerate(v8_cases('stress'))]
    rng=np.random.default_rng(31011000 if stage=='development' else 32011000)
    result=[]
    for i in range(32 if stage=='development' else 64):
        scenario=i//(8 if stage=='development' else 16)
        c=make_case('development',scenario*8)
        high=(i//2)%2 if stage=='development' else (i//8)%2
        impaired=False if stage=='development' else (i//4)%2==1
        profile=['delayed','loss','reordered','blackout','ego_blackout','command_delay'][(i+scenario)%6] if impaired else 'nominal'
        c.update(id=i,stage='v8_reliability_'+stage,mirror=int(rng.choice([-1,1])),
            speed=float(rng.uniform(12. if high else 8.,16. if high else 12.)),
            stiffness=float(rng.uniform(.75,1.25)),lateral=float(rng.uniform(.15,.45)),
            heading=float(rng.uniform(-.02,.02)),phase=float(rng.uniform(-8.,28.)),amplitude=float(rng.uniform(.9,1.3)),
            network='nominal' if profile=='command_delay' else profile,delay=.1 if profile=='command_delay' else 0.,
            npc_x_shift=float(rng.uniform(-5.,5.)),npc_speed_scale=float(rng.uniform(.75,1.25)),
            network_seed=int(rng.integers(1_000_000_000,2_000_000_000)),cluster_network='impaired' if impaired else 'nominal')
        c['lateral']*=c['mirror'];result.append(c)
    return result


def prepare():
    selected=json.loads((DATA/'calibration-v1/selection.json').read_text())['selected']
    assert selected is not None and selected['eligible']
    cbf=json.loads((DATA/'cbf-calibration-v1/selection.json').read_text())['selected']
    OUT.mkdir(parents=True,exist_ok=False)
    files=[p for p in Path(__file__).parent.iterdir() if p.suffix in ('.py','.md')]
    files.extend((ROOT/'integrations/unified_lans').glob('*.py'))
    for version in range(4,10):files.extend((ROOT/f'tools/unified_control_v{version}').glob('*.py'))
    files.extend(ROOT/name for name in ('tools/unified_campaign/study.py','tools/unified_campaign/campaign.py','controllers/lqr_controller.py','models/bicycle_model.py'))
    hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(files))}
    p=dict(selected=selected,arm=ARMS[selected['arm']],cbf=cbf,cases={s:cases(s) for s in ('development','final','v8_reserved','stress','known_crossing')},
        sources=hashes,models={seed:sha(ROOT/f'results/python-campaign-v2/policies/seed-{seed}/policy.zip') for seed in SEEDS},
        policies_changed=False,training_steps=0,expected_records=2309,seconds=6.,bootstrap_seed=41011000,
        v8_reserved_validation_only_authorized=True)
    write(OUT/'plan.json',p)
    for name in hashes:
        dest=OUT/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    return p


def initialize():
    import torch
    torch.set_num_threads(1)
    global MODELS
    MODELS={seed:load_policy(ROOT/f'results/python-campaign-v2/policies/seed-{seed}') for seed in SEEDS}


def run(job):
    stage,case,mode,actor=job;p=json.loads((OUT/'plan.json').read_text())
    directory=OUT/stage/f'{case["id"]:03d}-{mode}-{actor}';directory.mkdir(parents=True,exist_ok=False)
    params=dict(quality_factor=1.10,early_id=True,tracking_only=False)
    cls=Controller
    if mode in ('v8_original','v8_adaptive'):cls=V8
    elif mode=='v8_common':cls=Synchronous
    elif mode=='cbf':cls=CBF;params['omega']=p['cbf']['omega']
    elif mode in ('lqr','fixed','deterministic'):cls=Synchronous
    else:
        params.update(p['arm']);params.pop('sync')
    adaptive=mode in ('adaptive','hybrid','v8_common','v8_original','v8_adaptive')
    mpc=mode in ('optimized','adaptive','hybrid','v8_common','v8_original','v8_adaptive')
    params.update(adaptive=adaptive,mpc=mpc)
    label='hybrid' if mode in ACTOR_MODES else ('deterministic' if mpc else 'lqr' if mode=='cbf' else mode)
    result,rows=run_episode(case,label,MODELS.get(actor),grid=mpc,controller_factory=cls,controller_kwargs=params)
    raw=directory/'ticks.jsonl';raw.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
    result.update(mode=mode,actor=actor,stage=stage,raw_sha256=sha(raw),plan_sha256=sha(OUT/'plan.json'),
        recourse_ticks=sum(r['source']=='recovery_lqr' for r in rows),
        uncertified_recourse_ticks=sum(bool(r.get('recovery') and r['recovery']['mode']=='uncertified_emergency_improvement') for r in rows))
    write(directory/'summary.json',result);return result


def main():
    p=prepare();jobs=[]
    for stage,fixtures in p['cases'].items():
        modes=MODES if stage in ('development','final','v8_reserved') else ('lqr','optimized','adaptive','hybrid','v8_original')
        for case in fixtures:
            for mode in modes:
                for actor in SEEDS if mode in ACTOR_MODES else (0,):jobs.append((stage,case,mode,actor))
    assert len(jobs)==2309;results=[]
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn'),initializer=initialize) as pool:
        for f in as_completed([pool.submit(run,job) for job in jobs]):
            result=f.result();results.append(result)
            if len(results)%32==0:print('V8 RELIABILITY CONFIRMATION',len(results),'/2309',flush=True)
    for name,h in p['sources'].items():assert sha(ROOT/name)==h,('source changed',name)
    for stage in p['cases']:
        rr=sorted((r for r in results if r['stage']==stage),key=lambda r:(r['case']['id'],r['mode'],r['actor']))
        write(OUT/(stage+'-summary.json'),rr)
    write(OUT/'STATUS.json',dict(complete=True,episodes=len(results),training_steps=0,policies_changed=False))


if __name__=='__main__':main()
