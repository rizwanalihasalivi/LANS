"""Training-only speed/stiffness gain scheduling, never a PPO modification.

Select one analytical preview arm at each of six model/speed knots. The table
uses no scenario/seed identifier. Nominal R16 can be selected as a backup arm.
This is parameter development, not a final scientific comparison.
"""
from pathlib import Path
import json,hashlib,itertools
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint


def main():
    root=Path(__file__).resolve().parents[2];out=root/'results/v8-four-gates/schedule-development-v1';out.mkdir(parents=True,exist_ok=False)
    sources={'centered':root/'results/v8-four-gates/adaptive-preview-feasibility-v1','pure':root/'results/v8-four-gates/pure-preview-feasibility-v1'}
    data={family:[json.loads(p.read_text()) for p in sorted(path.glob('*/summary.json'))] for family,path in sources.items()}
    knots=list(itertools.product((8.,12.,16.),(.8,1.2)));base={r['case']['id']:r for r in data['pure'] if r['arm'] is None}
    arms=[('nominal',None),*[(family,tuple(arm)) for family,rr in data.items() for arm in sorted({tuple(r['arm']) for r in rr if r['arm'] is not None})]]
    totals={f:sum(r[f] for r in base.values()) for f in ('rmse_m','heading_rms','rate_rms')};budget=dict(heading_rms=.99,rate_rms=.98)
    plan=dict(knots=knots,arms=arms,quality_budgets=budget,selector='minimize summed RMSE subject to quality budgets and one analytical arm per speed/stiffness knot',scope='exposed training-only parameter development; no seed/scenario selection or final claims',input_hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for path in sources.values() for p in path.glob('*/summary.json')})
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');values=[]
    for v,s in knots:
        for family,arm in arms:
            rr=list(base.values()) if family=='nominal' else [r for r in data[family] if r['arm'] is not None and tuple(r['arm'])==arm]
            rr=[r for r in rr if r['case']['speed']==v and r['case']['plant_stiffness']==s];assert len(rr)==3
            values.append([sum(r[f] for r in rr) for f in totals])
    values=np.asarray(values);a=np.zeros((len(knots)+2,len(values)))
    for i in range(len(knots)):a[i,i*len(arms):(i+1)*len(arms)]=1.
    a[-2:]=values[:,1:].T;upper=np.r_[np.ones(len(knots)),[totals[f]*budget[f] for f in budget]];lower=np.r_[np.ones(len(knots)),[-np.inf]*2]
    solution=milp(values[:,0],integrality=np.ones(len(values)),bounds=Bounds(0.,1.),constraints=LinearConstraint(a,lower,upper),options=dict(time_limit=30.,mip_rel_gap=1e-7))
    result=dict(status=str(solution.message),success=bool(solution.success),selected=[],totals_reference=totals)
    if solution.x is not None:
        chosen=np.flatnonzero(solution.x>.5);assert len(chosen)==len(knots)
        result['selected']=[dict(speed=knots[i//len(arms)][0],stiffness=knots[i//len(arms)][1],family=arms[i%len(arms)][0],weights=arms[i%len(arms)][1]) for i in chosen]
        metrics=values[chosen].sum(axis=0);result['training_ratios']={f:float(m/totals[f]) for f,m in zip(totals,metrics)}
    (out/'selection.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)


if __name__=='__main__':main()
