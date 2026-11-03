"""Finite Python campaign with immutable inputs, cached episodes and explicit gates."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import time
import numpy as np
from integrations.unified_lans.inference import CONTRACT, FEATURES, sha, load_policy
from integrations.unified_lans.physics import Config
from integrations.unified_lans.run import clean
from .study import Env, make_case, run_episode

ROOT=Path(__file__).resolve().parents[2]
PROTOCOL=dict(version=2,seeds=[42,43,44],steps_per_seed=32768,seconds=6.,cases_per_stage=32,
    modes=['lqr','fixed','deterministic','optimized','ppo','hybrid'],service_s=.05,
    stages=['development','robustness','reserved_only_if_development_passes','wall_worker_only_if_development_passes',
            'webots_only_if_all_python_gates_pass'],
    gains=dict(ky=.04,kpsi=0.),optimized_grid=[-.08,-.04,0.,.04,.08],
    gate=dict(lqr_gain_percent=5.,optimized_gain_percent=1.,lower_ci_gain_positive=True,
              each_actor_gain_positive=True,max_heading_increase_percent=10.,max_rate_increase_percent=10.,
              min_progress_ratio=.99,failures=0,misses=0),
    bootstrap=dict(seed=640001,draws=5000,clusters='scenario-speed; mirror/stiffness and actors averaged within cluster'),
    selection='all final-endpoint hybrid actors evaluated; no best-seed or best-checkpoint selection',
    no_parameter_search_after_development=True,no_paid_services=True,
    interpretation='finite development campaign; logical-clock trials cannot establish real-time timing')


def write(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.pending')
    temporary.write_text(json.dumps(clean(value),indent=2,allow_nan=False)+'\n');temporary.replace(path)


def source_files():
    return sorted([*Path(__file__).parent.glob('*.py'),*(ROOT/'integrations/unified_lans').glob('*.py'),
                   ROOT/'controllers/lqr_controller.py',ROOT/'models/bicycle_model.py'])


def prepare(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    hashes={str(p.relative_to(ROOT)):sha(p) for p in source_files()}
    write(root/'protocol.json',dict(protocol=PROTOCOL,source_hashes=hashes,config=asdict(Config()),
                                  platform=platform.platform(),python=platform.python_version()))
    for p in source_files():
        target=root/'source'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    write(root/'status.json',dict(stage='prepared',webots='NOT_RUN',promotion=False))
    return root


def check(root):
    root=Path(root);record=json.loads((root/'protocol.json').read_text())
    assert record['protocol']==PROTOCOL,'Protocol changed; preserve this run and create a new version'
    for name,h in record['source_hashes'].items():assert sha(ROOT/name)==h,('Source changed',name)
    return root


def train(root):
    import torch
    import stable_baselines3
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback
    torch.set_num_threads(1);root=check(root)
    class Checkpoint(BaseCallback):
        def __init__(self,folder):super().__init__();self.folder=folder
        def _on_step(self):
            if self.num_timesteps%8192==0:
                self.model.save(self.folder/f'checkpoint-{self.num_timesteps}.zip')
                print('CHECKPOINT',self.folder.name,self.num_timesteps,flush=True)
            return True
    for seed in PROTOCOL['seeds']:
        folder=root/'policies'/f'seed-{seed}'
        if (folder/'manifest.json').exists():
            model=load_policy(folder);assert model.num_timesteps==PROTOCOL['steps_per_seed'];continue
        folder.mkdir(parents=True,exist_ok=False)
        write(root/'status.json',dict(stage='training',seed=seed,webots='NOT_RUN',promotion=False))
        env=Env();model=PPO('MlpPolicy',env,seed=seed,device='cpu',n_steps=128,batch_size=64,n_epochs=3,
            learning_rate=3e-4,policy_kwargs=dict(net_arch=[32,32]),verbose=0)
        model.learn(total_timesteps=PROTOCOL['steps_per_seed'],callback=Checkpoint(folder))
        model.save(folder/'policy.zip')
        write(folder/'manifest.json',dict(contract=CONTRACT,features=FEATURES,scale_rad=.08,
            policy_sha256=sha(folder/'policy.zip'),seed=seed,steps=int(model.num_timesteps),config=asdict(Config()),
            purpose='predeclared_python_development_endpoint',protocol_sha256=sha(root/'protocol.json'),
            source_hashes=json.loads((root/'protocol.json').read_text())['source_hashes'],
            versions=dict(python=platform.python_version(),sb3=stable_baselines3.__version__,torch=torch.__version__),
            credit='submitted request; reward from actual gated delayed transition; synchronous training'))
        env.close();print('TRAIN COMPLETE',seed,model.num_timesteps,flush=True)


def evaluate(root,stage):
    import torch
    torch.set_num_threads(1);root=check(root)
    if stage=='reserved':
        gate=json.loads((root/'development_gate.json').read_text())
        assert gate['passed'],'Reserved data remain unopened: development gate failed'
    models={seed:load_policy(root/'policies'/f'seed-{seed}') for seed in PROTOCOL['seeds']}
    dest=root/stage;dest.mkdir(exist_ok=True);results=[]
    for index in range(PROTOCOL['cases_per_stage']):
        case=make_case(stage,index)
        for mode in PROTOCOL['modes']:
            for actor in (PROTOCOL['seeds'] if mode in ('ppo','hybrid') else [0]):
                key=f'{index:03d}-{mode}-{actor}';meta=dest/(key+'.json');raw=dest/(key+'.jsonl')
                if meta.exists():
                    summary=json.loads(meta.read_text());assert sha(raw)==summary['raw_sha256']
                    assert summary['case']==case and summary['protocol_sha256']==sha(root/'protocol.json')
                else:
                    if raw.exists():raise RuntimeError('Preserve interrupted raw file and diagnose: '+str(raw))
                    result,rows=run_episode(case,'deterministic' if mode=='optimized' else mode,
                        models.get(actor),grid=mode=='optimized',seconds=PROTOCOL['seconds'])
                    raw.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
                    summary=dict(**result,actor=actor,protocol_sha256=sha(root/'protocol.json'),raw_sha256=sha(raw))
                    write(meta,summary)
                results.append(summary)
        write(root/'status.json',dict(stage=stage,completed_cases=index+1,total_cases=PROTOCOL['cases_per_stage'],
                                      webots='NOT_RUN',promotion=False))
        print(stage,'CASE COMPLETE',index+1,flush=True)
    write(root/(stage+'_summary.json'),results)
    return results


def assess(results):
    baselines={mode:{r['case']['id']:r for r in results if r['mode']==mode}
               for mode in ['lqr','fixed','deterministic','optimized']}
    actor_rows={seed:{r['case']['id']:r for r in results if r['mode']=='hybrid' and r['actor']==seed}
                for seed in PROTOCOL['seeds']}
    ids=sorted(baselines['lqr']);assert len(ids)==PROTOCOL['cases_per_stage']
    for rows in actor_rows.values():assert sorted(rows)==ids
    reasons=[];comparisons={};per_actor={}
    for mode in ('lqr','optimized'):
        cluster={}
        for i in ids:
            ref=baselines[mode][i];case=ref['case'];key=(case['scenario'],case['speed'])
            value=np.mean([rows[i]['rmse_m'] for rows in actor_rows.values()])
            cluster.setdefault(key,[]).append((ref['rmse_m'],value))
        pairs=np.array([np.mean(v,axis=0) for v in cluster.values()])
        rng=np.random.default_rng(PROTOCOL['bootstrap']['seed']);draw=rng.integers(len(pairs),size=(5000,len(pairs)))
        boot=pairs[draw].mean(axis=1);gains=100*(1-boot[:,1]/boot[:,0])
        means=pairs.mean(axis=0);gain=100*(1-means[1]/means[0]);ci=np.quantile(gains,[.025,.975])
        comparisons[mode]=dict(gain_percent=float(gain),ci95_percent=ci.tolist(),clusters=len(pairs))
        target=PROTOCOL['gate'][mode+'_gain_percent']
        if gain<target:reasons.append(f'gain_vs_{mode}_below_{target}_percent')
        if ci[0]<=0:reasons.append(f'lower_ci_vs_{mode}_not_positive')
    for seed,rows in actor_rows.items():
        value=np.mean([r['rmse_m'] for r in rows.values()]);base=np.mean([r['rmse_m'] for r in baselines['lqr'].values()])
        per_actor[str(seed)]=float(100*(1-value/base))
        if value>=base:reasons.append(f'actor_{seed}_no_positive_lqr_gain')
        for metric in ('heading_rms','rate_rms'):
            a=np.mean([r[metric] for r in rows.values()]);b=np.mean([r[metric] for r in baselines['lqr'].values()])
            if a>b*1.10+1e-12:reasons.append(f'actor_{seed}_{metric}_increase_over_10_percent')
        for i,row in rows.items():
            if row['failed']:reasons.append(f'actor_{seed}_failed_case_{i}')
            if row['progress_m']<.99*baselines['lqr'][i]['progress_m']:
                reasons.append(f'actor_{seed}_progress_regression_case_{i}')
    return dict(passed=not reasons,comparisons=comparisons,per_actor_lqr_gain_percent=per_actor,
                reasons=sorted(set(reasons)),selected_controller='all three final hybrid endpoints',
                scope='development promotion gate, correlated finite simulation grid; not universal superiority')


def robustness(root):
    import torch
    torch.set_num_threads(1);root=check(root);dest=root/'robustness';dest.mkdir(exist_ok=True)
    models={seed:load_policy(root/'policies'/f'seed-{seed}') for seed in PROTOCOL['seeds']};results=[]
    profiles=['delayed','loss','reordered','blackout','ego_blackout','command_delay']
    for scenario_index in range(4):
        for profile_index,profile in enumerate(profiles):
            case=make_case('development',scenario_index*8);case.update(id=scenario_index*6+profile_index,
                stage='robustness',speed=12.,stiffness=.8,network='nominal' if profile=='command_delay' else profile,
                delay=.1 if profile=='command_delay' else 0.,network_seed=510000+scenario_index*6+profile_index)
            for mode,actor in [('lqr',0),*[('hybrid',s) for s in PROTOCOL['seeds']]]:
                key=f"{case['id']:03d}-{mode}-{actor}";meta=dest/(key+'.json');raw=dest/(key+'.jsonl')
                if meta.exists():
                    summary=json.loads(meta.read_text());assert summary['case']==case and sha(raw)==summary['raw_sha256']
                else:
                    if raw.exists():raise RuntimeError('Preserve interrupted raw file: '+str(raw))
                    result,rows=run_episode(case,mode,models.get(actor),seconds=PROTOCOL['seconds'])
                    raw.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
                    summary=dict(**result,actor=actor,protocol_sha256=sha(root/'protocol.json'),raw_sha256=sha(raw));write(meta,summary)
                results.append(summary)
            print('robustness CASE COMPLETE',case['id']+1,flush=True)
    write(root/'robustness_summary.json',results);a=audit(root,'robustness')
    failed=[dict(case=r['case'],actor=r['actor']) for r in results if r['mode']=='hybrid' and r['failed']]
    write(root/'robustness_gate.json',dict(passed=not failed,failed=failed,episodes=len(results),audit=a,
        scope='logical-time network/command-delay stress; real-worker crash/stall requires separate wall-clock stage'))
    return not failed


def audit(root,stage):
    from integrations.unified_lans.physics import advance, errors
    from .study import setup
    root=check(root);results=json.loads((root/(stage+'_summary.json')).read_text());ticks=0
    expected=96 if stage=='robustness' else PROTOCOL['cases_per_stage']*10;assert len(results)==expected
    keys=set()
    for result in results:
        key=f"{result['case']['id']:03d}-{result['mode']}-{result['actor']}";assert key not in keys;keys.add(key)
        path=root/stage/(key+'.jsonl');assert sha(path)==result['raw_sha256']
        rows=[json.loads(s) for s in path.read_text().splitlines()]
        pipe,clock,ego,npcs,net=setup(result['case'])
        prior=0.;sse=0.
        for i,r in enumerate(rows):
            assert r['tick']==i and r['time_s']==i*.05
            np.testing.assert_allclose(r['state_before'],ego,rtol=0,atol=1e-12)
            command=Command(r['applied_steering'],r['applied_accel'])
            assert abs(command.steering-prior)<=.6*.05+1e-10 and abs(command.steering)<=.5
            assert -6<=command.accel<=2.5;prior=command.steering
            ego=advance(ego,command,.05,result['case']['stiffness'])
            np.testing.assert_allclose(ego,r['state_after'],rtol=0,atol=1e-12)
            err,_=errors(ego,pipe.route);assert abs(err[0]-r['error'])<1e-12
            if r['source']=='ppo':assert r['proposal_age']<.15 and r['proposal_wall_age']<.15 and r['risk']!='DANGER'
            if r['missing']:assert r['source'] in ('lqr','hold_brake') and r['issued_accel']==-6.
            sse+=r['error']**2
        n=result['expected_ticks'];rmse=math.sqrt((sse+(n-len(rows))*2.5**2)/n)
        assert abs(rmse-result['rmse_m'])<1e-12;ticks+=len(rows)
    output=dict(passed=True,episodes=len(results),ticks=ticks,protocol_sha256=sha(root/'protocol.json'))
    write(root/(stage+'_audit.json'),output);return output


def report(root,stage):
    root=check(root);results=json.loads((root/(stage+'_summary.json')).read_text())
    audit_result=audit(root,stage);gate=assess(results);write(root/(stage+'_gate.json'),gate)
    text=['# Python-first campaign results','',f'Stage: {stage}. Episodes: {len(results)}. Audited ticks: {audit_result["ticks"]}.',
          '',f'**Promotion gate: {"PASS" if gate["passed"] else "FAIL"}.**','',
          '| Controller | Mean RMSE (m) | Failed cases | Mean progress (m) |','|---|---:|---:|---:|']
    for mode in PROTOCOL['modes']:
        rows=[r for r in results if r['mode']==mode]
        text.append(f'| {mode} | {np.mean([r["rmse_m"] for r in rows]):.6f} | {sum(r["failed"] for r in rows)}/{len(rows)} | {np.mean([r["progress_m"] for r in rows]):.3f} |')
    text+=['','Hybrid gains and cluster-bootstrap 95% intervals:',json.dumps(gate['comparisons'],indent=2),'',
           'Per-actor LQR-relative gain (%): '+json.dumps(gate['per_actor_lqr_gain_percent']),'',
           'Gate reasons:',*['- '+r for r in gate['reasons']],'',
           'All outcomes retained. Logical-time performance supplies no measured real-time guarantee.',
           'Reserved data, real-worker final confirmation and native Webots remain conditional on Python gates.']
    (root/(stage+'_REPORT.md')).write_text('\n'.join(text)+'\n')
    write(root/'status.json',dict(stage=stage+'_complete',promotion=gate['passed'],webots='NOT_RUN',gate_reasons=gate['reasons']))
    print(json.dumps(gate,indent=2),flush=True);return gate


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','train','development','robustness','reserved','report','all'])
    p.add_argument('--output',required=True);p.add_argument('--stage',default='development',choices=['development','reserved'])
    a=p.parse_args();root=Path(a.output)
    if a.command=='prepare':prepare(root)
    elif a.command=='train':train(root)
    elif a.command=='robustness':robustness(root)
    elif a.command in ('development','reserved'):evaluate(root,a.command);report(root,a.command)
    elif a.command=='report':report(root,a.stage)
    else:
        if not root.exists():prepare(root)
        train(root);evaluate(root,'development');gate=report(root,'development');stress_pass=robustness(root)
        if gate['passed'] and stress_pass:evaluate(root,'reserved');report(root,'reserved')
        else:print('STOP: reserved/Webots gates remain closed; no thresholds or cases were changed.',flush=True)


if __name__=='__main__':main()
