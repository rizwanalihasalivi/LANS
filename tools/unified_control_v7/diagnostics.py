"""All prespecified phase windows and finite worker timings; JSON artifacts only."""
from pathlib import Path
import json
import numpy as np
from integrations.unified_lans.inference import sha
from .phases import rmse

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'results/causal-v7'


def load(path):return json.loads(path.read_text())


def write(path,value):
    assert not path.exists(),('Preserve existing evidence',path)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def phases(root):
    protocol=load(root/'protocol.json');records=load(root/'development_summary.json');raws={}
    for record in records:
        key=(record['case']['id'],record['mode'],record['actor'])
        raw=root/'development'/f'{key[0]:03d}-{key[1]}-{key[2]}.jsonl'
        assert sha(raw)==record['raw_sha256']
        raws[key]=[json.loads(line) for line in raw.read_text().splitlines()]
        assert abs(rmse(raws[key],0.,6.)-record['rmse_m'])<1e-12
    windows=[('whole_primary',0.,6.)]
    for cutoff in protocol['prespecified_phase_cutoffs_s']:
        windows.extend([(f'initial_0_to_{cutoff:g}',0.,cutoff),(f'later_{cutoff:g}_to_6',cutoff,6.)])
    output=[]
    for label,start,end in windows:
        values={key:rmse(rows,start,end) for key,rows in raws.items()}
        for mode in ['lqr','optimized']:
            cells={}
            for record in [r for r in records if r['mode']==mode]:
                i=record['case']['id'];reference=values[(i,mode,0)]
                hybrid=np.mean([values[(i,'hybrid',seed)] for seed in [42,43,44]])
                cells.setdefault((record['case']['scenario'],record['case']['speed']),[]).append([reference,hybrid])
            assert len(cells)==8
            pairs=np.array([np.mean(value,axis=0) for value in cells.values()])
            draw=np.random.default_rng(71413001).integers(8,size=(5000,8));boot=pairs[draw].mean(axis=1)
            gain=float(100*(1-pairs[:,1].mean()/pairs[:,0].mean()))
            if label=='whole_primary':
                original=load(root/'development_gate.json')['comparisons'][mode]['gain_percent']
                assert abs(gain-original)<1e-10
            output.append(dict(window=label,start_s=start,end_s=end,reference=mode,
                reference_mean_rmse_m=float(pairs[:,0].mean()),hybrid_mean_rmse_m=float(pairs[:,1].mean()),
                gain_percent=gain,descriptive_ci95_percent=np.quantile(100*(1-boot[:,1]/boot[:,0]),[.025,.975]).tolist(),
                secondary=label!='whole_primary',may_satisfy_primary_target=label=='whole_primary'))
    target=root/'phase_metrics.json'
    result=dict(protocol_sha256=sha(root/'protocol.json'),results=output,
        scope='All prespecified windows retained. Secondary phase gains do not satisfy the whole-episode target.')
    if target.exists():assert load(target)['results']==result['results']
    else:write(target,result)
    first_second=[]
    for record in [r for r in records if r['mode']=='lqr']:
        rows=raws[(record['case']['id'],'lqr',0)]
        first_second.append(sum(row['error']**2 for row in rows[:20])/sum(row['error']**2 for row in rows))
    progress=[];references={r['case']['id']:r for r in records if r['mode']=='lqr'}
    for record in [r for r in records if r['mode']=='hybrid']:
        baseline=references[record['case']['id']]
        if record['progress_m']/baseline['progress_m']<.99:
            progress.append(dict(case=record['case'],actor=record['actor'],
                progress_m=record['progress_m'],lqr_progress_m=baseline['progress_m'],
                progress_ratio=record['progress_m']/baseline['progress_m'],
                hybrid_rmse_m=record['rmse_m'],lqr_rmse_m=baseline['rmse_m']))
    safety={stage:load(root/f'{stage}_safety.json') for stage in
        ['regression-development','regression-stress','development','stress']}
    return dict(primary_gate=load(root/'development_gate.json'),requested_target=load(root/'requested_target.json'),
        status=load(root/'STATUS.json'),stage_safety=safety,progress_violations=progress,
        mean_per_case_lqr_first_second_squared_error_fraction=float(np.mean(first_second)),
        note='Transient fractions are descriptive; progress violations remain disqualifying.')


def runtime():
    root=DATA/'live-functional';records=load(root/'summary.json');assert len(records)==18
    output={}
    for role in ['tracking_winner','conic_engineering']:
        selected=[r for r in records if r['controller_role']==role];assert len(selected)==9
        rows=[]
        for record in selected:
            raw=root/role/f'seed-{record["seed"]}-{record["scenario"]}'/'ticks.jsonl'
            assert sha(raw)==record['raw_sha256']
            rows.extend(json.loads(line) for line in raw.read_text().splitlines())
        assert len(rows)==1080
        output[role]=dict(checks=9,ticks=1080,
            collisions=sum(row['collision'] for row in rows),
            corridor_exceedances=sum(abs(row['error'])>1.75 for row in rows),
            response_misses=sum(row['response_ms']>50 for row in rows),
            cycle_misses=sum(row['cycle_ms']>50 for row in rows),
            response_mean_ms=float(np.mean([row['response_ms'] for row in rows])),
            response_p95_ms=float(np.quantile([row['response_ms'] for row in rows],.95)),
            response_max_ms=max(row['response_ms'] for row in rows),
            cycle_max_ms=max(row['cycle_ms'] for row in rows),
            ppo_applied_ticks=sum(row['source']=='ppo' for row in rows))
    output['scope']='Fixed finite shared-cloud functional checks, not formal real-time or Webots validation. All misses retained.'
    return output


def main():
    output=dict(unique_new_simulation_episodes=1936,calibration_episodes=640,
        prospective_new_episodes=1232,shared_comparator_records_not_additional_episodes=272,
        matched_prediction_diagnosis_episodes=64,new_training_steps=0,
        cohorts={role:phases(DATA/role) for role in ['confirmation','engineering']},
        actual_worker=runtime(),reserved_opened=False,webots_run=False,
        requested_primary_target='30% whole-six-second mean episode RMSE gain over calibrated LQR, with all original constraints',
        source_sha256=sha(Path(__file__)))
    write(DATA/'diagnostics.json',output)
    for role,record in output['cohorts'].items():
        print(role,'whole-episode LQR gain',record['primary_gate']['comparisons']['lqr']['gain_percent'],
              '30% passed',record['requested_target']['passed'],flush=True)
    print(json.dumps(output['actual_worker'],indent=2),flush=True)


if __name__=='__main__':main()
