"""Prospective causal-controller comparison; all original and requested gates kept."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict,replace
from pathlib import Path
import argparse,json,multiprocessing as mp,shutil
import numpy as np
from integrations.unified_lans.physics import Config
from integrations.unified_lans.inference import sha,load_policy
from integrations.unified_lans.run import clean
from tools.unified_campaign import study
from tools.unified_control_v4 import campaign as audit_tools
from tools.unified_control_v6.control import Controller as Legacy
from .control import Controller

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'results/causal-v7/confirmation'
MODES=['lqr','fixed','deterministic','optimized','adaptive','ppo','hybrid']
_models=None


def choice():
    path=ROOT/'results/causal-v7/calibration/selection.json';selected=json.loads(path.read_text())['selected']
    assert selected is not None,'No predeclared training candidate passed the original actual constraints'
    return selected


def make_controller(*args,adaptive=False,mpc=False,selection=None,**kwargs):
    selected=choice() if selection is None else selection;args=list(args)
    if kwargs.pop('penalty',16.)!=16.:raise ValueError('all v7 comparisons require shared R=16')
    if len(args)>2:args[2]=replace(args[2],horizon=selected['horizon'])
    elif kwargs.get('cfg') is not None:kwargs['cfg']=replace(kwargs['cfg'],horizon=selected['horizon'])
    cls=Legacy if selected['factor'] is None else Controller
    if selected['factor'] is not None:kwargs['quality_factor']=selected['factor']
    return cls(*args,penalty=16.,adaptive=adaptive,mpc=mpc,**kwargs)


def cases(stage):
    if stage.startswith('regression'):return audit_tools.cases(stage)
    if stage=='stress':
        result=[]
        for s in range(4):
            for j,profile in enumerate(['delayed','loss','reordered','blackout','ego_blackout','command_delay']):
                c=study.make_case('development',s*8)
                c.update(id=s*6+j,stage='v7_stress',speed=12.,phase=14.,amplitude=1.2,
                    lateral=.3*c['mirror'],heading=.005*c['mirror'],stiffness=.8,
                    network='nominal' if profile=='command_delay' else profile,
                    delay=.1 if profile=='command_delay' else 0.,network_seed=72413000+s*6+j)
                result.append(c)
        return result
    reserved=stage=='reserved';rng=np.random.default_rng(94413000 if reserved else 71413000);result=[]
    for i in range(32):
        c=study.make_case('reserved' if reserved else 'development',i)
        c.update(stage='v7_'+stage,lateral=float(rng.uniform(.15,.45))*c['mirror'],heading=float(rng.uniform(-.015,.015)),
            phase=26. if reserved else 14.,amplitude=1.3 if reserved else 1.2,
            network_seed=(95413000 if reserved else 73413000)+i)
        result.append(c)
    return result


def write(path,value):
    path=Path(path);temporary=path.with_suffix('.pending')
    temporary.write_text(json.dumps(clean(value),indent=2,allow_nan=False)+'\n');temporary.replace(path)


def prepare(root,engineering=False):
    root.mkdir(parents=True,exist_ok=False);selected=choice()
    if engineering:
        selected=next(s for s in json.loads((ROOT/'results/causal-v7/calibration/selection.json').read_text())['scores'] if s['name']=='conic-h2-q110')
        assert selected['failures']==0 and selected['heading_ratio']<=1.10 and selected['rate_ratio']<=1.10 and selected['minimum_progress_ratio']>=.99
    files=[*Path(__file__).parent.glob('*.py'),Path(__file__).parent/'PROTOCOL.md',Path(__file__).parent/'ENGINEERING_PROTOCOL.md',
        *(ROOT/'tools/unified_control_v4').glob('*.py'),*(ROOT/'tools/unified_control_v5').glob('*.py'),
        *(ROOT/'tools/unified_control_v6').glob('*.py'),*(ROOT/'integrations/unified_lans').glob('*.py'),
        ROOT/'tools/unified_campaign/study.py',ROOT/'tools/unified_campaign/campaign.py',
        ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py']
    protocol=dict(version=7,selected=selected,controller_role='fixed_engineering_alternative' if engineering else 'tracking_calibration_winner',config=asdict(Config(horizon=selected['horizon'])),
        calibration_sha256=sha(ROOT/'results/causal-v7/calibration/selection.json'),modes=MODES,seeds=[42,43,44],seconds=6.,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in files},
        models={s:sha(ROOT/f'results/python-campaign-v2/policies/seed-{s}/policy.zip') for s in [42,43,44]},
        original_gate=audit_tools.OLD_PROTOCOL['gate'],requested_lqr_gain_percent=30.,new_training_steps=0,
        development=dict(namespace=71413000,phase=14.,amplitude=1.2),reserved=dict(namespace=94413000,phase=26.,amplitude=1.3),
        prespecified_phase_cutoffs_s=[.5,1.,2.],primary_metric='whole six-second failure-penalized mean episode RMSE',
        secondary_phase_cannot_replace_primary=True,all_endpoints_no_seed_selection=True)
    write(root/'protocol.json',protocol)
    for p in files:
        target=root/'source'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    return protocol


def initialize():
    import torch
    global _models
    torch.set_num_threads(1);_models={s:load_policy(ROOT/f'results/python-campaign-v2/policies/seed-{s}') for s in [42,43,44]}


def worker(job):
    root,stage,case,mode,actor=job;root=Path(root);key=f'{case["id"]:03d}-{mode}-{actor}'
    raw=root/stage/(key+'.jsonl');meta=root/stage/(key+'.json')
    if meta.exists():
        result=json.loads(meta.read_text());assert result['case']==case and sha(raw)==result['raw_sha256'];return str(root),stage,result
    assert not raw.exists(),('Preserve interrupted evidence',raw)
    selected=json.loads((root/'protocol.json').read_text())['selected']
    def factory(*args,**kwargs):return make_controller(*args,selection=selected,adaptive=mode in ('adaptive','hybrid'),mpc=mode in ('optimized','adaptive','hybrid'),**kwargs)
    study.Pipeline=factory
    result,rows=study.run_episode(case,'deterministic' if mode in ('optimized','adaptive') else mode,
        _models.get(actor),grid=mode in ('optimized','adaptive','hybrid'),seconds=6.)
    result['mode']=mode
    raw.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
    result.update(actor=actor,raw_sha256=sha(raw),protocol_sha256=sha(root/'protocol.json'));write(meta,result)
    return str(root),stage,result


def evaluate(root,stages,engineering_root=None):
    roots=[root]+([engineering_root] if engineering_root is not None else [])
    jobs=[];results={str(r):{stage:[] for stage in stages} for r in roots}
    for r in roots:
        for stage in stages:
            (r/stage).mkdir(exist_ok=True)
            modes=MODES if stage in ('development','reserved') else ['lqr','optimized','hybrid']
            if r==engineering_root:modes=[m for m in modes if m in ('optimized','adaptive','hybrid')]
            for c in cases(stage):
                for mode in modes:
                    for actor in [42,43,44] if mode in ('ppo','hybrid') else [0]:jobs.append((str(r),stage,c,mode,actor))
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn'),initializer=initialize) as pool:
        done=0
        for future in as_completed([pool.submit(worker,j) for j in jobs]):
            r,stage,result=future.result();results[r][stage].append(result);done+=1
            if done%32==0:print('CAUSAL COMPARISON',done,'/',len(jobs),flush=True)
    if engineering_root is not None:
        for stage in stages:
            for record in results[str(root)][stage]:
                if record['mode'] in ('optimized','adaptive','hybrid'):continue
                key=f'{record["case"]["id"]:03d}-{record["mode"]}-{record["actor"]}'
                raw=root/stage/(key+'.jsonl');target=engineering_root/stage/raw.name
                if target.exists():assert sha(target)==sha(raw)
                else:shutil.copyfile(raw,target)
                shared=dict(record,protocol_sha256=sha(engineering_root/'protocol.json'),shared_comparator_source=str(raw.relative_to(ROOT)))
                write(engineering_root/stage/(key+'.json'),shared);results[str(engineering_root)][stage].append(shared)
    for r in roots:
        for stage,records in results[str(r)].items():
            records.sort(key=lambda x:(x['case']['id'],x['mode'],x['actor']))
            write(r/f'{stage}_summary.json',records);audit_tools.audit(r,stage,records);audit_tools.summary(r,stage,records)
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',default=str(OUTPUT));args=parser.parse_args();root=Path(args.output)
    protocol=prepare(root) if not root.exists() else json.loads((root/'protocol.json').read_text())
    for name,h in protocol['source_hashes'].items():assert sha(ROOT/name)==h,('source changed',name)
    for seed,h in protocol['models'].items():assert sha(ROOT/f'results/python-campaign-v2/policies/seed-{seed}/policy.zip')==h
    engineering=root.parent/'engineering';ep=prepare(engineering,True) if not engineering.exists() else json.loads((engineering/'protocol.json').read_text())
    for name,h in ep['source_hashes'].items():assert sha(ROOT/name)==h,('source changed',name)
    results=evaluate(root,['regression-development','regression-stress','development','stress'],engineering)
    for r in [root,engineering]:
        gate=json.loads((r/'development_gate.json').read_text());gain=gate['comparisons']['lqr']['gain_percent']
        requested=dict(passed=bool(gate['passed'] and gain>=30.),original_gate_passed=gate['passed'],lqr_gain_percent=gain,target_percent=30.)
        write(r/'requested_target.json',requested)
        safe=all(json.loads((r/f'{stage}_safety.json').read_text())['passed'] for stage in ['regression-development','regression-stress','stress'])
        if requested['passed'] and safe and r==root:evaluate(r,['reserved'])
        write(r/'STATUS.json',dict(original_development_gate_passed=gate['passed'],requested_30_percent_passed=requested['passed'],
            reserved='completed' if requested['passed'] and safe and r==root else 'NOT_RUN',formal_wall_worker='NOT_RUN',webots='NOT_RUN'))


if __name__=='__main__':main()
