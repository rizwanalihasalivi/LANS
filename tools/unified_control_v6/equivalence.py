"""Closed-loop regression of equivalent backend against eight fixed raw traces."""
from pathlib import Path
import json
import numpy as np
from integrations.unified_lans.inference import load_policy,sha
from integrations.unified_lans.run import clean
from .ablation import run_episode,audit
from .campaign import selected
from .fast_control import Controller

ROOT=Path(__file__).resolve().parents[2]


def main():
    import torch
    torch.set_num_threads(1)
    original=ROOT/'results/proposal-completion-v6/ablations'
    out=original.parent/'backend-equivalence';out.mkdir(exist_ok=False)
    protocol=json.loads((original/'protocol.json').read_text())
    cases=[c for c in protocol['cases'] if c['replicate']==0 and c['profile'] in ('nominal','command_delay')]
    assert len(cases)==8;choice,Original=selected();model=load_policy(ROOT/'results/python-campaign-v2/policies/seed-42')
    (out/'protocol.json').write_text(json.dumps(dict(cases=cases,tolerance=1e-12,
        original_protocol_sha256=sha(original/'protocol.json'),fast_source_sha256=sha(Path(__file__).with_name('fast_control.py')),
        purpose='paired fresh-original implementation regression; historical comparison retained separately; not independent outcomes'),indent=2))
    results=[]
    for case in cases:
        raw=original/f'{case["id"]:03d}-full.jsonl';record=json.loads((original/f'{case["id"]:03d}-full.json').read_text())
        assert sha(raw)==record['raw_sha256'];before=[json.loads(line) for line in raw.read_text().splitlines()]
        original_result,fresh=run_episode(case,'full',model,choice,Original);audit(original_result,fresh)
        result,after=run_episode(case,'full',model,choice,Controller);audit(result,after)
        for name,rows in [('reference',fresh),('fast',after)]:
            target=out/f'{case["id"]:03d}-{name}.jsonl';target.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
        assert len(before)==len(fresh)==len(after)
        history_difference=max(float(np.max(abs(np.asarray(a['state_after'])-np.asarray(b['state_after'])))) for a,b in zip(before,fresh))
        for a,b in zip(fresh,after):
            for field in ['state_before','state_after','issued_steering','issued_accel','applied_steering','applied_accel']:
                np.testing.assert_allclose(a[field],b[field],rtol=0,atol=1e-12)
            assert a['source']==b['source']
        target=out/f'{case["id"]:03d}-fast.jsonl'
        results.append(dict(case_id=case['id'],ticks=len(after),historical_sha256=sha(raw),
            fresh_reference_sha256=sha(out/f'{case["id"]:03d}-reference.jsonl'),
            original_replay_max_historical_state_difference=history_difference,
            fast_raw_sha256=sha(target),passed=True))
        print('Exact closed-loop backend regression',len(results),'/',len(cases),'PASS',flush=True)
    (out/'audit.json').write_text(json.dumps(dict(passed=True,episodes=8,ticks=sum(r['ticks'] for r in results),results=results),indent=2))


if __name__=='__main__':main()
