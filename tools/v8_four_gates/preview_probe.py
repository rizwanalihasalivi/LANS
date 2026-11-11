"""Predeclared nominal-model preview feasibility; all arms retained."""
from pathlib import Path
import itertools,json,math,hashlib,shutil
import numpy as np
from integrations.unified_lans.physics import Command,Config,advance,constrain,errors
from tools.unified_campaign.study import StudyRoute
from tools.unified_control_v4.control import ScheduledLQR
from .preview import command

ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/v8-four-gates/preview-feasibility-v1'


def run(c,arm,out):
    route=StudyRoute(c['route'],1,1.,.9);y,h,_=route.geometry(0.)
    z=np.array([0.,y+.3,h+.005,c['speed'],0.,0.]);previous=Command();base=ScheduledLQR(16.);cfg=Config(horizon=2.)
    rows=[]
    for tick in range(120):
        nominal=base(z,route)
        desired=nominal if arm is None else command(z,previous.steering,route,*arm,stiffness=1.)
        desired=float(np.clip(desired,nominal-.08,nominal+.08));u=constrain(Command(desired,0.),previous,cfg)
        before=z.copy();z=advance(z,u,.05,c['plant_stiffness']);e,_=errors(z,route)
        rows.append(dict(tick=tick,state_before=before.tolist(),state_after=z.tolist(),steering=u.steering,
            error=float(e[0]),heading_error=float(e[2]),steering_rate=(u.steering-previous.steering)/.05));previous=u
    raw=out/'ticks.jsonl';raw.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    r=dict(case=c,arm=arm,rmse_m=math.sqrt(np.mean([r['error']**2 for r in rows])),
        heading_rms=math.sqrt(np.mean([r['heading_error']**2 for r in rows])),rate_rms=math.sqrt(np.mean([r['steering_rate']**2 for r in rows])),
        corridor_ticks=sum(abs(r['error'])>1.75 for r in rows),raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest())
    (out/'summary.json').write_text(json.dumps(r,indent=2)+'\n');return r


def main():
    OUT.mkdir(parents=True,exist_ok=False);cases=[dict(id=i,route=r,speed=v,plant_stiffness=s) for i,(r,v,s) in enumerate(itertools.product(('straight','sine','lane_change'),(8.,12.,16.),(.8,1.2)))]
    arms=[None,*itertools.product((.1,1.,4.,16.),(.05,.2,1.,4.))];files=list(Path(__file__).parent.glob('*.py'))+list(Path(__file__).parent.glob('*.md'))
    plan=dict(cases=cases,arms=arms,seconds=6.,prediction_stiffness=1.,scope='exposed development only, no traffic',sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (OUT/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for f in files:d=OUT/'source'/f.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,d)
    all_results=[]
    for j,arm in enumerate(arms):
        rr=[]
        for c in cases:
            d=OUT/f'{j:02d}-{c["id"]:02d}';d.mkdir();rr.append(run(c,arm,d))
        all_results.extend(rr);print('PREVIEW FEASIBILITY',j+1,'/17',arm,flush=True)
    base={r['case']['id']:r for r in all_results if r['arm'] is None};scores=[]
    for arm in arms[1:]:
        rr=[r for r in all_results if r['arm']==arm]
        def ratio(field):return float(np.mean([r[field] for r in rr])/np.mean([r[field] for r in base.values()]))
        scores.append(dict(arm=arm,gain_percent=100*(1-ratio('rmse_m')),heading_ratio=ratio('heading_rms'),rate_ratio=ratio('rate_rms'),corridor_ticks=sum(r['corridor_ticks'] for r in rr)))
    (OUT/'scores.json').write_text(json.dumps(scores,indent=2)+'\n');print(json.dumps(scores),flush=True)


if __name__=='__main__':main()
