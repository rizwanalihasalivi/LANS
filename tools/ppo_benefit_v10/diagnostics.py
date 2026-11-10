"""Training-only actor-fit and admission diagnostics; no prospective outcomes read."""
import json
from collections import Counter
import numpy as np
from integrations.unified_lans.inference import sha
from .core import DATA,dump


def main():
    import torch
    from stable_baselines3 import PPO
    torch.set_num_threads(1)
    dataset=DATA/'teacher/dataset.npz';data=np.load(dataset);obs=data['observations'];labels=data['actions'][:,0];weights=data['weights']
    report=[]
    for seed in (42,43,44):
        folder=DATA/f'policies/seed-{seed}';fit={}
        for mode,name in [('bc','bc-policy.zip'),('ppo','policy.zip')]:
            model=PPO.load(folder/name,device='cpu');values,_=model.predict(obs,deterministic=True);values=values[:,0]
            # Calibration coefficients are descriptive training diagnostics only;
            # no calibrated actor is deployed or evaluated in this study.
            design=np.c_[values,np.ones(len(values))];w=np.sqrt(weights)
            affine=np.linalg.lstsq(w[:,None]*design,w*labels,rcond=None)[0]
            fit[mode]=dict(model_sha256=sha(folder/name),mse=float(np.mean((values-labels)**2)),
                weighted_mse=float(np.sum(weights*(values-labels)**2)/np.sum(weights)),
                nonzero_label_mse=float(np.mean((values[labels!=0]-labels[labels!=0])**2)),
                mean_action=float(values.mean()),action_rms=float(np.sqrt(np.mean(values**2))),
                teacher_action_rms=float(np.sqrt(np.mean(labels**2))),
                learned_std_normalized=float(torch.exp(model.policy.log_std.detach())[0]),
                descriptive_affine_fit=affine.tolist())
        categories=Counter();sources=Counter();by_delay={};failures=0;steps=0
        for line in (folder/'training.jsonl').open():
            row=json.loads(line);decision=row['decision'];delay=str(row['case']['delay'])
            if 'ppo' in decision['eligible']:
                category='selected' if decision['source']=='ppo' else ('feasible_not_selected' if decision['eligible']['ppo'] else 'guard_rejected')
            elif decision['risk']=='DANGER':category='danger'
            elif decision['proposal_age'] is None:category='no_response'
            else:category='expired_or_unavailable'
            categories[category]+=1;sources[decision['source']]+=1;steps+=1;failures+=row['terminated']
            group=by_delay.setdefault(delay,Counter());group[category]+=1
        assert steps==16384
        report.append(dict(seed=seed,fit=fit,steps=steps,training_failures=failures,
            admission=dict(categories),sources=dict(sources),by_delay={k:dict(v) for k,v in by_delay.items()},
            trace_sha256=sha(folder/'training.jsonl')))
    dump(DATA/'training-diagnostics.json',dict(scope='Training data only; descriptive fit is not held-out performance.',
        source_sha256=sha(__file__),dataset_sha256=sha(dataset),actors=report))
    print('Saved training-only diagnostics; no prospective or final data read.')


if __name__=='__main__':main()
