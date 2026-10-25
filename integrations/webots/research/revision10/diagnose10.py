"""Post-training descriptive actor drift on the already frozen Step2 DEV rows.

No new labels, checkpoint selection or training. Off-policy diagnostics are not
closed-loop performance or a causal attribution of any PPO regression.
"""
import argparse,csv,json
from pathlib import Path
import numpy as np
import torch
from bootstrap import RESEARCH
from policy10 import P,FrozenStudent,logits
from evaluate10 import load_checkpoint,STUDENTS


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();torch.set_num_threads(1)
    with np.load(RESEARCH.parent/'results/revision8-student/data/dev.npz') as z:
        x=torch.from_numpy(z['x']);groups=z['groups'];costs=z['costs'];labels=z['labels']
    regret=np.clip((costs-costs.min(1)[:,None])/np.maximum(costs[:,2],1e-4)[:,None],0,1);rows=[]
    with torch.no_grad():
        for pair,seed in enumerate(P['rl_seeds']):
            student=FrozenStudent(STUDENTS/str(P['student_seeds'][pair]));teacher_logits=student(x);reference=teacher_logits.log_softmax(1);reference_class=teacher_logits.argmax(1)
            for arm in P['arms']:
                for step in P['checkpoints']:
                    actor=load_checkpoint(a.run/'training',arm,pair,step).model;outputs=logits(actor,x);logp=outputs.log_softmax(1);chosen=outputs.argmax(1).numpy()
                    chosen_regret=regret[np.arange(len(chosen)),chosen]
                    row=dict(arm=arm,seed=seed,steps=step,action_agreement=float(np.mean(chosen==reference_class.numpy())),
                        mean_student_to_ppo_kl=float((reference.exp()*(reference-logp)).sum(1).mean()),
                        mean_entropy=float(-(logp.exp()*logp).sum(1).mean()),nonzero_action_fraction=float(np.mean(chosen!=2)),
                        episode_mean_teacher_regret=float(np.mean([chosen_regret[groups==g].mean() for g in np.unique(groups)])),
                        label_accuracy=float(np.mean(chosen==labels)))
                    rows.append(row)
    with (a.run/'actor-drift.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
    lines=['# Descriptive actor drift','',
        'All24,300 original Step2 DEV observations and their existing labels/costs; no new teacher data, optimization or selection. These are off-policy supervised diagnostics, not fresh closed-loop results or proof of a causal mechanism.',
        '', '| Arm | RL seed | Steps | Argmax agreement with student | KL(student || PPO) | Episode mean teacher regret | Nonzero decisions |','|---|---|---:|---:|---:|---:|---:|']
    for r in rows:
        if r['steps']!=100000:continue
        lines.append(f'| {r["arm"]} | {r["seed"]} | {r["steps"]} | {r["action_agreement"]:.2%} | {r["mean_student_to_ppo_kl"]:.6f} | {r["episode_mean_teacher_regret"]:.6f} | {r["nonzero_action_fraction"]:.2%} |')
    lines+=['','PPO target KL is relative to each rollout policy, so it does not prevent cumulative drift from the initial student. Higher teacher regret indicates disagreement with this finite expected-cost teacher on these fixed observations; it is not independently a tracking or generalization claim. All four arms were frozen before training; no post-outcome anchor/reward retuning was run. This diagnostic is not used for selection.']
    (a.run/'actor-drift.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))


if __name__=='__main__':main()
