"""Audit raw ticks independently of runner summaries; fail on broken contracts."""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from .inference import sha
from .physics import Command, Config, Route, advance, errors


def audit(root):
    root=Path(root);provenance=json.loads((root/'provenance.json').read_text())
    cfg=Config(**provenance['config']);summaries=json.loads((root/'summary.json').read_text());audits=[]
    current={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}
    # Historical provenance remains useful after new source edits; raw validation
    # is explicit about whether today's source matches the execution snapshot.
    source_matches=provenance['sources']==current
    folders=sorted(p for p in root.iterdir() if p.is_dir())
    assert len(folders)==len(summaries)>0
    assert len({s['case_dir'] for s in summaries})==len(summaries)
    for summary in summaries:
        folder=root/summary['case_dir']
        local=json.loads((folder/'summary.json').read_text());assert local==summary
        assert sha(folder/'ticks.jsonl')==summary['raw_sha256']
        rows=[json.loads(s) for s in (folder/'ticks.jsonl').read_text().splitlines()]
        assert len(rows)==summary['ticks']>0
        previous=Command();issued=Command();pending=[];commands=[]
        route=Route('sine' if summary['scenario']=='curved' else ('lane_change' if summary['scenario']=='merge' else 'straight'))
        previous_state=None
        for i,r in enumerate(rows):
            assert r['tick']==i and r['time_s']==i*cfg.dt
            if previous_state is not None:np.testing.assert_allclose(r['state_before'],previous_state,rtol=0,atol=1e-12)
            command=Command(r['issued_steering'],r['issued_accel'])
            assert abs(command.steering)<=cfg.steering_limit+1e-10
            assert abs(command.steering-issued.steering)<=cfg.steering_rate*cfg.dt+1e-10
            assert -cfg.max_brake<=command.accel<=cfg.max_accel
            issued=command;pending.append((r['time_s']+summary['command_delay_s'],command))
            while pending and pending[0][0]<=r['time_s']+1e-9:_,previous=pending.pop(0)
            assert previous==Command(r['applied_steering'],r['applied_accel'])
            if r['missing']:
                assert r['source'] in ('lqr','hold_brake') and r['issued_accel']==-cfg.max_brake
            if r['worker_failed']:assert r['source'] in ('lqr','hold_brake')
            if r['source']=='ppo':
                assert 0<=r['proposal_age']<cfg.proposal_ttl
                assert 0<=r['proposal_wall_age']<cfg.proposal_ttl
                assert r['eligible']['ppo'] and r['risk']!='DANGER'
                assert r['costs']['ppo']<r['costs']['lqr'] or not r['eligible']['lqr']
            predicted=advance(r['state_before'],previous,cfg.dt,summary['stiffness'])
            np.testing.assert_allclose(predicted,r['state_after'],rtol=0,atol=1e-12)
            state=np.array(r['state_after']);e,_=errors(state,route)
            assert abs(float(e[0])-r['error'])<1e-12
            distance=min(np.linalg.norm(np.array(n[:2])-state[:2])-2*cfg.vehicle_radius for n in r['npc_truth'].values())
            assert abs(distance-r['true_clearance'])<1e-10
            assert r['collision']==(distance<=0)
            previous_state=r['state_after'];commands.append(previous)
        rmse=float(np.sqrt(np.mean([r['error']**2 for r in rows])))
        assert abs(rmse-summary['rmse_m'])<1e-12
        assert summary['collision']==any(r['collision'] for r in rows)
        audits.append(dict(case=folder.name,ticks=len(rows),rmse_m=rmse,raw_sha256=sha(folder/'ticks.jsonl')))
    result=dict(passed=True,source_matches=source_matches,episodes=len(audits),ticks=sum(r['ticks'] for r in audits),cases=audits,
                scope='command/FIFO/freshness/fallback/physics and metric replay; not independent scientific or physical validation')
    (root/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run')
    a=parser.parse_args();result=audit(a.run)
    print(f"AUDIT PASS: {result['episodes']} episodes, {result['ticks']} ticks; source_matches={result['source_matches']}")
