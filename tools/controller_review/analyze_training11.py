"""Descriptive diagnostics after the frozen continued-PPO experiment; no tuning."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();out=a.run.resolve();rows=list(csv.DictReader((out/'episodes.csv').open()));groups={};costs={};new_entropy=[];old_entropy=[];agreements=0;compared=0
    def logits(m,x):return np.tanh(np.tanh(((x-m['mean'])/m['std'])@m['w0']+m['b0'])@m['w1']+m['b1'])@m['w2']+m['b2']
    def entropy(y):
        p=np.exp(y-y.max());p/=p.sum();return float(-(p*np.log(np.maximum(p,1e-30))).sum())
    for pair,seed in enumerate((701,802,903)):
        models={kind:dict(np.load(out/f'actors/{kind}-{seed}.npz',allow_pickle=False)) for kind in ('oldppo_rk','newppo_rk')}
        rr=[r for r in rows if int(r['pair'])==pair]
        for r in rr:
            source=r['source'];key=source+'/'+r['scenario'];g=groups.setdefault(key,dict(ticks=0,active=0,submitted=0,weight_sum=0.,reasons=Counter(),proposal_classes=Counter()))
            with np.load(out/f'pair-{pair}/traces'/r['trace'],allow_pickle=False) as d:
                n=len(d['command']);mask=d['submitted'].astype(bool);g['ticks']+=n;g['active']+=int(np.count_nonzero(d['weight']));g['submitted']+=int(mask.sum());g['weight_sum']+=float(d['weight'].sum());g['reasons'].update(d['reason'].tolist());g['proposal_classes'].update(map(str,d['proposed_residual'][mask].tolist()))
                parts=dict(lateral=float(np.mean((d['lateral_error']/.5)**2)),heading=float(.2*np.mean((d['heading_error']/.1)**2)),actuator_rate=float(.2*np.mean((d['steering_rate']/.35)**2)),command=float(.005*np.mean((d['command']/.5)**2)))
                assert abs(sum(parts.values())+float(d['reward'].mean()))<1e-11
                costs.setdefault(source,[]).append(parts)
                if source=='newppo_rk':
                    for x in d['query'][mask]:
                        before=logits(models['oldppo_rk'],x[None,:])[0];after=logits(models['newppo_rk'],x[None,:])[0]
                        old_entropy.append(entropy(before));new_entropy.append(entropy(after));agreements+=int(before.argmax()==after.argmax());compared+=1
    for g in groups.values():g.update(active_fraction=g['active']/g['ticks'],mean_weight=g['weight_sum']/g['ticks']);g['reasons']=dict(g['reasons']);g['proposal_classes']=dict(g['proposal_classes'])
    decomposition={source:{k:float(np.mean([x[k] for x in values])) for k in values[0]} for source,values in costs.items()}
    for v in decomposition.values():v['total_physical_cost']=sum(v.values())
    checkpoints=[]
    for pair in range(3):
        progress=list(csv.DictReader((out/f'training-{pair}/progress.csv').open()));last=progress[-1];checkpoints.append(dict(pair=pair,last_logged_environment_steps=int(last['time/total_timesteps']),last_logged_kl=float(last['train/approx_kl']),last_logged_entropy=-float(last['train/entropy_loss']),last_logged_explained_variance=float(last['train/explained_variance']),scope='SB3 progress logs are emitted before each iteration update; these are last logged diagnostics, not a recomputation of final optimizer metrics.'))
    result=dict(scope='Post-hoc descriptive development analysis, not parameter selection or new training. Entropy/argmax comparison uses the SAME new-policy visited inputs, not different trajectories.',groups=groups,physical_cost_decomposition=decomposition,matched_input_policy_comparison=dict(queries=compared,old_new_argmax_agreement=agreements/compared,old_entropy_mean=float(np.mean(old_entropy)),new_entropy_mean=float(np.mean(new_entropy))),last_logged_training=checkpoints,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),verified_raw_seal_sha256=hashlib.sha256((out/'evidence-hashes.json').read_bytes()).hexdigest())
    file=out/'learning-diagnostics.json'
    if file.exists():assert result==json.loads(file.read_text()),'Diagnostic source/data changed'
    else:file.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(policy_comparison=result['matched_input_policy_comparison'],costs=decomposition),indent=2))
if __name__=='__main__':main()
