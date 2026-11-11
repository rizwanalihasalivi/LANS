"""Post-evaluation diagnosis of recorded sequence-owner decision reasons."""
from collections import Counter,defaultdict
import json
from integrations.unified_lans.inference import sha
from tools.ppo_plan_v11.probe import dump
from .train import DATA


def main():
    out=DATA/'evaluation';records=json.loads((out/'summary.json').read_text());groups=defaultdict(Counter);hashes={}
    for record in records:
        if record['mode'] not in ('bc','v11','ppo'):continue
        c=record['case'];path=out/f'{c["id"]:03d}-{record["mode"]}-{record["seed"]}.jsonl'
        assert sha(path)==record['raw_sha256'];hashes[str(path.relative_to(DATA))]=sha(path)
        count=groups[(record['mode'],c['delay'])]
        for line in path.open():
            row=json.loads(line);count['ticks']+=1
            if row['source']=='ppo_plan':count['selected']+=1
            elif 'sequence_cost' not in row:count['not_scored']+=1
            elif row['sequence_margin']<0:count['recorded_predicted_guard_rejection']+=1
            elif row['sequence_cost']>=row['sequence_reference_cost']-1e-8:count['did_not_beat_analytical_cost']+=1
            else:count['other_nonselection']+=1
    rows=[]
    for (mode,delay),count in sorted(groups.items()):
        assert count['ticks']==sum(v for k,v in count.items() if k!='ticks')
        if delay==.1:assert count['selected']==0 and count['not_scored']==count['ticks']
        rows.append(dict(mode=mode,delay_s=delay,counts=dict(count)))
    report=dict(source_sha256=sha(__file__),protocol_sha256=sha(out/'protocol.json'),raw_sha256=hashes,groups=rows,
        scope='Descriptive counts of recorded owner reasons on the already-opened cohort; not causal attribution of training ingredients, a global headroom bound or independent certification of every rejected plan.')
    folder=DATA/'diagnostics';folder.mkdir(exist_ok=True);dump(folder/'recorded-authority.json',report)
    for row in rows:print(json.dumps(row))


if __name__=='__main__':main()
