"""Independent coverage, source, physics, selector, quality and timing audits."""
from pathlib import Path
import json
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.physics import Command,advance,Config
from integrations.unified_lans.simulation import truth_metrics
from tools.unified_campaign.study import StudyRoute,initial
from tools.unified_campaign.campaign import assess
from tools.unified_control_v6.verify import check_record

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'results/causal-v7'


def load(path):return json.loads(path.read_text())


def source_check(root):
    protocol=load(root/'protocol.json')
    for name,h in protocol['source_hashes'].items():assert sha(root/'source'/name)==h,('snapshot',name)
    for name in ['integrations/unified_lans/physics.py','integrations/unified_lans/simulation.py',
                 'tools/unified_campaign/study.py','controllers/lqr_controller.py','models/bicycle_model.py']:
        if name in protocol['source_hashes']:assert sha(ROOT/name)==protocol['source_hashes'][name],('active replay source',name)
    return protocol


def calibration():
    root=DATA/'calibration';protocol=source_check(root);results=load(root/'summary.json');assert len(results)==640
    assert len({(r['candidate'],r['mode'],r['case']['id']) for r in results})==640
    for r in results:
        assert r['case']==protocol['cases'][r['case']['id']]
        raw=root/f'{r["candidate"]}-{r["mode"]}-{r["case"]["id"]:02d}.jsonl'
        assert r['protocol_sha256']==sha(root/'protocol.json');check_record(r,raw)
    selection=load(root/'selection.json');scores=[]
    for candidate in protocol['candidates']:
        rr=[r for r in results if r['candidate']==candidate['name']]
        baseline={r['case']['id']:r for r in results if r['candidate']==f'lqr-h{candidate["horizon"]:g}'}
        assert len(rr)==128 and len(baseline)==64
        by_mode={}
        for mode in protocol['modes']:
            mm=[r for r in rr if r['mode']==mode]
            by_mode[mode]=dict(heading_ratio=float(np.mean([r['heading_rms'] for r in mm])/np.mean([r['heading_rms'] for r in baseline.values()])),
                rate_ratio=float(np.mean([r['rate_rms'] for r in mm])/np.mean([r['rate_rms'] for r in baseline.values()])))
        scores.append(dict(**candidate,failures=sum(r['failed'] for r in rr),
            heading_ratio=max(s['heading_ratio'] for s in by_mode.values()),rate_ratio=max(s['rate_ratio'] for s in by_mode.values()),
            minimum_progress_ratio=min(r['progress_m']/baseline[r['case']['id']]['progress_m'] for r in rr),
            mean_rmse_m=float(np.mean([r['rmse_m'] for r in rr])),by_mode=by_mode))
    assert scores==selection['scores']
    eligible=[s for s in scores if s['failures']==0 and s['heading_ratio']<=1.10+1e-12 and s['rate_ratio']<=1.10+1e-12 and s['minimum_progress_ratio']>=.99-1e-12]
    assert min(eligible,key=lambda s:(s['mean_rmse_m'],s['name']))==selection['selected']
    print('All 640 training episodes and fixed selector verified',flush=True)


def comparisons():
    shared=0
    for role in ['confirmation','engineering']:
        root=DATA/role;p=source_check(root)
        for seed,h in p['models'].items():assert sha(ROOT/f'results/python-campaign-v2/policies/seed-{seed}/policy.zip')==h
        for stage,expected in [('regression-development',160),('regression-stress',120),('development',352),('stress',120)]:
            results=load(root/f'{stage}_summary.json');assert len(results)==expected
            assert len({(r['case']['id'],r['mode'],r['actor']) for r in results})==expected
            for r in results:
                key=f'{r["case"]["id"]:03d}-{r["mode"]}-{r["actor"]}'
                raw=root/stage/(key+'.jsonl');assert r==load(root/stage/(key+'.json'))
                assert r['protocol_sha256']==sha(root/'protocol.json');check_record(r,raw)
                if 'shared_comparator_source' in r:
                    assert role=='engineering' and sha(ROOT/r['shared_comparator_source'])==sha(raw);shared+=1
            if stage=='development':assert assess(results)==load(root/'development_gate.json')
        gate=load(root/'development_gate.json');target=load(root/'requested_target.json')
        assert target['passed']==bool(gate['passed'] and gate['comparisons']['lqr']['gain_percent']>=30.)
        assert target['target_percent']==30.
        status=load(root/'STATUS.json')
        if not target['passed']:assert status['reserved']=='NOT_RUN' and status['webots']=='NOT_RUN'
        print(role,'all 752 records verified, primary original gate',gate['passed'],'30% target',target['passed'],flush=True)
    assert shared==272
    print('272 shared comparators verified byte-identical; only 1232 newly computed prospective episodes',flush=True)


def prediction():
    root=DATA/'prediction-diagnosis';protocol=source_check(root);records=load(root/'lqr_summary.json');assert len(records)==64
    assert len({r['case']['id'] for r in records})==64
    for r in records:
        assert r['case']==protocol['cases'][r['case']['id']]
        check_record(r,root/f'{r["case"]["id"]:03d}-lqr.jsonl')
    old=ROOT/'results/proposal-completion-v6/ablations/summary.json'
    assert sha(old)==protocol['old_summary_sha256'];source=load(old)
    for record in load(root/'quality_comparison.json'):
        profile=record['profile'];mode=record['variant']
        rr=[r for r in source if r['variant']==mode and (profile=='all' or r['case']['profile']==profile)]
        bb=[r for r in records if profile=='all' or r['case']['profile']==profile]
        heading=float(np.mean([r['heading_rms'] for r in rr])/np.mean([r['heading_rms'] for r in bb]))
        rate=float(np.mean([r['rate_rms'] for r in rr])/np.mean([r['rate_rms'] for r in bb]))
        assert heading==record['mean_heading_ratio_to_lqr'] and rate==record['mean_rate_ratio_to_lqr']
        assert record['heading_rate_quality_passed']==bool(heading<=1.10+1e-12 and rate<=1.10+1e-12)
    print('All 64 matched-LQR prediction trade-off diagnoses verified',flush=True)


def functional():
    root=DATA/'live-functional';protocol=source_check(root);summary=load(root/'summary.json');assert len(summary)==18
    keys={(r['controller_role'],r['seed'],r['scenario']) for r in summary};assert len(keys)==18
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
    print('All 18 actual-worker functional traces, failures and deadline counts verified',flush=True)


def main():
    calibration();comparisons();prediction();functional()
    print('VERIFIED: 1936 unique simulation episodes, 272 shared records, 18 functional checks; no fabricated 30% pass.',flush=True)


if __name__=='__main__':main()
