"""Prespecified secondary time-window analysis; whole-episode target stays primary."""
from pathlib import Path
import json,math
import numpy as np
from integrations.unified_lans.inference import sha

ROOT=Path(__file__).resolve().parents[2]


def rmse(rows,start,end,expected=120):
    a=round(start/.05);b=round(end/.05);assert 0<=a<b<=expected
    sse=sum(rows[i]['error']**2 if i<len(rows) else 2.5**2 for i in range(a,b))
    return math.sqrt(sse/(b-a))


def main():
    root=ROOT/'results/causal-v7/confirmation';protocol=json.loads((root/'protocol.json').read_text())
    records=json.loads((root/'development_summary.json').read_text());raws={}
    for r in records:
        key=f'{r["case"]["id"]:03d}-{r["mode"]}-{r["actor"]}';raw=root/'development'/(key+'.jsonl')
        assert sha(raw)==r['raw_sha256'];raws[key]=[json.loads(line) for line in raw.read_text().splitlines()]
    windows=[('whole_primary',0.,6.)]
    for cutoff in protocol['prespecified_phase_cutoffs_s']:
        windows.extend([(f'initial_0_to_{cutoff:g}',0.,cutoff),(f'later_{cutoff:g}_to_6',cutoff,6.)])
    output=[]
    for label,start,end in windows:
        values={}
        for r in records:
            key=f'{r["case"]["id"]:03d}-{r["mode"]}-{r["actor"]}'
            values[(r['case']['id'],r['mode'],r['actor'])]=rmse(raws[key],start,end)
        for mode in ['lqr','optimized']:
            cells={}
            for r in [r for r in records if r['mode']==mode]:
                i=r['case']['id'];reference=values[(i,mode,0)];hybrid=np.mean([values[(i,'hybrid',s)] for s in [42,43,44]])
                cells.setdefault((r['case']['scenario'],r['case']['speed']),[]).append([reference,hybrid])
            pairs=np.array([np.mean(v,axis=0) for v in cells.values()]);draw=np.random.default_rng(71413001).integers(8,size=(5000,8));boot=pairs[draw].mean(axis=1)
            output.append(dict(window=label,start_s=start,end_s=end,reference=mode,
                reference_mean_rmse_m=float(pairs[:,0].mean()),hybrid_mean_rmse_m=float(pairs[:,1].mean()),
                gain_percent=float(100*(1-pairs[:,1].mean()/pairs[:,0].mean())),
                descriptive_ci95_percent=np.quantile(100*(1-boot[:,1]/boot[:,0]),[.025,.975]).tolist(),
                secondary=label!='whole_primary',may_satisfy_primary_target=label=='whole_primary'))
    target=root/'phase_metrics.json';assert not target.exists()
    target.write_text(json.dumps(dict(protocol_sha256=sha(root/'protocol.json'),results=output,
        scope='All prespecified windows retained. A secondary 30% phase gain is not a whole-episode 30% result.'),indent=2))
    print('Prespecified primary/secondary phase metrics saved; no window selection or promotion override.',flush=True)


if __name__=='__main__':main()
