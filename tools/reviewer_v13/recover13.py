"""Reproduce the archived 7.685% result; retain every paired actor and episode."""
import boot13
from collections import Counter
import csv
import gzip
import hashlib
import json
import math
import statistics
import numpy as np
import torch
from experiment import FollowupEnv
from checkpoint12 import atomic_json, digest
from models13 import original, export, residual, logits

PARENT = 'e3a52f49930fcc3dc1ce7426dde6ea5edeec1cc8'


def main(out):
    import subprocess
    torch.set_num_threads(1)
    old = boot13.ROOT/'docs/research/reviewer-followup-v2'
    pinned = subprocess.check_output(['git','show',PARENT+':docs/research/reviewer-followup-v2/manifest.json'], cwd=boot13.ROOT)
    assert pinned == (old/'manifest.json').read_bytes()
    for name, expected in json.loads(pinned)['hashes'].items(): assert digest(boot13.ROOT/name) == expected, name
    (out/'actors').mkdir(parents=True, exist_ok=True)
    (out/'recovery').mkdir(exist_ok=True)
    rows = list(csv.DictReader((old/'episodes.csv').open()))
    chosen = [r for r in rows if (r['profile'],r['source']) in (('lqr','none'),('age_original','ppo'),('age_original','student'))]
    results = []; traces = 0; decisions = 0; comparisons = Counter(); diagnostics = {}
    for pair in range(3):
        models = {source:export(original(pair,source),student=source=='student') for source in ('ppo','student')}
        for source, model in models.items(): np.savez_compressed(out/f'actors/{source}-{pair}.npz', **model)
        for row in (r for r in chosen if int(r['pair']) == pair):
            profile, source = row['profile'], row['source']
            name = f'{row["speed"]}-{row["path"]}-{row["mirror"]}-{row["scenario"]}-{profile}-{source}'
            trace = old/f'pair-{pair}/traces/{name}.csv.gz'
            case = (int(row['speed']),row['path'],int(row['mirror']),row['scenario'],int(row['noise_id']))
            env = FollowupEnv(profile,case); obs,_ = env.reset(); recorded=[]
            with gzip.open(trace,'rt') as stream:
                for i, oldrow in enumerate(csv.DictReader(stream)):
                    available = env.ctrl.pending is None
                    res = residual(models[source],obs) if available and source in models else 0.
                    if available and source in models:
                        decisions += 1
                        if source == 'ppo':
                            alternative = residual(models['student'],obs)
                            comparisons['same_input_queries'] += 1
                            comparisons['different_actions'] += alternative != res
                    obs,_,failed,done,actual = env.step_residual(res)
                    for key in ('command','baseline','actuator','lateral_error','heading_error','steering_rate','weight','packet_seq','proposed_residual'):
                        assert abs(actual[key]-float(oldrow[key])) < 1e-11, (pair,name,i,key)
                    for j in range(20): assert actual[f'obs{j}'] == float(oldrow[f'obs{j}'])
                    assert actual['reason'] == oldrow['reason']
                    recorded.append(actual)
            assert len(recorded) == int(row['steps']) and (failed or done)
            n = len(recorded)
            mean=lambda key: statistics.mean(r[key]**2 for r in recorded)
            for key, value in [('rmse_m',math.sqrt(mean('lateral_error'))),('heading_rmse_rad',math.sqrt(mean('heading_error'))),('rate_rms_rad_s',math.sqrt(mean('steering_rate')))]:
                assert abs(value-float(row[key])) < 1e-12
            correction=np.array([r['command']-r['baseline'] for r in recorded]); delta=np.diff(np.r_[0.,correction])
            actions=np.array([r['proposed_residual'] for r in recorded if r['submitted']])
            result=dict(pair=pair,name=name,source=source,scenario=row['scenario'],steps=n,
                rmse_m=float(row['rmse_m']),heading_rmse_rad=float(row['heading_rmse_rad']),rate_rms_rad_s=float(row['rate_rms_rad_s']),
                saturated_ticks=sum(abs(r['steering_rate']) > .349 for r in recorded),
                correction_jump_energy=float(delta@delta),maximum_correction_jump=float(abs(delta).max()),
                action_switches=int(np.count_nonzero(np.diff(actions))),requests=len(actions),trace_sha256=digest(trace))
            atomic_json(out/f'recovery/{pair}-{name}.json',result);results.append(result);traces+=n
        print('recovered',pair,len(results),traces,flush=True)
    for source in ('none','ppo','student'):
        group=[r for r in results if r['source']==source]
        diagnostics[source]=dict(episodes=len(group),rmse_m=statistics.mean(r['rmse_m'] for r in group),
            rate_rms_rad_s=statistics.mean(r['rate_rms_rad_s'] for r in group),
            saturation_pct=100*sum(r['saturated_ticks'] for r in group)/sum(r['steps'] for r in group),
            correction_jump_energy=sum(r['correction_jump_energy'] for r in group),
            maximum_correction_jump=max(r['maximum_correction_jump'] for r in group),
            action_switch_fraction=sum(r['action_switches'] for r in group)/sum(r['requests'] for r in group))
    diagnostics['ppo']['gain_vs_lqr_pct']=100*(1-diagnostics['ppo']['rmse_m']/diagnostics['none']['rmse_m'])
    diagnostics['ppo']['rate_change_vs_lqr_pct']=100*(diagnostics['ppo']['rate_rms_rad_s']/diagnostics['none']['rate_rms_rad_s']-1)
    expected=json.loads((old/'summary.json').read_text())['age_original/ppo']['gain_vs_lqr_pct']
    assert abs(expected-diagnostics['ppo']['gain_vs_lqr_pct'])<1e-10
    result=dict(episodes=len(results),transitions=traces,neural_queries=decisions,all_actors_and_episodes_reproduced=True,
        diagnostics=diagnostics,same_ppo_inputs=dict(comparisons),source_sha256=digest(boot13.HERE/'recover13.py'),
        limits='Original20m/s grid, aggregate tracking gain; no balanced winner. Action drift/switch counts are descriptive; no sole-cause claim.')
    atomic_json(out/'recovered.json',result)
    atomic_json(out/'actors/manifest.json',dict(profile='causal_filter_history_v13',sha256={p.name:digest(p) for p in (out/'actors').glob('*.npz')}))
    print(json.dumps(result,indent=2))


if __name__=='__main__': main(boot13.ROOT/'docs/research/recovered-ppo-v13')
