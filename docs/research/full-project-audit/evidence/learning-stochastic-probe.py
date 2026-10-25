"""Off-policy behavior diagnostic; no fitting, selection or fresh tracking claim."""
import sys,json,argparse
from pathlib import Path
import numpy as np,torch
p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
sys.path.insert(0,str(a.repo/'integrations/webots/research/revision9'))
from policy9 import FrozenStudent
root=a.repo/'integrations/webots/results';data=np.load(root/'revision8-student/data/dev.npz');cost=data['costs'];regret=np.clip((cost-cost.min(1,keepdims=True))/np.maximum(cost[:,2:3],1e-4),0,1);groups=data['groups'];rows=[]
for seed in [701,802,903]:
 model=FrozenStudent(root/f'revision8-student/students/{seed}')
 with torch.no_grad():probs=torch.softmax(model(torch.from_numpy(data['x'])),1).numpy()
 chosen=probs.argmax(1);expected=(probs*regret).sum(1);det=regret[np.arange(len(chosen)),chosen]
 grouped=lambda x:float(np.mean(np.bincount(groups,weights=x)/np.bincount(groups)))
 rows.append(dict(student_seed=seed,observations=len(chosen),argmax_teacher_regret=grouped(det),sampled_expected_teacher_regret=grouped(expected),probability_of_non_argmax_action=float(np.mean(1-probs.max(1))),sampled_nonzero_fraction=float(np.mean(1-probs[:,2])),argmax_nonzero_fraction=float(np.mean(chosen!=2))))
a.output.write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))
