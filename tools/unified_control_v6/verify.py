"""Read-only coverage, source/model, physical-trace and original-gate verification."""
from pathlib import Path
import json,math
import numpy as np
from integrations.unified_lans.inference import sha
from integrations.unified_lans.simulation import truth_metrics
from integrations.unified_lans.physics import Config
from tools.unified_campaign.campaign import assess
from .ablation import audit

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'results/proposal-completion-v6'


def load(path):
    def reject(value):raise ValueError(('invalid JSON constant',value))
    return json.loads(path.read_text(),parse_constant=reject)


def source_check(root,key='source_hashes'):
    protocol=load(root/'protocol.json')
    for name,h in protocol[key].items():assert sha(root/'source'/name)==h,('snapshot mismatch',name)
    for name in ['integrations/unified_lans/physics.py','integrations/unified_lans/simulation.py',
                 'tools/unified_campaign/study.py','tools/unified_control_v6/ablation.py']:
        if name in protocol[key]:assert sha(ROOT/name)==protocol[key][name],('active replay source changed',name)
    return protocol


def check_record(record,raw):
    assert sha(raw)==record['raw_sha256'],raw
    rows=[json.loads(s) for s in raw.read_text().splitlines()];audit(record,rows)
    assert len(rows)==record['ticks']
    failed=len(rows)<record['expected_ticks'] or any(r['collision'] or abs(r['error'])>1.75 for r in rows)
    assert failed==record['failed']
    case=record['case']
    from tools.unified_campaign.study import StudyRoute,initial
    route=StudyRoute(initial(case['scenario'])[0].kind,case['mirror'],case['phase'],case['amplitude'])
    for row in rows:
        npcs=row.get('npc_truth_after',row.get('npc_truth'))
        metrics=truth_metrics(np.array(row['state_after']),{k:np.array(v) for k,v in npcs.items()},route,Config())
        for key in ['error','heading_error','true_clearance']:
            assert abs(row[key]-metrics[key])<1e-12,(raw,key)
        assert metrics['collision']==row['collision'] and metrics['corridor_exceeded']==row['corridor_exceeded']
    n=len(rows)
    for key,value in [('heading_rms',math.sqrt(sum(r['heading_error']**2 for r in rows)/n)),
                      ('rate_rms',math.sqrt(sum(r['steering_rate']**2 for r in rows)/n)),
                      ('progress_m',rows[-1]['state_after'][0]),('min_clearance',min(r['true_clearance'] for r in rows))]:
        assert abs(record[key]-value)<1e-12,(raw,key)
    if 'collision' in record:assert record['collision']==any(r['collision'] for r in rows)
    else:assert record['collisions']==sum(r['collision'] for r in rows)
    return n


def main():
    ticks=0;episodes=0
    root=DATA/'calibration';protocol=source_check(root,'sources');records=load(root/'summary.json')
    assert len(records)==448
    for r in records:
        assert r['case']==protocol['cases'][r['case']['id']]
        ticks+=check_record(r,root/f'{r["candidate"]}-{r["mode"]}-{r["case"]["id"]:02d}.jsonl');episodes+=1
    selection=load(root/'selection.json');scores=selection['scores']
    base=[r for r in records if r['candidate']=='lqr']
    for score in scores:
        rr=[r for r in records if r['candidate']==score['candidate']];assert len(rr)==128
        assert score['failures']==sum(r['failed'] for r in rr)
        assert abs(score['progress']-np.mean([r['progress_m'] for r in rr]))<1e-12
        assert abs(score['balanced']-np.mean([r['rmse_m']+.1*r['heading_rms']+.01*r['rate_rms'] for r in rr]))<1e-12
        for metric,key in [('heading_rms','heading_ratio'),('rate_rms','rate_ratio')]:
            assert abs(score[key]-np.mean([r[metric] for r in rr])/np.mean([r[metric] for r in base]))<1e-12
    stable=[s for s in scores if s['failures']==0];maximum=max(s['progress'] for s in stable)
    eligible=[s for s in stable if s['progress']>=.99*maximum and s['heading_ratio']<=1.10 and s['rate_ratio']<=1.10]
    assert min(eligible,key=lambda s:(s['balanced'],s['candidate']))==selection['selected']
    print('Calibration: all 448 episodes, physical replay and fixed selector PASS',flush=True)
    root=DATA/'confirmation';protocol=source_check(root)
    for seed,h in protocol['models'].items():assert sha(ROOT/f'results/python-campaign-v2/policies/seed-{seed}/policy.zip')==h
    for stage,expected in [('regression-development',160),('regression-stress',120),('development',352),('stress',120)]:
        records=load(root/f'{stage}_summary.json');assert len(records)==expected
        assert len({(r['case']['id'],r['mode'],r['actor']) for r in records})==expected
        for r in records:
            key=f'{r["case"]["id"]:03d}-{r["mode"]}-{r["actor"]}'
            assert r==load(root/stage/(key+'.json')) and r['protocol_sha256']==sha(root/'protocol.json')
            ticks+=check_record(r,root/stage/(key+'.jsonl'));episodes+=1
        if stage=='development':assert assess(records)==load(root/'development_gate.json')
        print('Formal',stage,expected,'episodes verified',flush=True)
    root=DATA/'ablations';protocol=source_check(root);records=load(root/'summary.json');assert len(records)==384
    assert len({(r['case']['id'],r['variant']) for r in records})==384
    for r in records:
        assert r['case']==protocol['cases'][r['case']['id']]
        key=f'{r["case"]["id"]:03d}-{r["variant"]}'
        assert r==load(root/(key+'.json')) and r['protocol_sha256']==sha(root/'protocol.json')
        ticks+=check_record(r,root/(key+'.jsonl'));episodes+=1
    print('Ablations: all 384 planned episodes, including failed variants, PASS integrity',flush=True)
    print('VERIFIED',episodes,'canonical episodes,',ticks,'saved ticks; duplicate parallel intermediates are not extra trials',flush=True)
    gate=load(DATA/'confirmation/development_gate.json')
    print('Original promotion gate:', 'PASS' if gate['passed'] else 'FAIL',gate['reasons'],flush=True)


if __name__=='__main__':main()
