"""Verify frozen inputs and seal/check independently replayed raw evidence."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--seal',action='store_true');a=p.parse_args();out=a.run
    for name,digest in json.loads((out/'manifest.json').read_text())['hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    for group,key in (('timing','hashes'),('dynamic-recovery','source_hashes')):
        for name,digest in json.loads((out/group/'protocol.json').read_text())[key].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    paths=[]
    for group in ('pair-0','pair-1','pair-2','actors','timing','dynamic-recovery','kit-smoke'):
        paths.extend(f for f in (out/group).rglob('*') if f.is_file() and 'source' not in f.relative_to(out/group).parts and f.suffix in ('.npz','.json','.csv'))
    paths += [out/n for n in ('manifest.json','summary.json','decision.json','episodes.csv')]
    hashes={str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths}
    file=out/'evidence-hashes.json'
    if file.exists():assert json.loads(file.read_text())['sha256']==hashes,'Verified raw evidence changed; inspect, do not overwrite the seal'
    else:
        assert a.seal,'Evidence seal missing; seal only after complete replay'
        assert (out/'timing/verification.json').exists() and (out/'dynamic-recovery/verification.json').exists()
        file.write_text(json.dumps(dict(sha256=hashes,scope='Verified inputs and raw data; derived PDF/Word build metadata deliberately separate'),indent=2)+'\n')
    print('Verified frozen inputs and',len(hashes),'raw evidence files')

if __name__=='__main__':main()
