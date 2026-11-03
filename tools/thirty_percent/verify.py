"""Read-only independent verification of all offline diagnostic traces and claims."""
from pathlib import Path
import json,math
import numpy as np
from integrations.unified_lans.inference import sha
from tools.unified_control_v4.control import ScheduledLQR
from tools.unified_campaign.study import StudyRoute,initial
from .run import ROOT,inputs,replay,metrics,feasible


def check_trace(record,args,path,actions):
    rows=[json.loads(s) for s in path.read_text().splitlines()]
    assert len(rows)==len(actions)==len(args[1])
    case=record['case'];route=StudyRoute(initial(case['scenario'])[0].kind,case['mirror'],case['phase'],case['amplitude'])
    baseline=ScheduledLQR(16.)
    np.testing.assert_array_equal(rows[0]['state_before'],args[0])
    for i,row in enumerate(rows):
        assert abs(row['acceleration']-args[1][i])<1e-12
        np.testing.assert_array_equal(row['npc_truth'],args[2][i])
        assert abs(row['requested_residual_rad']-.08*actions[i])<1e-12
        # A refreshed raw hash cannot make invented authority labels valid.
        expected=baseline(np.array(row['state_before']),route)
        assert abs(expected-row['baseline_steering'])<=1e-8
    return replay(rows,record)


def snapshots(root):
    p=json.loads((root/'protocol.json').read_text())
    for name,h in p['source_hashes'].items():assert sha(root/'source'/name)==h,('source snapshot',name)
    for name in ['integrations/unified_lans/physics.py','tools/unified_control_v4/control.py','tools/unified_campaign/study.py']:
        assert sha(ROOT/name)==p['source_hashes'][name],('active replay source changed',name)
    return p


def close_metrics(actual,reported):
    for key,value in actual.items():
        if isinstance(value,bool):assert value==reported[key]
        else:assert abs(value-reported[key])<=1e-8,(key,value,reported[key])


def summarized(records):
    reference_mean=float(np.mean([r['reference']['rmse_m'] for r in records]));mean=float(np.mean([r['metrics']['rmse_m'] for r in records]))
    heading=np.mean([r['metrics']['heading_rms'] for r in records])/np.mean([r['reference']['heading_rms'] for r in records])
    rate=np.mean([r['metrics']['rate_rms'] for r in records])/np.mean([r['reference']['rate_rms'] for r in records])
    cells={}
    for r in sorted(records,key=lambda r:r['case']['id']):cells.setdefault((r['case']['scenario'],r['case']['speed']),[]).append([r['reference']['rmse_m'],r['metrics']['rmse_m']])
    pairs=np.array([np.mean(v,axis=0) for v in cells.values()]);assert len(pairs)==8
    draw=np.random.default_rng(30413001).integers(8,size=(5000,8));boot=pairs[draw].mean(axis=1)
    return dict(mean_rmse_m=mean,gain_percent=100*(1-mean/reference_mean),heading_mean_ratio=float(heading),rate_mean_ratio=float(rate),
                ci95_percent=np.quantile(100*(1-boot[:,1]/boot[:,0]),[.025,.975]).tolist())


def main():
    local=ROOT/'results/thirty-percent-headroom';conic=ROOT/'results/thirty-percent-conic'
    p=snapshots(local);q=snapshots(conic);assert q['input_protocol_sha256']==sha(local/'protocol.json')
    sources={r['case']['id']:r for r in p['cases']};assert sorted(sources)==list(range(32))
    summary=json.loads((local/'summary.json').read_text());all_local=json.loads((local/'all_results.json').read_text())
    assert len(all_local)==64 and len({(r['mode'],r['case']['id']) for r in all_local})==64
    count=0;ticks=0
    for r in all_local:
        record=sources[r['case']['id']];assert r['reference']==record
        _,args,reference=inputs(local,record);directory=local/f'{r["case"]["id"]:03d}-{r["mode"]}'
        assert r==json.loads((directory/'result.json').read_text())
        for label,key in [('candidate','candidate_actions'),('accepted','accepted_actions')]:
            raw=directory/f'{label}.jsonl';assert sha(raw)==r[f'{label}_raw_sha256']
            values=check_trace(record,args,raw,np.array(r[key]));actual=metrics(values,120,reference)
            close_metrics(actual,r['candidate_metrics'] if label=='candidate' else r['metrics']);count+=1;ticks+=120
        accepted=bool(r['solver']['success']) and feasible(r['candidate_metrics'],r['mode']=='quality_constrained')
        assert accepted==r['accepted']
        np.testing.assert_array_equal(r['accepted_actions'],r['candidate_actions'] if accepted else np.zeros(120))
    for row in summary:
        rr=[r for r in all_local if r['mode']==row['mode']];values=summarized(rr)
        for key in ['mean_rmse_m','gain_percent','heading_mean_ratio','rate_mean_ratio']:assert abs(values[key]-row[key])<1e-8
        np.testing.assert_allclose(values['ci95_percent'],row['ci95_percent'],rtol=0,atol=1e-8)
        assert row['accepted_solves']==sum(r['accepted'] for r in rr)
        assert row['thirty_percent_mean_target_met']==(row['gain_percent']>=30.)
    print('Local diagnostic: all 64 solves, 128 candidate/fallback traces, source hashes and bootstrap metrics verified',flush=True)
    conic_records=json.loads((conic/'all_results.json').read_text());assert len(conic_records)==64
    assert len({(r['mode'],r['case']['id']) for r in conic_records})==64
    for r in conic_records:
        record=sources[r['case']['id']];assert r['reference']==record
        _,args,reference=inputs(local,record);raw=conic/r['mode']/f'{r["case"]["id"]:03d}.jsonl'
        assert sha(raw)==r['raw_sha256'];assert r==json.loads(raw.with_suffix('.json').read_text())
        values=check_trace(record,args,raw,np.array(r['actions']));close_metrics(metrics(values,120,reference),r['metrics']);count+=1;ticks+=120
    for row in json.loads((conic/'summary.json').read_text()):
        rr=[r for r in conic_records if r['mode']==row['mode']];values=summarized(rr)
        for key in ['mean_rmse_m','gain_percent','heading_mean_ratio','rate_mean_ratio']:assert abs(values[key]-row[key])<1e-8
        np.testing.assert_allclose(values['ci95_percent'],row['ci95_percent'],rtol=0,atol=1e-8)
        quality=values['heading_mean_ratio']<=1.10+1e-12 and values['rate_mean_ratio']<=1.10+1e-12
        assert quality==row['original_mean_quality_passed']
        assert row['thirty_percent_mean_target_met']==(row['gain_percent']>=30.)
        logs=[json.loads((conic/row['mode']/f'iteration-{i}.json').read_text()) for i in range(6)]
        assert len(logs)==6 and all(logs[i]['after']['mean_rmse_m']<=logs[i]['before']['mean_rmse_m']+1e-12 for i in range(6))
    print('Joint conic diagnostic: all 64 final traces and both actual-quality outcomes verified',flush=True)
    print(count,'diagnostic traces,',ticks,'steps checked; same 32 observed fixtures, not independent new traffic trials',flush=True)
    print('30% tracking target: NOT ACHIEVED. No offline result promoted as causal hybrid/PPO validation.',flush=True)


if __name__=='__main__':main()
