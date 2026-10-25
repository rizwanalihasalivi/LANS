"""Inspect original supplied packages without running or extracting their code."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def inspect(path):
    result = dict(archive=path.name, missing=[], mismatched=[], external_path_members=[])
    with zipfile.ZipFile(path) as archive:
        result['crc_error'] = archive.testzip()
        names = set(archive.namelist())
        manifests = [n for n in names if n.endswith('FILE_MANIFEST.json')]
        result['manifest_files'] = manifests
        for name in sorted(manifests):
            base = str(PurePosixPath(name).parent)
            for relative, expected in json.loads(archive.read(name)).items():
                member = base+'/'+relative if base != '.' else relative
                if member not in names:
                    result['missing'].append(member)
                    continue
                content = archive.read(member)
                if len(content) != expected['bytes'] or hashlib.sha256(content).hexdigest() != expected['sha256']:
                    result['mismatched'].append(member)
        for name in sorted(names):
            if name.endswith('.py') and b'/mnt/data/' in archive.read(name):
                result['external_path_members'].append(name)
    result['self_contained_reproduction_verified'] = False
    result['status'] = 'incomplete_or_nonportable' if result['missing'] or result['mismatched'] or result['crc_error'] or result['external_path_members'] else 'inventory_only'
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',type=Path,default=Path(__file__).resolve().parents[2]/'research-inputs')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    archives=sorted(args.input_dir.glob('*.zip'))
    if not archives:
        raise ValueError('no supplied ZIP archives found')
    results=[inspect(path) for path in archives]
    with args.output.open('x') as stream:
        json.dump(dict(purpose='archive inventory, not execution or completeness certification',archives=results),stream,indent=2)
        stream.write('\n')
    print(args.output)


if __name__ == '__main__':
    main()
