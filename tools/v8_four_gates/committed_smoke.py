"""Fixed exposed-fixture comparison for committed-prefix proposal alignment."""
import json,hashlib
from pathlib import Path
from tools.unified_control_v4.calibrate import cases
from tools.unified_control_v9.learning import run_episode
from integrations.unified_lans.run import clean
from .committed import Controller
from .longitudinal import Synchronous


def main():
    root=Path(__file__).resolve().parents[2];out=root/'results/v8-four-gates/committed-smoke-v1';out.mkdir(parents=True,exist_ok=False)
    selected=[cases()[i] for i in (0,20,36,52)];files=[*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.md')]
    (out/'plan.json').write_text(json.dumps(dict(cases=selected,source_hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},expected_records=8,scope='exposed implementation smoke, not validation'),indent=2)+'\n')
    results=[]
    for c in selected:
        for name,cls,adaptive in (('lqr',Synchronous,False),('committed',Controller,True)):
            r,rows=run_episode(c,'deterministic' if adaptive else 'lqr',grid=adaptive,controller_factory=cls,controller_kwargs=dict(adaptive=adaptive,mpc=adaptive,barrier_frequency=3.,quality_factor=1.,tracking_only=False))
            d=out/f'{name}-{c["id"]}';d.mkdir();(d/'ticks.jsonl').write_text(''.join(json.dumps(clean(x),allow_nan=False)+'\n' for x in rows))
            r.update(arm=name,mpc_ticks=sum(bool(x.get('planned_candidate_selected')) for x in rows));(d/'summary.json').write_text(json.dumps(clean(r),indent=2)+'\n');results.append(r);print(name,c['id'],r,flush=True)
    (out/'summary.json').write_text(json.dumps(clean(results),indent=2)+'\n')


if __name__=='__main__':main()
