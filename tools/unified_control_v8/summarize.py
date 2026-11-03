"""Compact machine-readable audit summary, without thesis assets."""
from pathlib import Path
import json
import numpy as np
from integrations.unified_lans.inference import sha

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'results/causal-v8'


def load(path):return json.loads(path.read_text())


def main():
    root=DATA/'confirmation';comparisons=load(root/'development_all_comparisons.json')
    runtime_root=DATA/'live-functional';records=load(runtime_root/'summary.json');assert len(records)==9
    ticks=[]
    for record in records:
        raw=runtime_root/record['controller_role']/f'seed-{record["seed"]}-{record["scenario"]}'/'ticks.jsonl'
        assert sha(raw)==record['raw_sha256'];ticks.extend(json.loads(line) for line in raw.read_text().splitlines())
    assert len(ticks)==1080
    runtime=dict(checks=9,ticks=len(ticks),response_misses=sum(r['response_ms']>50 for r in ticks),
        cycle_misses=sum(r['cycle_ms']>50 for r in ticks),response_mean_ms=float(np.mean([r['response_ms'] for r in ticks])),
        response_p95_ms=float(np.quantile([r['response_ms'] for r in ticks],.95)),response_max_ms=max(r['response_ms'] for r in ticks),
        cycle_max_ms=max(r['cycle_ms'] for r in ticks),collisions=sum(r['collision'] for r in ticks),
        corridor_exceedances=sum(abs(r['error'])>1.75 for r in ticks),ppo_applied_ticks=sum(r['source']=='ppo' for r in ticks))
    quality={name:dict(mean_heading_no_worse=c['mean_heading_ratio']<=1.,mean_rate_no_worse=c['mean_rate_ratio']<=1.,
        every_cell_progress_at_least_99_percent=c['minimum_cell_actor_progress_ratio']>=.99) for name,c in comparisons['comparisons'].items()}
    result=dict(selected=load(DATA/'calibration/selection.json')['selected'],simulation_episodes=1431,
        training_steps_added=0,prospective_episodes=848,calibration_episodes=576,known_regression_episodes=7,
        safety={s:load(root/f'{s}_safety.json') for s in ['regression-development','regression-stress','development','stress']},
        original_gate=load(root/'development_gate.json'),requested_target=load(root/'requested_target.json'),
        comparisons=comparisons,quality_no_regression_flags=quality,actual_worker=runtime,
        status=load(root/'STATUS.json'),analysis_source_sha256=sha(Path(__file__)),
        note='All seven whole-run references retained. Functional timings are finite cloud measurements, not formal or native validation.')
    path=DATA/'diagnostics.json';assert not path.exists();path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(runtime,indent=2),flush=True)
    for name,c in comparisons['comparisons'].items():print(name,c['gain_percent'],c['ci95_percent'],flush=True)


if __name__=='__main__':main()
