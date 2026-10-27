import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
import verify_full_laptop as portable_verify


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args();out=args.run
    cfg=json.loads((out/'protocol.json').read_text())
    for n,h in cfg['source_hashes'].items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h
    portable_verify.CASES.clear();portable_verify.CASES.update(recover=0.)
    for seed in cfg['seeds']:
        sys.argv=['verify_full_laptop.py','--run',str(out/f'seed-{seed}'),'--models',str(ROOT/'docs/research/reviewer-aligned-v3/portable-actor')]
        portable_verify.main()
    (out/'verification.json').write_text(json.dumps(dict(raw_deadlines_model_physical_features_and_plant_replayed=True,
        source_hashes_verified=True,seeds=cfg['seeds']))+'\n')


if __name__=='__main__':main()
