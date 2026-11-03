"""Semantic tamper checks on temporary copies, after updating aggregate checksums."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from .audit import check_python,check_native


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--python',required=True);p.add_argument('--native',required=True);a=p.parse_args()
    results={}
    for label,source,check in [('python',Path(a.python),check_python),('native',Path(a.native),check_native)]:
        with tempfile.TemporaryDirectory(prefix='lans-semantic-check-',dir='/tmp') as temp:
            root=Path(temp)/label;root.mkdir()
            shutil.copytree(source/'source',root/'source');shutil.copyfile(source/'plan.json',root/'plan.json')
            stage=root/'development';stage.mkdir();summary=json.loads((source/'development/summary.json').read_text())
            first=summary['results'][0];target=f"{first['case']}-{first['speed']:g}-{first['seed']}"
            for case in (source/'development').iterdir():
                if not case.is_dir():continue
                if case.name==target:shutil.copytree(case,stage/case.name)
                else:(stage/case.name).symlink_to(case.resolve(),target_is_directory=True)
            if label=='python':
                first['collisions']=1;record=json.loads((stage/target/'summary.json').read_text());record['collisions']=1
                (stage/target/'summary.json').write_text(json.dumps(record))
            else:
                trace=stage/target/'follower.jsonl';data=[json.loads(s) for s in trace.read_text().splitlines()]
                event=next(e for row in data for e in row['radio_incoming'] if 'state' in json.loads(e['message']))
                wire=json.loads(event['message']);wire['state'][0]+=.123;event['message']=json.dumps(wire)
                trace.write_text(''.join(json.dumps(row)+'\n' for row in data))
                newhash=hashlib.sha256(trace.read_bytes()).hexdigest();first['raw_sha256']['follower']=newhash
                record=json.loads((stage/target/'verification.json').read_text());record['raw_sha256']['follower']=newhash
                (stage/target/'verification.json').write_text(json.dumps(record))
            (stage/'summary.json').write_text(json.dumps(summary))
            try:check(root,'development')
            except AssertionError:results[label+'_semantic_corruption_rejected_after_rehash']=True
            else:raise RuntimeError('Auditor accepted '+label+' corruption')
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
