"""Replay returned portable-worker packets against their original Torch policies."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/reviewer_v5'))
import boot5
import numpy as np
import torch
from stable_baselines3 import PPO

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();out=a.run
    torch.set_num_threads(1)
    manifest=json.loads((out/'portable-actor/manifest.json').read_text())
    package=json.loads((out/'package-provenance.json').read_text());models={}
    for pair,seed in enumerate((701,802,903)):
        f=out/f'{package["arm"]}-{pair}/policy.zip'
        assert hashlib.sha256(f.read_bytes()).hexdigest()==manifest['model_provenance'][str(seed)]['source_sha256']
        models[seed]=PPO.load(f,device='cpu')
    summary=json.loads((out/'kit-smoke/summary.json').read_text());count=0
    for episode in summary['episodes']:
        for row in csv.DictReader((out/'kit-smoke'/f'{episode["case"]}-packets.csv').open()):
            x=np.array(json.loads(row['observation_json']),dtype=np.float32)
            assert x.shape==(20,) and np.isfinite(x).all() and np.all(x[[15,16,17,19]]==0)
            action,_=models[episode['seed']].predict(x,deterministic=True)
            assert abs([-.08,-.04,0.,.04,.08][int(action)]-float(row['residual']))<1e-12
            count+=1
    assert count>0
    result=dict(returned_packets=count,torch_source_action_disagreements=0,all_three_source_hashes_verified=True,scope='Cloud portability diagnostic; not actual laptop or selected-controller timing validation')
    (out/'runtime-policy-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(result)

if __name__=='__main__':main()
