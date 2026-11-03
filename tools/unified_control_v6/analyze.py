"""Build full component tables, clustered intervals and numerical prediction study."""
from pathlib import Path
from collections import defaultdict
import json, math
import numpy as np
from scipy.stats import binomtest, spearmanr
from integrations.unified_lans.inference import sha
from integrations.unified_lans.physics import Command, advance, constrain
from integrations.unified_lans.run import clean
from tools.unified_campaign.study import StudyRoute, initial
from tools.unified_control_v4.control import ScheduledLQR, gain_table, GRID
from tools.unified_control_v4.kernels import rollout

ROOT=Path(__file__).resolve().parents[2]


def aggregate(records):
    tp=sum(r['warning_tp'] for r in records);fp=sum(r['warning_fp'] for r in records);fn=sum(r['warning_fn'] for r in records)
    return dict(episodes=len(records),failures=sum(r['failed'] for r in records),
        collisions=sum(r['collision'] for r in records),corridor_failures=sum(r['corridor_failure'] for r in records),
        duration_completed=sum(r['ticks']==r['expected_ticks'] for r in records),
        goals_reached=sum(r['goal_reached'] for r in records),
        mean_rmse_m=float(np.mean([r['rmse_m'] for r in records])),
        mean_progress_m=float(np.mean([r['progress_m'] for r in records])),
        mean_heading_rms=float(np.mean([r['heading_rms'] for r in records])),
        mean_rate_rms=float(np.mean([r['rate_rms'] for r in records])),
        minimum_clearance_m=min(r['min_clearance'] for r in records),
        warning_precision=tp/(tp+fp) if tp+fp else None,warning_recall=tp/(tp+fn) if tp+fn else None,
        warning_tp=tp,warning_fp=fp,warning_fn=fn)


def contrasts(records):
    by={}
    for r in records:by[(r['variant'],r['case']['id'])]=r
    full=[r for r in records if r['variant']=='full'];fixtures=sorted({r['case']['fixture_id'] for r in full})
    result=[]
    for variant in sorted({r['variant'] for r in records}-{'full'}):
        cells=[]
        for fixture in fixtures:
            a=[r for r in full if r['case']['fixture_id']==fixture]
            b=[by[(variant,r['case']['id'])] for r in a]
            cells.append([np.mean([r['failed'] for r in a]),np.mean([r['failed'] for r in b]),
                          np.mean([r['rmse_m'] for r in a]),np.mean([r['rmse_m'] for r in b])])
        cells=np.asarray(cells);delta=cells[:,1]-cells[:,0];nonzero=delta[abs(delta)>1e-12]
        p=float(binomtest(int(sum(nonzero>0)),len(nonzero)).pvalue) if len(nonzero) else 1.
        rng=np.random.default_rng(24310001);draw=rng.integers(len(cells),size=(5000,len(cells)));boot=cells[draw].mean(axis=1)
        result.append(dict(ablated_variant=variant,fixtures=len(cells),failure_increase_percentage_points=float(100*delta.mean()),
            failure_increase_ci95_pp=np.quantile(100*(boot[:,1]-boot[:,0]),[.025,.975]).tolist(),
            full_rmse_gain_percent=float(100*(1-cells[:,2].mean()/cells[:,3].mean())),
            full_rmse_gain_ci95_percent=np.quantile(100*(1-boot[:,2]/boot[:,3]),[.025,.975]).tolist(),
            failure_exact_sign_p=p,non_tied_fixtures=len(nonzero)))
    order=sorted(range(len(result)),key=lambda i:result[i]['failure_exact_sign_p']);previous=0.
    for rank,index in enumerate(order):
        value=max(previous,min(1.,(len(order)-rank)*result[index]['failure_exact_sign_p']))
        result[index]['failure_holm_p']=value;previous=value
    return result


def predict_pending(state,command,pending,now,delay,stiffness):
    state=np.array(state);cursor=now
    for due,cmd in pending:
        if due>now+delay+1e-9:break
        if due>cursor:state=advance(state,command,due-cursor,stiffness);cursor=due
        command=cmd
    if now+delay>cursor:state=advance(state,command,now+delay-cursor,stiffness)
    return state


def prediction_study(root,records,config):
    # Scoring-only true states and hidden plant stiffness never feed deployment.
    # The candidate grid and fixed feedback after the first step are common.
    from integrations.unified_lans.physics import Config
    cfg=Config(**config);items=[];positions=[]
    for record in [r for r in records if r['variant']=='full']:
        case=record['case'];raw=root/f'{case["id"]:03d}-full.jsonl'
        assert sha(raw)==record['raw_sha256'];rows=[json.loads(line) for line in raw.read_text().splitlines()]
        route=StudyRoute(initial(case['scenario'])[0].kind,case['mirror'],case['phase'],case['amplitude'])
        route_array=np.array([{'straight':0,'sine':1,'lane_change':2}[route.kind],case['mirror'],case['phase'],case['amplitude']])
        pending=[];previous=Command();previous_issued=Command()
        for row in rows:
            now=row['time_s']
            if row['tick']%20==0 and row['ego_age']<=1e-9:
                estimate=row['stiffness_estimate'];feedback=float(np.clip(round(estimate*20)/20,.7,1.3))
                true=predict_pending(row['state_before'],previous,pending,now,case['delay'],case['stiffness'])
                for label,stiff in [('nominal',1.),('adaptive',estimate)]:
                    pred=predict_pending(row['state_before'],previous,pending,now,case['delay'],stiff)
                    positions.append(dict(case_id=case['id'],tick=row['tick'],model=label,delay=case['delay'],
                        application_position_error_m=float(np.linalg.norm(pred[:2]-true[:2])),
                        stiffness_absolute_error=abs(stiff-case['stiffness'])))
                base=ScheduledLQR(16.);base.stiffness=feedback;gains=gain_table(16.,feedback)
                # Same physical commands for both model scorers: generate from
                # the causal adaptive application estimate, never fixture truth.
                predicted=predict_pending(row['state_before'],previous,pending,now,case['delay'],estimate)
                nominal=predict_pending(row['state_before'],previous,pending,now,case['delay'],1.)
                vehicle_rows=[]
                for other in row['npc_truth_before'].values():
                    from integrations.unified_lans.traffic import extrapolate
                    # This controlled ranking diagnostic holds traffic at the
                    # current-truth CV state for all scorers; it does not assess
                    # stale-traffic uncertainty or actual future NPC reactions.
                    vehicle_rows.append([*extrapolate(other,case['delay']),0.])
                npcs=np.array(vehicle_rows,float).reshape(-1,7)
                costs={'nominal':[],'adaptive':[],'truth':[]}
                for residual in GRID:
                    command=constrain(Command(base(predicted,route)+residual,row['issued_accel']),previous_issued,cfg)
                    for label,state,stiff in [('nominal',nominal,1.),('adaptive',predicted,estimate),('truth',true,case['stiffness'])]:
                        costs[label].append(float(rollout(state,command.steering,command.accel,previous_issued.steering,
                            cfg.dt,cfg.horizon,stiff,gains,route_array,npcs,cfg.vehicle_radius,cfg.buffer,
                            cfg.uncertainty_rate,cfg.steering_limit,cfg.steering_rate,feedback)[0]))
                truth=np.asarray(costs['truth'])
                for label in ('nominal','adaptive'):
                    values=np.asarray(costs[label]);informative=np.ptp(values)>1e-12 and np.ptp(truth)>1e-12
                    rho=float(spearmanr(values,truth).statistic) if informative else None
                    best=int(np.argmin(values))
                    items.append(dict(case_id=case['id'],tick=row['tick'],model=label,spearman=rho,
                        true_grid_regret=float(truth[best]-truth.min()),
                        cost_mae=float(np.mean(abs(values-truth))),predicted_costs=values.tolist(),true_costs=truth.tolist()))
            issued=Command(row['issued_steering'],row['issued_accel']);pending.append((now+case['delay'],issued));previous_issued=issued
            while pending and pending[0][0]<=now+1e-9:_,previous=pending.pop(0)
    summaries={}
    for label in ('nominal','adaptive'):
        rr=[r for r in items if r['model']==label];pp=[r for r in positions if r['model']==label]
        delayed=[r for r in pp if r['delay']>0]
        ranked=[r for r in rr if r['spearman'] is not None]
        summaries[label]=dict(sampled_states=len(rr),informative_rank_states=len(ranked),mean_cost_mae=float(np.mean([r['cost_mae'] for r in rr])),
            mean_grid_regret=float(np.mean([r['true_grid_regret'] for r in rr])),
            informative_mean_grid_regret=float(np.mean([r['true_grid_regret'] for r in ranked])) if ranked else None,
            mean_spearman=float(np.mean([r['spearman'] for r in ranked])) if ranked else None,
            mean_application_position_error_m=float(np.mean([r['application_position_error_m'] for r in pp])),
            delayed_application_position_error_m=float(np.mean([r['application_position_error_m'] for r in delayed])),
            mean_stiffness_absolute_error=float(np.mean([r['stiffness_absolute_error'] for r in pp])))
    return dict(scope='controlled scoring-only CV-traffic/grid diagnostic, not realized full-plan ranking or causal policy superiority',
                summary=summaries,candidates=items,position_records=positions)


def main():
    from .raw_analysis import main as raw_main
    raw_main()


if __name__=='__main__':main()
