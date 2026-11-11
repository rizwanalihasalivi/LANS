"""Preserve the shared collision that no fresh learned proposal can influence."""
import json
from pathlib import Path
import numpy as np
from integrations.unified_lans.inference import sha
from tools.ppo_plan_v11.probe import dump
from .train import DATA


def main():
    out=DATA/'evaluation';records=json.loads((out/'summary.json').read_text())
    failed=[r for r in records if r['failed']]
    assert len(failed)==14 and {r['case']['id'] for r in failed}=={53}
    case=failed[0]['case'];assert case['scenario']=='crossing' and case['delay']==.1
    base=next(r for r in failed if r['mode']=='adaptive');reference_path=out/'053-adaptive-0.jsonl'
    reference=[json.loads(v) for v in reference_path.read_text().splitlines()];sources=[]
    columns=('issued_steering','issued_accel','applied_steering','applied_accel')
    first=next(r for r in reference if r['collision']);assert first['time_s']==46*.05
    for record in failed:
        path=out/f'053-{record["mode"]}-{record["seed"]}.jsonl';assert sha(path)==record['raw_sha256']
        rows=[json.loads(v) for v in path.read_text().splitlines()]
        assert len(rows)==47 and sum(r['collision'] for r in rows)==1 and not any(r['corridor_exceeded'] for r in rows)
        assert not any(r['source'] in ('ppo','ppo_plan') for r in rows)
        if record['mode']!='lqr':
            np.testing.assert_allclose([[r[k] for k in columns] for r in rows],[[r[k] for k in columns] for r in reference],rtol=0,atol=1e-12)
            np.testing.assert_allclose([r['state_after'] for r in rows],[r['state_after'] for r in reference],rtol=0,atol=1e-12)
        sources.append(dict(mode=record['mode'],seed=record['seed'],raw_sha256=sha(path)))
    report=dict(case=case,source_sha256=sha(__file__),protocol_sha256=sha(out/'protocol.json'),raw_sources=sources,
        repeated_failures=14,unique_failed_fixtures=1,collision_time_s=first['time_s'],ticks_before_stop=47,
        all_learned_commands_and_trajectories_equal_adaptive=True,learned_selected_ticks=0,
        service_s=.05,actuator_delay_s=.1,strict_proposal_ttl_s=.15,
        conclusion='The strict service-plus-actuator age budget grants PPO zero authority on this fixture. Changing only learned weights cannot repair its collision under the frozen owner. Shared supervision/fallback repair and new matched validation are prerequisites for qualified promotion.',
        scope='Counterexample diagnosis; no controller changes, excluded cases or refreshed proposal timestamps.')
    folder=DATA/'diagnostics';folder.mkdir(exist_ok=True);dump(folder/'shared-collision-case-53.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
