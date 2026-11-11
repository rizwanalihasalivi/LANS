"""Conditional fixed-prefix bound for the original scalar steering architecture.

This is a relaxed bound on already-open training data, not a global controller
impossibility theorem. It permits zero error after the first possible command
change and ignores later quality/traffic constraints, so it is optimistic.
"""
from pathlib import Path
import json,math
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.physics import Command,Config,constrain
from tools.unified_control_v4.control import ScheduledLQR

ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path('/workspace/LANS/results/causal-v8/calibration')
OUT=ROOT/'results/ppo-plan-v11/scalar-prefix-bound'


def main():
    OUT.mkdir(parents=True,exist_ok=False);results=[];hashes={}
    for path in sorted(SOURCE.glob('conic-v8-early-id-adaptive-*.json')):
        meta=json.loads(path.read_text());raw=path.with_suffix('.jsonl');assert sha(raw)==meta['raw_sha256']
        rows=[json.loads(line) for line in raw.read_text().splitlines()];case=meta['case'];prefix=0;previous=Command()
        hashes[str(path)]=sha(path);hashes[str(raw)]=sha(raw)
        if .05+case['delay']>=.15-1e-9:prefix=meta['expected_ticks']
        else:
            assert case['delay']==0.,'This diagnostic has no delayed forecast reconstruction outside the no-authority case'
            baseline=ScheduledLQR(16.)
            for i,row in enumerate(rows):
                baseline.stiffness=float(np.clip(round(row['stiffness_estimate']*20)/20,.7,1.3))
                from tools.unified_campaign.study import StudyRoute
                kind={'following':'straight','crossing':'straight','merge':'lane_change','curved':'sine'}[case['scenario']]
                route=StudyRoute(kind,case['mirror'],case['phase'],case['amplitude'])
                base=baseline(np.asarray(row['state_before']),route)
                low=constrain(Command(base-.08,0.),previous,Config()).steering
                high=constrain(Command(base+.08,0.),previous,Config()).steering
                assert low-1e-12<=row['issued_steering']<=high+1e-12
                available=i>=1 and row['risk']!='DANGER' and not row['ego_backup']
                # End early whenever longitudinal equivalence cannot be inferred
                # from a feasible baseline. This weakens, never tightens, the bound.
                if available and (not row['eligible'].get('lqr',False) or high-low>1e-12):break
                prefix+=1;previous=Command(row['issued_steering'],row['issued_accel'])
        n=meta['expected_ticks'];fixed_sse=sum(r['error']**2 for r in rows[:prefix])
        if prefix==n:fixed_sse+=(n-len(rows))*6.25
        lower=math.sqrt(fixed_sse/n)
        assert lower<=meta['rmse_m']+1e-12
        results.append(dict(case=case,unmodifiable_prefix_ticks=prefix,baseline_rmse_m=meta['rmse_m'],optimistic_floor_m=lower))
    assert len(results)==64
    mean=float(np.mean([r['baseline_rmse_m'] for r in results]));floor=float(np.mean([r['optimistic_floor_m'] for r in results]))
    report=dict(cases=64,baseline_mean_rmse_m=mean,optimistic_mean_rmse_floor_m=floor,
        conditional_max_gain_percent=100*(1-floor/mean),full_no_authority_cases=sum(r['unmodifiable_prefix_ticks']==120 for r in results),
        rows=results,input_hashes=hashes,source_sha256=sha(__file__),
        assumptions=['Valid finite scalar +/-0.08 proposals; fixed 50ms service; strict 150ms issue TTL.',
            'Unchanged v8 plant, observation/model estimator, analytical path and longitudinal supervision.',
            'No intentional worker failure or timestamp rewriting; ideal nominal sensor packets as in these fixtures.'],
        limitation='Conditional optimistic relaxation on opened training fixtures; not an attained PPO gain or global impossibility proof.')
    (OUT/'bound.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows','input_hashes')},indent=2))


if __name__=='__main__':main()
