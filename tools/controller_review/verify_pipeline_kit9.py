"""A cached ZIP must still match the frozen source, selected actors and disk bundle."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();kit=a.run/'LANS_Causal_Python310_Kit';decision=json.loads((a.run/'decision.json').read_text());models=a.run/'runtime-actors'/(decision['selected'] or 'legacy_history')
manifest=json.loads((kit/'bundle-manifest.json').read_text())['sha256'];names=set(manifest)|{'bundle-manifest.json'}
for name,digest in manifest.items():
    file=kit/name;assert hashlib.sha256(file.read_bytes()).hexdigest()==digest,name
    if name.startswith(('tools/','integrations/')):assert file.read_bytes()==(ROOT/name).read_bytes(),name
    if name.startswith('actor/'):assert file.read_bytes()==(models/name[6:]).read_bytes(),name
assert (kit/'requirements.txt').read_text()=='numpy==1.23.5\nscipy==1.10.1\nnumba==0.57.1\ngymnasium==0.28.1\n'
with zipfile.ZipFile(kit.with_suffix('.zip')) as z:
    assert z.testzip() is None
    expected={str(Path(kit.name)/name) for name in names};assert set(z.namelist())==expected
    for name in names:assert z.read(str(Path(kit.name)/name))==(kit/name).read_bytes(),name
print('Cached source/model bundle and ZIP verified:',len(names),'files')
