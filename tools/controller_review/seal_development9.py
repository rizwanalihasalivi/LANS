"""Cache only the new full single-observation replay, with immutable inputs/data."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];out=ROOT/'docs/research/reviewer-pipeline-v9'
for name,digest in json.loads((out/'manifest.json').read_text())['hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
assert 'one observation per call' in json.loads((out/'decision.json').read_text())['actor_replay_shape']
files=[f for group in ('pair-0','pair-1','pair-2','actors','runtime-actors','legacy_history-0','legacy_history-1','legacy_history-2','causal_history-0','causal_history-1','causal_history-2') for f in (out/group).rglob('*') if f.is_file()]
files += [out/n for n in ('decision.json','summary.json','episodes.csv','manifest.json')]
hashes={str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
file=out/'development-evidence-hashes.json'
verifier=hashlib.sha256((ROOT/'tools/controller_review/verify_development9.py').read_bytes()).hexdigest()
value=dict(sha256=hashes,verifier_sha256=verifier,scope='Single-observation actor agreement and full causal/gate/physical replay')
if file.exists():assert value==json.loads(file.read_text()),'Replayed development evidence or verifier changed'
else:file.write_text(json.dumps(value,indent=2)+'\n')
print('Development replay seal verified:',len(hashes),'files')
