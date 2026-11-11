"""Fixed balanced-weight follow-up to the retained aggressive preview probe."""
from pathlib import Path
import itertools,json,math,hashlib,shutil
import numpy as np
from . import preview_probe as harness
from .preview_balanced import command

ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/v8-four-gates/preview-feasibility-v2'


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    cases=[dict(id=i,route=r,speed=v,plant_stiffness=s) for i,(r,v,s) in enumerate(itertools.product(('straight','sine','lane_change'),(8.,12.,16.),(.8,1.2)))]
    arms=[None,*itertools.product((1.,4.,16.,64.),(1.,16.,64.,256.))];files=[*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.md')]
    plan=dict(cases=cases,arms=arms,seconds=6.,prediction_stiffness=1.,scope='training/exposed feasibility only, no traffic',
        fixed_weights=dict(lateral=1.,lateral_error_derivative=.1,yaw=.1,input_magnitude=16.),
        sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (OUT/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for f in files:d=OUT/'source'/f.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,d)
    harness.command=command;results=[]
    for j,arm in enumerate(arms):
        for c in cases:
            d=OUT/f'{j:02d}-{c["id"]:02d}';d.mkdir();results.append(harness.run(c,arm,d))
        print('BALANCED PREVIEW',j+1,'/17',arm,flush=True)
    base={r['case']['id']:r for r in results if r['arm'] is None};scores=[]
    for arm in arms[1:]:
        rr=[r for r in results if r['arm']==arm]
        ratio=lambda f:float(np.mean([r[f] for r in rr])/np.mean([r[f] for r in base.values()]))
        scores.append(dict(arm=arm,gain_percent=100*(1-ratio('rmse_m')),heading_ratio=ratio('heading_rms'),rate_ratio=ratio('rate_rms'),corridor_ticks=sum(r['corridor_ticks'] for r in rr)))
    (OUT/'scores.json').write_text(json.dumps(scores,indent=2)+'\n');print(json.dumps(scores),flush=True)


if __name__=='__main__':main()
