"""Check all archive/member hashes and content-preserving parallel aliases."""
from pathlib import Path
import json
from zipfile import ZipFile
from tools.unified_control_v5 import verify_evidence as common


def main():
    root=Path(__file__).parent/'evidence'
    assert len((root/'SHA256SUMS').read_text().splitlines())==4
    common.EVIDENCE=root;common.verify_archives()
    members={};aliases=[]
    for line in (root/'SHA256SUMS').read_text().splitlines():
        _,name=line.split(maxsplit=1)
        with ZipFile(root/name) as archive:
            manifest=json.loads(archive.read('EVIDENCE_MANIFEST.json'))['files']
            assert not set(members).intersection(manifest)
            members.update(manifest)
            for member in manifest:
                if member.endswith('/deduplicated_aliases.json'):aliases=json.loads(archive.read(member))
    assert aliases
    for alias in aliases:
        assert alias['original'] not in members
        target=members[alias['canonical']]
        assert target['sha256']==alias['sha256'] and target['size']==alias['size']
    print(len(aliases),'parallel intermediate content aliases verified; no duplicate trial counts')


if __name__=='__main__':main()
