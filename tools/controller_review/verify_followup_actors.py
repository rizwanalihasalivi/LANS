"""Replay every submitted development proposal from recorded causal features."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/reviewer_followup'))
import boot
import numpy as np
import torch
from stable_baselines3 import PPO
from causal_student import load_causal


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args()
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    counts={};models={}
    for pair,seed in enumerate((2701,2802,2903)):
        student=load_causal(ROOT/f'docs/research/causal-interface-2026-10-26/models/{(701,802,903)[pair]}')
        ppo=PPO.load(ROOT/f'docs/research/reviewer-causal-v1/training/finetune-{seed}/policy.zip',device='cpu')
        for path in sorted((args.run/f'pair-{pair}/traces').glob('*.csv.gz')):
            source=path.name.removesuffix('.csv.gz').split('-')[-1]
            if source not in ('student','ppo'):continue
            with gzip.open(path,'rt') as handle:rows=[r for r in csv.DictReader(handle) if r['submitted']=='True']
            x=np.array([[float(r[f'obs{i}']) for i in range(20)] for r in rows],dtype=np.float32)
            assert np.isfinite(x).all() and np.all(x[:,[14,15,16,17,19]]==0)
            with torch.no_grad():
                index=student(torch.from_numpy(x)).argmax(1).numpy() if source=='student' else ppo.predict(x,deterministic=True)[0]
            expected=np.array([-.08,-.04,0.,.04,.08])[index]
            assert np.allclose(expected,[float(r['proposed_residual']) for r in rows],rtol=0,atol=1e-8),path
            counts[source]=counts.get(source,0)+len(rows)
        print(pair,counts,flush=True)
    manifest=json.loads((args.run/'manifest.json').read_text())
    for name,digest in manifest['hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    (args.run/'actor-verification.json').write_text(json.dumps(dict(submitted_queries=counts,disagreements=0,
        causal_removed_channels_verified=True,all_frozen_input_hashes_verified=True),indent=2)+'\n')


if __name__=='__main__':main()
