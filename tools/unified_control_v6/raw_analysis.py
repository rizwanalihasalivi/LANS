"""Machine-readable experiment analysis only; no draft, figure or table exports."""
from pathlib import Path
import json
from integrations.unified_lans.inference import sha
from integrations.unified_lans.run import clean
from .analyze import aggregate,contrasts,prediction_study

ROOT=Path(__file__).resolve().parents[2]


def main():
    root=ROOT/'results/proposal-completion-v6/ablations'
    out=root.parent/'analysis';out.mkdir(exist_ok=False)
    protocol=json.loads((root/'protocol.json').read_text())
    records=json.loads((root/'summary.json').read_text())
    assert len(records)==384 and len({(r['case']['id'],r['variant']) for r in records})==384
    for r in records:
        assert sha(root/f'{r["case"]["id"]:03d}-{r["variant"]}.jsonl')==r['raw_sha256']
    summaries=[dict(variant=v,**aggregate([r for r in records if r['variant']==v])) for v in protocol['variants']]
    for summary in summaries:
        summary['safe_goal_achievements']=sum(r['goal_reached'] and not r['failed'] for r in records if r['variant']==summary['variant'])
    profiles=[dict(variant=v,profile=p,**aggregate([r for r in records if r['variant']==v and r['case']['profile']==p]))
              for v in protocol['variants'] for p in sorted({r['case']['profile'] for r in records})]
    result=dict(protocol_sha256=sha(root/'protocol.json'),summary=summaries,by_profile=profiles,contrasts=contrasts(records))
    (out/'component_results.json').write_text(json.dumps(clean(result),indent=2))
    prediction=prediction_study(root,records,protocol['config'])
    (out/'prediction_ranking.json').write_text(json.dumps(clean(prediction),indent=2))
    (out/'provenance.json').write_text(json.dumps(dict(analysis_source_sha256=sha(Path(__file__)),
        computation_source_sha256=sha(Path(__file__).with_name('analyze.py')),
        policy='No thesis draft, figure or presentation table generated, per user instruction',
        postprocessing_notes=['Constant-cost actuator-saturated grids have undefined rank, not perfect rank; exclude them from mean Spearman.',
                              'Distance-goal flags and safety-constrained goal achievement are reported separately.']),indent=2))
    print('Completed machine-readable component contrasts and controlled prediction diagnostic.',flush=True)


if __name__=='__main__':main()
