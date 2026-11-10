"""One prospective confirmation of the analytical V2 traffic repair."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import json,multiprocessing as mp,shutil
import numpy as np
from integrations.unified_lans.run import clean
from tools.unified_control_v9.learning import run_episode
from tools.unified_control_v8.control import Controller as V8
from tools.unified_control_v8.campaign import cases as v8_cases
from tools.unified_campaign.study import make_case
from . import confirm as prior
from .traffic_guard import Controller,Synchronous,CBF
from .calibrate import write,sha

OUT=prior.DATA/'confirmation-v2'


def cases():
    rng=np.random.default_rng(36111000);final=[]
    for i in range(64):
        scenario=i//16;high=(i//8)%2;impaired=(i//4)%2==1
        profile=['delayed','loss','reordered','blackout','ego_blackout','command_delay'][(i+scenario)%6] if impaired else 'nominal'
        c=make_case('development',scenario*8)
        c.update(id=i,stage='v2_independent_final',mirror=int(rng.choice([-1,1])),speed=float(rng.uniform(12. if high else 8.,16. if high else 12.)),
            stiffness=float(rng.uniform(.75,1.25)),lateral=float(rng.uniform(.15,.45)),heading=float(rng.uniform(-.02,.02)),
            phase=float(rng.uniform(-8.,28.)),amplitude=float(rng.uniform(.9,1.3)),network='nominal' if profile=='command_delay' else profile,
            delay=.1 if profile=='command_delay' else 0.,npc_x_shift=float(rng.uniform(-5.,5.)),npc_speed_scale=float(rng.uniform(.75,1.25)),
            network_seed=int(rng.integers(1_000_000_000,2_000_000_000)),cluster_network='impaired' if impaired else 'nominal')
        c['lateral']*=c['mirror'];final.append(c)
    stress=[dict(c,stage='v2_regression_stress',network_seed=37111000+i,cluster_network='impaired') for i,c in enumerate(v8_cases('stress'))]
    return dict(final=final,stress=stress)


def prepare():
    assert json.loads((prior.DATA/'v2-exposed-development/STATUS.json').read_text())['development_pass']
    p=json.loads((prior.DATA/'confirmation-v1/plan.json').read_text());OUT.mkdir(exist_ok=False)
    files=[prior.ROOT/name for name in p['sources']];files.extend(Path(__file__).parent.glob('*.py'));files.extend(Path(__file__).parent.glob('*.md'))
    hashes={str(f.relative_to(prior.ROOT)):sha(f) for f in sorted(set(files))}
    plan=dict(cases=cases(),arm=p['arm'],cbf=p['cbf'],source_hashes=hashes,models=p['models'],expected_records=1240,bootstrap_seed=42011000,
        policies_changed=False,training_steps=0,exposed_development_plan_sha256=sha(prior.DATA/'v2-exposed-development/plan.json'))
    write(OUT/'plan.json',plan)
    for name in hashes:
        d=OUT/'source'/name;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(prior.ROOT/name,d)
    return plan


def run(job):
    stage,c,mode,actor=job;p=json.loads((OUT/'plan.json').read_text());dest=OUT/stage/f'{c["id"]:03d}-{mode}-{actor}';dest.mkdir(parents=True)
    cls=Controller;kw=dict(quality_factor=1.1,early_id=True,tracking_only=False)
    if mode in ('v8_original','v8_adaptive'):cls=V8
    elif mode=='v8_common' or mode in ('lqr','fixed','deterministic'):cls=Synchronous
    elif mode=='cbf':cls=CBF;kw['omega']=p['cbf']['omega']
    else:kw.update(p['arm']);kw.pop('sync')
    adaptive=mode in ('adaptive','hybrid','v8_common','v8_original','v8_adaptive');mpc=mode in ('optimized','adaptive','hybrid','v8_common','v8_original','v8_adaptive')
    kw.update(adaptive=adaptive,mpc=mpc)
    label='hybrid' if mode in prior.ACTOR_MODES else 'deterministic' if mpc else 'lqr' if mode=='cbf' else mode
    r,rows=run_episode(c,label,prior.MODELS.get(actor),grid=mpc,controller_factory=cls,controller_kwargs=kw)
    raw=dest/'ticks.jsonl';raw.write_text(''.join(json.dumps(clean(x),allow_nan=False)+'\n' for x in rows))
    r.update(mode=mode,actor=actor,stage=stage,raw_sha256=sha(raw),plan_sha256=sha(OUT/'plan.json'),
        recourse_ticks=sum(x['source']=='recovery_lqr' for x in rows),
        uncertified_recourse_ticks=sum(bool(x.get('recovery') and x['recovery']['mode']=='uncertified_emergency_improvement') for x in rows))
    write(dest/'summary.json',r);return r


def main():
    p=prepare();jobs=[]
    for stage,cc in p['cases'].items():
        for c in cc:
            for mode in prior.MODES if stage=='final' else ('lqr','optimized','adaptive','hybrid','v8_original'):
                for a in prior.SEEDS if mode in prior.ACTOR_MODES else (0,):jobs.append((stage,c,mode,a))
    assert len(jobs)==1240;results=[]
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn'),initializer=prior.initialize) as pool:
        for i,f in enumerate(as_completed([pool.submit(run,j) for j in jobs]),1):
            results.append(f.result())
            if i%32==0:print('V2 FROZEN CONFIRMATION',i,'/1240',flush=True)
    for name,h in p['source_hashes'].items():assert sha(prior.ROOT/name)==h,('source changed',name)
    for stage in p['cases']:
        rr=sorted((r for r in results if r['stage']==stage),key=lambda r:(r['case']['id'],r['mode'],r['actor']));write(OUT/(stage+'-summary.json'),rr)
    write(OUT/'STATUS.json',dict(completed=True,episodes=1240,policies_changed=False,training_steps=0,final_once_complete=True))


if __name__=='__main__':main()
