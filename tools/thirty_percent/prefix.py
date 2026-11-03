"""Conditional error floor if an existing controller's initial prefix is retained."""
from pathlib import Path
import json,math
from integrations.unified_lans.inference import sha

ROOT=Path(__file__).resolve().parents[2]


def main():
    root=ROOT/'results/thirty-percent-headroom';protocol=json.loads((root/'protocol.json').read_text())
    rows=[]
    for record in protocol['cases']:
        path=root/'input'/f'{record["case"]["id"]:03d}-lqr-0.jsonl'
        assert sha(path)==record['raw_sha256']
        raw=[json.loads(s) for s in path.read_text().splitlines()]
        rows.append(dict(case_id=record['case']['id'],prefix_floors={str(t):math.sqrt(sum(r['error']**2 for r in raw[:round(t/.05)])/120)
            for t in [.05,.1,.25,.5,1.,2.]},
            first_second_sse_fraction=sum(r['error']**2 for r in raw[:20])/sum(r['error']**2 for r in raw)))
    summary=[]
    for duration in [.05,.1,.25,.5,1.,2.]:
        lower=sum(r['prefix_floors'][str(duration)] for r in rows)/len(rows)
        summary.append(dict(prefix_seconds=duration,conditional_mean_rmse_floor_m=lower,
            largest_possible_gain_if_prefix_unchanged_percent=100*(1-lower/protocol['baseline_mean_rmse_m']),
            thirty_percent_requires_changing_this_prefix=lower>protocol['target_mean_rmse_m']))
    output=dict(scope='rigorous only conditional on exactly retaining the specified baseline error prefix; not an actuator reachability bound',
        assumption='all later squared tracking errors optimistically zero',source_sha256=sha(Path(__file__)),
        cases=rows,summary=summary,mean_first_second_sse_fraction=sum(r['first_second_sse_fraction'] for r in rows)/len(rows))
    dest=root/'prefix_floor.json';assert not dest.exists();dest.write_text(json.dumps(output,indent=2))
    print(json.dumps(dict(summary=summary,mean_first_second_sse_fraction=output['mean_first_second_sse_fraction']),indent=2))


if __name__=='__main__':main()
