import json
import math
import numpy as np
import pytest
from tools.unified_campaign import campaign as base
from tools.unified_campaign.study import make_case,run_episode
from integrations.unified_lans.run import clean
from integrations.unified_lans.inference import sha
from tools.unified_improvement.verify import imports


def fixture(root):
    (root/'protocol.json').write_text('{}')
    dest=root/'development';dest.mkdir()
    result,rows=run_episode(make_case('development',0),'lqr',seconds=.25)
    results=[]
    for actor in range(10):
        key=f'000-lqr-{actor}';raw=dest/(key+'.jsonl')
        raw.write_text(''.join(json.dumps(clean(r))+'\n' for r in rows))
        results.append(dict(**result,actor=actor,raw_sha256=sha(raw)))
    (root/'development_summary.json').write_text(json.dumps(results))
    return dest


def test_full_raw_auditor_executes_and_detects_physics_tampering(tmp_path,monkeypatch):
    imports();fixture(tmp_path)
    monkeypatch.setattr(base,'check',lambda r:r)
    monkeypatch.setattr(base,'PROTOCOL',dict(cases_per_stage=1))
    result=base.audit(tmp_path,'development')
    assert result['passed'] and result['ticks']==50
    summary=json.loads((tmp_path/'development_summary.json').read_text())
    raw=tmp_path/'development/000-lqr-0.jsonl'
    rows=[json.loads(s) for s in raw.read_text().splitlines()];rows[0]['state_after'][1]+=.1
    raw.write_text(''.join(json.dumps(r)+'\n' for r in rows));summary[0]['raw_sha256']=sha(raw)
    (tmp_path/'development_summary.json').write_text(json.dumps(summary))
    with pytest.raises(AssertionError):base.audit(tmp_path,'development')
