"""Observed-transition identification with fixed preview arms; development only."""
from pathlib import Path
import itertools,json,hashlib,shutil,math
import numpy as np
from integrations.unified_lans.physics import Config,Command,advance,constrain,errors
from integrations.unified_lans.traffic import Packet
from tools.unified_control_v4.control import Controller as Identifier,ScheduledLQR
from tools.unified_campaign.study import StudyRoute
from .preview_centered import command

ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/v8-four-gates/adaptive-preview-feasibility-v1'


def run(c,arm,out):
    route=StudyRoute(c['route'],1,1.,.9);y,h,_=route.geometry(0.);z=np.array([0.,y+.3,h+.005,c['speed'],0.,0.]);prev=Command();cfg=Config(horizon=2.)
    base=ScheduledLQR(16.);identifier=Identifier(route,cfg=cfg,penalty=16.,adaptive=True,mpc=False)
    rows=[]
    for i in range(120):
        now=i*.05;identifier.inbox.ingest(Packet('ego',i,now,tuple(z)),now);identifier.update_model()
        anchor=base(z,route) if arm is None else identifier.baseline_fn(z,route)
        desired=anchor if arm is None else command(z,prev.steering,route,*arm,stiffness=identifier.feedback_stiffness)
        u=constrain(Command(float(np.clip(desired,anchor-.08,anchor+.08)),0.),prev,cfg)
        before=z.copy();z=advance(z,u,.05,c['plant_stiffness']);e,_=errors(z,route)
        rows.append(dict(tick=i,state_before=before.tolist(),state_after=z.tolist(),steering=u.steering,error=float(e[0]),heading_error=float(e[2]),steering_rate=(u.steering-prev.steering)/.05,
            prediction_stiffness=identifier.feedback_stiffness,stiffness_estimate=identifier.stiffness_estimate))
        identifier.history.append((now,now+.05,u));identifier.history=[x for x in identifier.history if x[1]>=now-.5];identifier.issued=identifier.applied=u;prev=u
    raw=out/'ticks.jsonl';raw.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    r=dict(case=c,arm=arm,rmse_m=math.sqrt(np.mean([r['error']**2 for r in rows])),heading_rms=math.sqrt(np.mean([r['heading_error']**2 for r in rows])),
        rate_rms=math.sqrt(np.mean([r['steering_rate']**2 for r in rows])),corridor_ticks=sum(abs(r['error'])>1.75 for r in rows),raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest())
    (out/'summary.json').write_text(json.dumps(r,indent=2)+'\n');return r


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    cases=[dict(id=i,route=r,speed=v,plant_stiffness=s) for i,(r,v,s) in enumerate(itertools.product(('straight','sine','lane_change'),(8.,12.,16.),(.8,1.2)))]
    arms=[None,*itertools.product((4.,16.,64.),(4.,16.,64.),(4.,8.,16.))];files=[*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.md')]
    plan=dict(cases=cases,arms=arms,seconds=6.,prediction='causal measured transition ID, no plant-truth parameter access',scope='training/exposed feasibility only',
        sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (OUT/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for f in files:d=OUT/'source'/f.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,d)
    results=[]
    for j,arm in enumerate(arms):
        for c in cases:
            d=OUT/f'{j:02d}-{c["id"]:02d}';d.mkdir();results.append(run(c,arm,d))
        print('ADAPTIVE PREVIEW',j+1,'/28',arm,flush=True)
    base={r['case']['id']:r for r in results if r['arm'] is None};scores=[]
    for arm in arms[1:]:
        rr=[r for r in results if r['arm']==arm];ratio=lambda f:float(np.mean([r[f] for r in rr])/np.mean([r[f] for r in base.values()]))
        scores.append(dict(arm=arm,gain_percent=100*(1-ratio('rmse_m')),heading_ratio=ratio('heading_rms'),rate_ratio=ratio('rate_rms'),corridor_ticks=sum(r['corridor_ticks'] for r in rr)))
    (OUT/'scores.json').write_text(json.dumps(scores,indent=2)+'\n');print(json.dumps(scores),flush=True)


if __name__=='__main__':main()
