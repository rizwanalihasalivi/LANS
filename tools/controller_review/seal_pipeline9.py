"""Content seal for new, independently replayed finite-study evidence."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--seal',action='store_true');a=p.parse_args();out=a.run
    for name,digest in json.loads((out/'manifest.json').read_text())['hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    for name,digest in json.loads((out/'actors/manifest.json').read_text())['sha256'].items():assert hashlib.sha256((out/'actors'/name).read_bytes()).hexdigest()==digest,name
    for name,digest in json.loads((out/'timing/protocol.json').read_text())['hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    paths=[]
    for group in ('pair-0','pair-1','pair-2','actors','runtime-actors','timing','legacy_history-0','legacy_history-1','legacy_history-2','causal_history-0','causal_history-1','causal_history-2','kit-smoke'):
        paths.extend(f for f in (out/group).rglob('*') if f.is_file() and 'source' not in f.relative_to(out/group).parts and f.suffix in ('.npz','.json','.csv','.zip','.pkl'))
    paths += [out/n for n in ('manifest.json','summary.json','decision.json','episodes.csv','development-evidence-hashes.json','batch-replay-discrepancy.json','verification.log','student-bridge-check.json','admission-analysis.json')]
    hashes={str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths};file=out/'evidence-hashes.json'
    if file.exists():assert json.loads(file.read_text())['sha256']==hashes,'Raw evidence changed; investigate rather than overwrite'
    else:
        assert a.seal and (out/'timing/full-verification.json').exists() and (out/'kit-smoke/full-verification.json').exists()
        file.write_text(json.dumps(dict(sha256=hashes,scope='Raw training, models, development replay, original timing and packaging smoke; reports separate'),indent=2)+'\n')
    print('Verified',len(hashes),'raw evidence files')
if __name__=='__main__':main()
