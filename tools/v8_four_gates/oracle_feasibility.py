"""NONDEPLOYABLE known-plant finite-horizon quality feasibility diagnostic.

This gives the solver plant truth on purpose, solely to separate control-design
trade-offs from identification/execution failures. It is not controller evidence,
a rigorous nonlinear lower bound, a safety proof or a proposed deployed method.
"""
from pathlib import Path
import itertools,json,hashlib,math
import numpy as np
from integrations.unified_lans.physics import Config,Command,errors,advance
from tools.unified_campaign.study import StudyRoute
from tools.unified_control_v4.control import gain_table
from tools.unified_control_v5.control import baseline_plan
from .robust_planner import Request,solve


def main():
    root=Path(__file__).resolve().parents[2];out=root/'results/v8-four-gates/oracle-feasibility-v1';out.mkdir(parents=True,exist_ok=False)
    cases=[dict(id=i,route=r,speed=v,plant_stiffness=s) for i,(r,v,s) in enumerate(itertools.product(('straight','sine','lane_change'),(8.,12.,16.),(.8,1.2)))]
    (out/'plan.json').write_text(json.dumps(dict(cases=cases,horizon=6.,expected_records=36,scope=__doc__,quality_factor=1.,sources={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}),indent=2)+'\n');results=[]
    for c in cases:
        route=StudyRoute(c['route'],1,1.,.9);y,h,_=route.geometry(0.);initial=np.array([0.,y+.3,h+.005,c['speed'],0.,0.]);cfg=Config(horizon=6.);gains=gain_table(16.,1.);r=np.array([{'straight':0,'sine':1,'lane_change':2}[route.kind],1.,1.,.9])
        baseline=baseline_plan(initial,120,0.,0.,.05,c['plant_stiffness'],gains,r,.5,.6,1.)
        request=Request(1,0.,0.,0.,0.,tuple(initial),0.,0.,cfg,c['plant_stiffness'],1.,tuple(tuple(float(x) for x in row) for row in gains),tuple(r),(),1.,0.)
        response=solve(request)
        for name,commands in (('lqr',baseline),('known_model_optimum_candidate',response.commands if response.commands is not None else baseline)):
            z=initial.copy();rows=[];previous=0.
            for i,u in enumerate(commands):
                before=z.copy();z=advance(z,Command(u,0.),.05,c['plant_stiffness']);e,_=errors(z,route)
                rows.append(dict(tick=i,state_before=before.tolist(),state_after=z.tolist(),steering=float(u),error=float(e[0]),heading_error=float(e[2]),steering_rate=float((u-previous)/.05)));previous=u
            d=out/f'{c["id"]:02d}-{name}';d.mkdir();raw=d/'ticks.jsonl';raw.write_text(''.join(json.dumps(x)+'\n' for x in rows))
            summary=dict(case=c,arm=name,status=response.status if name!='lqr' else 'reference',rmse_m=math.sqrt(np.mean([x['error']**2 for x in rows])),heading_rms=math.sqrt(np.mean([x['heading_error']**2 for x in rows])),rate_rms=math.sqrt(np.mean([x['steering_rate']**2 for x in rows])),corridor_ticks=sum(abs(x['error'])>1.75 for x in rows),raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest())
            (d/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');results.append(summary)
        print('ORACLE FEASIBILITY',c['id']+1,'/18',response.status,flush=True)
    baseline=[r for r in results if r['arm']=='lqr'];candidate=[r for r in results if r['arm']!='lqr'];ratios={f:float(np.mean([r[f] for r in candidate])/np.mean([r[f] for r in baseline])) for f in ('rmse_m','heading_rms','rate_rms')}
    (out/'summary.json').write_text(json.dumps(dict(records=results,ratios=ratios,scope=__doc__),indent=2)+'\n');print(ratios,flush=True)


if __name__=='__main__':main()
