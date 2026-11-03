"""Read-only source, raw dynamics, coverage, selection and target verification."""
from pathlib import Path
import json
import numpy as np
from integrations.unified_lans.physics import Command,advance,Config
from integrations.unified_lans.simulation import truth_metrics
from tools.unified_campaign.study import StudyRoute,initial
from integrations.unified_lans.inference import sha
from tools.unified_control_v6.verify import check_record
from tools.unified_control_v7.verify import source_check
from tools.unified_campaign.campaign import assess
from .campaign import all_comparisons,requested_target,cases,ROOT

DATA=ROOT/'results/causal-v8'


def load(path):return json.loads(path.read_text())


def calibration():
    root=DATA/'calibration';p=source_check(root);rr=load(root/'summary.json');assert len(rr)==576
    assert len({(r['candidate'],r['mode'],r['case']['id']) for r in rr})==576
    for r in rr:
        assert r['case']==p['cases'][r['case']['id']]
        raw=root/f'{r["candidate"]}-{r["mode"]}-{r["case"]["id"]:02d}.jsonl'
        assert r==load(raw.with_suffix('.json')) and r['protocol_sha256']==sha(root/'protocol.json')
        check_record(r,raw)
    base={r['case']['id']:r for r in rr if r['candidate']=='lqr-h2'};assert len(base)==64
    scores=[]
    for candidate in p['candidates']:
        records=[r for r in rr if r['candidate']==candidate['name']];assert len(records)==128
        by_mode={}
        for mode in p['modes']:
            rows=[r for r in records if r['mode']==mode];assert len(rows)==64
            by_mode[mode]=dict(heading_ratio=float(np.mean([r['heading_rms'] for r in rows])/np.mean([r['heading_rms'] for r in base.values()])),
                rate_ratio=float(np.mean([r['rate_rms'] for r in rows])/np.mean([r['rate_rms'] for r in base.values()])))
        scores.append(dict(**candidate,failures=sum(r['failed'] for r in records),
            heading_ratio=max(v['heading_ratio'] for v in by_mode.values()),rate_ratio=max(v['rate_ratio'] for v in by_mode.values()),
            minimum_progress_ratio=min(r['progress_m']/base[r['case']['id']]['progress_m'] for r in records),
            mean_rmse_m=float(np.mean([r['rmse_m'] for r in records])),by_mode=by_mode))
    selected=load(root/'selection.json');assert selected['scores']==scores
    eligible=[s for s in scores if not s['failures'] and s['heading_ratio']<=1.10+1e-12 and s['rate_ratio']<=1.10+1e-12 and s['minimum_progress_ratio']>=.99-1e-12]
    assert selected['selected']==(min(eligible,key=lambda s:(s['mean_rmse_m'],s['name'])) if eligible else None)
    print('576 training episodes and unchanged finite selector verified',flush=True)


def confirmation():
    root=DATA/'confirmation';p=source_check(root);total=0
    for s,h in p['models'].items():assert sha(ROOT/f'results/python-campaign-v2/policies/seed-{s}/policy.zip')==h
    for stage,n in [('regression-development',160),('regression-stress',120),('development',448),('stress',120)]:
        rr=load(root/f'{stage}_summary.json');assert len(rr)==n
        assert len({(r['case']['id'],r['mode'],r['actor']) for r in rr})==n
        fixtures={c['id']:c for c in cases(stage)}
        for r in rr:
            assert r['case']==fixtures[r['case']['id']]
            raw=root/stage/f'{r["case"]["id"]:03d}-{r["mode"]}-{r["actor"]}.jsonl'
            assert r==load(raw.with_suffix('.json')) and r['protocol_sha256']==sha(root/'protocol.json')
            total+=check_record(r,raw)
        hybrid=[r for r in rr if r['mode']=='hybrid'];safety=load(root/f'{stage}_safety.json')
        assert safety==dict(passed=not any(r['failed'] for r in hybrid),failures=sum(r['failed'] for r in hybrid),cases=len(hybrid),collisions=sum(r['collisions']>0 for r in hybrid))
        if stage=='development':
            assert assess(rr)==load(root/'development_gate.json')
            assert all_comparisons(rr)==load(root/'development_all_comparisons.json')
        print(stage,n,'records verified',flush=True)
    safe=all(load(root/f'{s}_safety.json')['passed'] for s in ['regression-development','regression-stress','development','stress'])
    target=requested_target(load(root/'development_gate.json'),load(root/'development_all_comparisons.json'),safe)
    assert target==load(root/'requested_target.json')
    if not target['passed']:assert load(root/'STATUS.json')['reserved']=='NOT_RUN'
    print('848 prospective episodes, all seven comparisons and 30% target verified; ticks',total,flush=True)


def conflict_regression():
    root=DATA/'conflict-regression';p=load(root/'protocol.json')
    for name,h in p['sources'].items():assert sha(root/'source'/name)==h
    result=load(root/'summary.json');rr=result['records'];assert len(rr)==7
    for r,metric in zip(rr,result['results']):
        assert r['case']==p['case'] and r['protocol_sha256']==sha(root/'protocol.json')
        check_record(r,root/f'{r["controller_role"]}-{r["actor"]}.jsonl')
        assert metric['progress_ratio']==r['progress_m']/rr[0]['progress_m']
    print('All 7 observed conflict regression episodes verified',flush=True)


def functional():
    root=DATA/'live-functional';protocol=source_check(root);summary=load(root/'summary.json');assert len(summary)==9
    keys={(r['controller_role'],r['seed'],r['scenario']) for r in summary};assert len(keys)==9
    for result in summary:
        directory=root/result['controller_role']/f'seed-{result["seed"]}-{result["scenario"]}'
        raw=directory/'ticks.jsonl';assert sha(raw)==result['raw_sha256'];rows=[json.loads(s) for s in raw.read_text().splitlines()]
        assert len(rows)==result['ticks']==120
        case=load(directory/'protocol.json')['case'];state=np.array(rows[0]['state_before']);previous=0.
        route=StudyRoute(initial(case['scenario'])[0].kind,case['mirror'],case['phase'],case['amplitude'])
        for row in rows:
            np.testing.assert_allclose(state,row['state_before'],rtol=0,atol=1e-12)
            command=Command(row['applied_steering'],row['applied_accel'])
            assert abs(command.steering-previous)<=.03+1e-10 and abs(command.steering)<=.5 and -6<=command.accel<=2.5
            state=advance(state,command,.05,case['stiffness']);np.testing.assert_allclose(state,row['state_after'],rtol=0,atol=1e-12);previous=command.steering
            truth=truth_metrics(state,{k:np.array(v) for k,v in row['npc_truth'].items()},route,Config())
            assert abs(truth['error']-row['error'])<1e-12 and abs(truth['true_clearance']-row['true_clearance'])<1e-12
            assert truth['collision']==row['collision']
            if row['source']=='ppo':assert row['proposal_age']<.15 and row['proposal_wall_age']<.15 and not row['ego_backup']
        assert sum(r['response_ms']>50 for r in rows)==result['response_misses']
        assert sum(r['cycle_ms']>50 for r in rows)==result['cycle_misses']
        assert sum(r['collision'] for r in rows)==result['collisions']
        assert sum(abs(r['error'])>1.75 for r in rows)==result['corridor_exceedances']
        assert max(r['response_ms'] for r in rows)==result['response_max_ms']
    print('All 9 actual-worker functional traces, failures and deadline counts verified',flush=True)


def main():
    calibration();confirmation();conflict_regression();functional()
    print('VERIFIED: 1431 simulation episodes and 9 functional checks; all old and new outcomes retained.',flush=True)


if __name__=='__main__':main()
