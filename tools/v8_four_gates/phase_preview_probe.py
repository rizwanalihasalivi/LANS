"""State-dependent preview blending for approach/settling trade-offs.

Blend depends on received lateral error and lateral velocity, never episode
time, scenario, seed, plant truth or saved comparator results.
"""
import math,itertools,json,hashlib,shutil
from pathlib import Path
import numpy as np
from . import adaptive_preview_probe as harness
from .preview_centered import command as centered
from .pure_preview import command as pure

FAST=((pure,(16.,16.,.1)),(centered,(4.,4.,4.)))
SLOW=(pure,(16.,64.,.1))


def command(state,previous,route,fast_index,threshold,lookahead,stiffness=1.):
    y,h,_=route.geometry(state[0]);ey=state[1]-y;ep=math.atan2(math.sin(state[2]-h),math.cos(state[2]-h))
    approaching=ey+lookahead*(state[4]+state[3]*ep);w=approaching**2/(approaching**2+threshold**2)
    function,args=FAST[int(fast_index)];fast=function(state,previous,route,*args,stiffness=stiffness)
    function,args=SLOW;slow=function(state,previous,route,*args,stiffness=stiffness)
    return float(w*fast+(1-w)*slow)


def main():
    root=Path(__file__).resolve().parents[2];out=root/'results/v8-four-gates/phase-preview-feasibility-v1';out.mkdir(parents=True,exist_ok=False)
    cases=[dict(id=i,route=r,speed=v,plant_stiffness=s) for i,(r,v,s) in enumerate(itertools.product(('straight','sine','lane_change'),(8.,12.,16.),(.8,1.2)))]
    arms=[None,*itertools.product((0,1),(.03,.1,.2),(0.,.2,.5))];files=[*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.md')]
    plan=dict(cases=cases,arms=arms,seconds=6.,expected_records=342,scope='fixed exposed state-dependent analytical-controller feasibility; no PPO or validation',source_hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for p in files:d=out/'source'/p.relative_to(root);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,d)
    harness.command=command;rr=[]
    for j,arm in enumerate(arms):
        for c in cases:d=out/f'{j:02d}-{c["id"]:02d}';d.mkdir();rr.append(harness.run(c,arm,d))
        print('PHASE PREVIEW',j+1,'/19',arm,flush=True)
    base={r['case']['id']:r for r in rr if r['arm'] is None};scores=[]
    for arm in arms[1:]:
        sub=[r for r in rr if r['arm']==arm];ratio=lambda f:float(np.mean([r[f] for r in sub])/np.mean([r[f] for r in base.values()]))
        scores.append(dict(arm=arm,gain_percent=100*(1-ratio('rmse_m')),heading_ratio=ratio('heading_rms'),rate_ratio=ratio('rate_rms'),corridor_ticks=sum(r['corridor_ticks'] for r in sub)))
    (out/'scores.json').write_text(json.dumps(scores,indent=2)+'\n');print(json.dumps(scores),flush=True)


if __name__=='__main__':main()
