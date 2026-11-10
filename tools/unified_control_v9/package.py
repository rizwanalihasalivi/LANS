"""Seal complete v9 raw evidence in bounded archives; independently verify bytes.

Large traces are split into byte-preserving members, never shortened or sampled.
The seal maps every original file to its ordered pieces and pins the complete
audit and source snapshot. Run only after the final audit and focused checks.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import platform
import shutil
import tempfile
import zipfile
from importlib.metadata import version

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'results/publication-v9'
OUT = Path(__file__).parent / 'evidence'
MAX_ARCHIVE_BYTES = 50 * 1024 ** 2
RAW_BUDGET = 40 * 1024 ** 2
CHUNK_BYTES = 32 * 1024 ** 2
CACHE_SUFFIXES = {'.pyc', '.pyo', '.nbc', '.nbi'}
PRESENTATION_SUFFIXES = {'.pdf', '.png', '.svg', '.jpg', '.jpeg', '.csv', '.docx', '.pptx'}
STAGES = {'calibration': ('episodes', 576), 'baselines': ('episodes', 448),
          'training': ('steps', 49152), 'confirmation': ('episodes', 2416),
          'runtime': ('checks', 20), 'native': ('episodes', 16)}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 ** 2), b''):
            result.update(block)
    return result.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def safe_name(name):
    assert isinstance(name, str) and name and '\\' not in name and '\x00' not in name
    path = PurePosixPath(name)
    assert path.parts and not path.is_absolute() and '..' not in path.parts and str(path) == name, name
    return name


def inventory(data, root):
    """Do not follow native project controller symlinks or include generated caches."""
    members, skipped = [], []
    for folder, directories, filenames in os.walk(data, followlinks=False):
        base = Path(folder)
        for name in sorted(list(directories)):
            path = base / name
            if path.is_symlink() or name in ('__pycache__', '.pytest_cache'):
                directories.remove(name)
                skipped.append(dict(path=str(path.relative_to(root)),
                    reason='symlink_not_followed' if path.is_symlink() else 'generated_cache',
                    target=os.readlink(path) if path.is_symlink() else None))
        for name in sorted(filenames):
            path = base / name
            if path.is_symlink() or path.suffix in CACHE_SUFFIXES:
                skipped.append(dict(path=str(path.relative_to(root)),
                    reason='symlink_not_followed' if path.is_symlink() else 'generated_cache',
                    target=os.readlink(path) if path.is_symlink() else None))
                continue
            assert path.is_file(), path
            assert path.suffix.lower() not in PRESENTATION_SUFFIXES, ('Unexpected presentation artifact', path)
            members.append(path)
    return sorted(members), sorted(skipped, key=lambda item: item['path'])


def check_audit_inputs(audit, root=ROOT):
    """Bind a completed numerical audit to the exact inputs being sealed."""
    hashes = audit['input_hashes']
    assert isinstance(hashes, dict) and hashes, 'Audit must pin every checked input'
    for name, expected in hashes.items():
        safe_name(name)
        assert isinstance(expected, str) and len(expected) == 64
        assert digest(root / name) == expected, ('Input changed after independent audit', name)


def complete_audit(data):
    path = data / 'verification.json'
    audit = json.loads(path.read_text())
    assert audit['all_requested_stages_verified'], 'Complete all independent audit stages before sealing'
    assert set(audit['stages']) == set(STAGES), ('Incomplete audit stage coverage', audit['stages'].keys())
    for stage, (field, expected) in STAGES.items():
        result = audit['stages'][stage]
        assert result['status'] == 'VERIFIED' and result[field] == expected, (stage, result)
    assert audit['stages']['training']['shadow_steps'] == 49152
    assert audit['verifier_sha256'] == digest(Path(__file__).parent / 'verify.py'), 'Audit code changed after verification'
    check_audit_inputs(audit)
    return dict(path=str(path.relative_to(ROOT)), sha256=digest(path), stages=audit['stages'],
                input_hashes=audit['input_hashes'], verifier_sha256=audit['verifier_sha256'],
                all_requested_stages_verified=audit['all_requested_stages_verified'])


def snapshot(data):
    """Pin the final technical source and all v9 execution/failed-attempt logs."""
    logs = data / 'execution-logs'
    logs.mkdir(exist_ok=True)
    for source in sorted(Path('/workspace/cloud-setup').glob('*v9*.log')):
        if 'package' not in source.name:
            shutil.copyfile(source, logs / source.name)
    source_root = data / 'final-source'
    source_root.mkdir(exist_ok=False)
    source_files = sorted([*Path(__file__).parent.glob('*.py'), *Path(__file__).parent.glob('*.md'),
                           *Path(__file__).parent.joinpath('references').glob('*'), ROOT / 'README.md'])
    for source in source_files:
        assert source.is_file() and not source.is_symlink(), source
        target = source_root / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    info = dict(python=platform.python_version(), versions={name: version(name) for name in
        ['numpy', 'scipy', 'numba', 'llvmlite', 'osqp', 'clarabel', 'torch', 'stable-baselines3', 'gymnasium']},
        analysis_source_hashes={str(path.relative_to(ROOT)): digest(path) for path in source_files},
        scope='576 calibration, 448 geometric calibration, 49152 continuation and shadow steps, '
              '2416 frozen comparison episodes, 20 actual-worker checks, 16 native transfer episodes; '
              'all recorded logging failures and native technical smokes retained.',
        exclusions='Generated bytecode/JIT caches and symlinks only; symlink metadata is retained in SEAL.json. '
                   'Presentation artifacts are not generated or accepted; packaging output logs are excluded to avoid self-reference.')
    write_json(data / 'execution_manifest.json', info)


def seal(data, out, root, audit, raw_budget=RAW_BUDGET, chunk_bytes=CHUNK_BYTES):
    """Byte-based partitioning bounds each ZIP without selecting experimental rows."""
    assert 0 < chunk_bytes < raw_budget <= RAW_BUDGET
    paths, skipped = inventory(data, root)
    assert paths, 'No evidence files'
    out.mkdir(parents=True, exist_ok=False)
    sources = {safe_name(str(path.relative_to(root))): dict(size=path.stat().st_size,
                sha256=digest(path), pieces=[]) for path in paths}
    # Some inputs (historical policy bundles and shared code) live outside this
    # dataset. Recheck those too; all archived inputs must match the audit hash.
    check_audit_inputs(audit, root)
    for name, expected in audit['input_hashes'].items():
        if name in sources:
            assert sources[name]['sha256'] == expected, ('Archived input differs from audited input', name)
    assert sources[audit['path']]['sha256'] == audit['sha256'], 'Archived audit differs from checked report'
    archives = []
    current = None
    current_path = None
    current_members = None
    budget = 0

    def close_archive():
        nonlocal current, current_path, current_members, budget
        if current is None:
            return
        current.writestr('EVIDENCE_MANIFEST.json', json.dumps(dict(version=2, files=current_members),
                         sort_keys=True, indent=2) + '\n')
        current.close()
        target = current_path.with_suffix('')
        current_path.rename(target)
        assert target.stat().st_size < MAX_ARCHIVE_BYTES, ('Archive exceeds strict 50 MiB cap', target)
        archives.append(dict(name=target.name, size=target.stat().st_size, sha256=digest(target),
                             members=len(current_members)))
        print(target.name, len(current_members), 'members', round(target.stat().st_size / 1024 ** 2, 3), 'MiB', flush=True)
        current = None
        current_members = None
        budget = 0

    try:
        for source_index, path in enumerate(paths):
            source_name = str(path.relative_to(root))
            record = sources[source_name]
            source_digest = hashlib.sha256()
            consumed = 0
            count = max(1, (record['size'] + chunk_bytes - 1) // chunk_bytes)
            with path.open('rb') as stream:
                for piece_index in range(count):
                    content = stream.read(chunk_bytes)
                    member = source_name if count == 1 else f'_chunks/{source_index:08d}/{piece_index:06d}'
                    estimated = len(content) + 1024 + 3 * len(member.encode()) + 5 * (len(content) // 16384 + 1)
                    assert estimated < raw_budget, ('Choose a smaller chunk size', member)
                    if current is not None and budget + estimated > raw_budget:
                        close_archive()
                    if current is None:
                        name = f'raw-evidence-{len(archives) + 1:03d}.zip'
                        current_path = out / (name + '.partial')
                        current = zipfile.ZipFile(current_path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6)
                        current_members = {}
                    piece = dict(source=source_name, offset=consumed, size=len(content),
                                 sha256=hashlib.sha256(content).hexdigest())
                    assert member not in current_members
                    current.writestr(member, content)
                    current_members[member] = piece
                    record['pieces'].append(dict(archive=current_path.with_suffix('').name, member=member, **piece))
                    source_digest.update(content)
                    consumed += len(content)
                    budget += estimated
                assert not stream.read(1), ('Source grew during sealing', path)
            assert consumed == record['size'] and source_digest.hexdigest() == record['sha256'], ('Source changed during sealing', path)
        close_archive()
    finally:
        if current is not None:
            current.close()
    check_audit_inputs(audit, root)
    manifest = dict(version=2, archive_limit_bytes=MAX_ARCHIVE_BYTES, raw_budget=raw_budget,
                    chunk_bytes=chunk_bytes, independent_audit=audit, archives=archives,
                    files=sources, skipped=skipped,
                    reconstruction='Concatenate each source file pieces in listed offset order. '
                                   'All byte counts, piece SHA256, reconstructed source SHA256 and ZIP CRCs are checked.')
    write_json(out / 'SEAL.json', manifest)
    sums = [record['sha256'] + '  ' + record['name'] for record in archives]
    sums.append(digest(out / 'SEAL.json') + '  SEAL.json')
    (out / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')
    return verify(out)


def verify(out=OUT):
    """Verify sealed evidence without the working raw directory or installed ML stack."""
    out = Path(out)
    sums = {}
    for line in (out / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        assert safe_name(name) == Path(name).name and name not in sums
        assert len(expected) == 64 and all(ch in '0123456789abcdef' for ch in expected)
        assert digest(out / name) == expected, ('Outer SHA256 mismatch', name)
        sums[name] = expected
    manifest = json.loads((out / 'SEAL.json').read_text())
    assert manifest['version'] == 2 and manifest['archive_limit_bytes'] == MAX_ARCHIVE_BYTES
    expected_archives = {entry['name']: entry for entry in manifest['archives']}
    assert len(expected_archives) == len(manifest['archives']) and expected_archives
    assert set(sums) == set(expected_archives) | {'SEAL.json'}
    assert {p.name for p in out.iterdir()} == set(sums) | {'SHA256SUMS'}, 'Unexpected or incomplete sealed output'
    expected_pieces = {}
    for source, record in manifest['files'].items():
        safe_name(source)
        cursor = 0
        assert record['pieces'], source
        for piece in record['pieces']:
            key = (safe_name(piece['archive']), safe_name(piece['member']))
            assert key not in expected_pieces and key[0] in expected_archives
            assert piece['source'] == source and piece['offset'] == cursor and piece['size'] >= 0
            cursor += piece['size']
            expected_pieces[key] = {k: piece[k] for k in ('source', 'offset', 'size', 'sha256')}
        assert cursor == record['size'], ('Noncontiguous source pieces', source)
    verified = {}
    for name, entry in expected_archives.items():
        target = out / name
        assert entry['sha256'] == sums[name] and entry['size'] == target.stat().st_size < MAX_ARCHIVE_BYTES
        with zipfile.ZipFile(target) as archive:
            names = archive.namelist()
            assert len(names) == len(set(names)), ('Duplicate ZIP member', name)
            assert archive.testzip() is None, ('ZIP CRC mismatch', name)
            contents = json.loads(archive.read('EVIDENCE_MANIFEST.json'))
            assert contents['version'] == 2
            members = contents['files']
            assert set(names) == set(members) | {'EVIDENCE_MANIFEST.json'}
            assert len(members) == entry['members']
            for member, record in members.items():
                safe_name(member)
                key = (name, member)
                assert key in expected_pieces and record == expected_pieces[key]
                hasher = hashlib.sha256()
                length = 0
                with archive.open(member) as stream:
                    for block in iter(lambda: stream.read(1024 ** 2), b''):
                        hasher.update(block)
                        length += len(block)
                assert length == record['size'] and hasher.hexdigest() == record['sha256'], ('Member hash/size mismatch', key)
                verified[key] = record
        print(name, 'outer SHA256,', len(members), 'member hashes/sizes and ZIP CRCs PASS', flush=True)
    assert verified == expected_pieces
    # Single-piece files need no second read. Large traces are independently
    # reassembled as a stream so loss, repetition and reordering cannot pass.
    for source, record in manifest['files'].items():
        pieces = record['pieces']
        if len(pieces) == 1:
            assert pieces[0]['sha256'] == record['sha256']
            continue
        hasher = hashlib.sha256()
        for piece in pieces:
            with zipfile.ZipFile(out / piece['archive']) as archive, archive.open(piece['member']) as stream:
                for block in iter(lambda: stream.read(1024 ** 2), b''):
                    hasher.update(block)
        assert hasher.hexdigest() == record['sha256'], ('Reassembled source SHA256 mismatch', source)
    audit = manifest['independent_audit']
    audit_path = safe_name(audit['path'])
    assert audit_path in manifest['files']
    assert manifest['files'][audit_path]['sha256'] == audit['sha256'], 'Audit report is not bound to archived bytes'
    archived_audit = json.loads(b''.join(source_blocks(out, manifest['files'][audit_path])))
    for field in ('stages', 'input_hashes', 'verifier_sha256', 'all_requested_stages_verified'):
        assert archived_audit[field] == audit[field], ('Audit metadata differs from archived report', field)
    assert isinstance(audit['input_hashes'], dict) and audit['input_hashes']
    for name, expected in audit['input_hashes'].items():
        safe_name(name)
        if name in manifest['files']:
            assert manifest['files'][name]['sha256'] == expected, ('Sealed input differs from audited input', name)
    result = dict(archives=len(expected_archives), source_files=len(manifest['files']),
                  zip_members=len(verified), source_bytes=sum(r['size'] for r in manifest['files'].values()),
                  all_outer_member_crc_and_reconstructed_hashes_verified=True)
    print('SEALED EVIDENCE VERIFIED', json.dumps(result, sort_keys=True), flush=True)
    return result


def source_blocks(out, record):
    """Read ordered source pieces; callers first verify the complete seal."""
    cursor = 0
    for piece in record['pieces']:
        assert piece['offset'] == cursor
        length = 0
        with zipfile.ZipFile(Path(out) / piece['archive']) as archive, archive.open(piece['member']) as stream:
            for block in iter(lambda: stream.read(1024 ** 2), b''):
                length += len(block)
                yield block
        assert length == piece['size']
        cursor += length
    assert cursor == record['size']


def _restore_path(root, source):
    """Refuse every symlink, collision and non-directory parent before writing."""
    safe_name(source)
    target = root / source
    assert target.is_relative_to(root), ('Restore path escapes target', source)
    for parent in (root, *root.parents, *target.parents):
        assert not parent.is_symlink(), ('Restore cannot follow a symlink', parent)
        if parent.exists():
            assert parent.is_dir(), ('Restore parent is not a directory', parent)
    assert not target.exists() and not target.is_symlink(), ('Preserve existing destination', target)
    return target


def restore(out, destination):
    """Reconstruct all original files after complete byte/audit verification."""
    verify(out)
    out = Path(out)
    manifest = json.loads((out / 'SEAL.json').read_text())
    root = Path(destination).absolute()
    # Check all destinations before creating even the first output file. Existing
    # unrelated files are allowed; existing evidence files are never overwritten.
    destinations = {source: _restore_path(root, source) for source in manifest['files']}
    total = 0
    for source, record in manifest['files'].items():
        target = _restore_path(root, source)
        assert target == destinations[source]
        target.parent.mkdir(parents=True, exist_ok=True)
        # Recheck after directory creation; exclusive creation also refuses a
        # file or symlink appearing at the destination during reconstruction.
        _restore_path(root, source)
        hasher = hashlib.sha256()
        count = 0
        with target.open('xb') as stream:
            for block in source_blocks(out, record):
                stream.write(block)
                hasher.update(block)
                count += len(block)
        assert count == record['size'] and hasher.hexdigest() == record['sha256'], ('Restored source mismatch', source)
        total += count
    result = dict(destination=str(root), files=len(destinations), bytes=total,
                  skipped_symlinks_recreated=False, all_reconstructed_hashes_verified=True)
    print('EVIDENCE RESTORED', json.dumps(result, sort_keys=True), flush=True)
    return result


def self_test():
    """Exercise chunking, empty files, symlink exclusion and tamper detection."""
    with tempfile.TemporaryDirectory(prefix='publication-v9-package-') as name:
        root = Path(name)
        data = root / 'data'
        data.mkdir()
        (data / 'empty.jsonl').write_bytes(b'')
        (data / 'small.json').write_bytes(b'{"raw": true}\n')
        (data / 'large.jsonl').write_bytes(bytes(range(256)) * 40)
        (data / 'external').symlink_to(root, target_is_directory=True)
        audit_record = dict(stages={}, input_hashes={'data/large.jsonl': digest(data / 'large.jsonl')},
                            verifier_sha256='0' * 64, all_requested_stages_verified=False,
                            role='synthetic_byte_seal_self_test')
        write_json(data / 'verification.json', audit_record)
        audit = dict(path='data/verification.json', sha256=digest(data / 'verification.json'),
                     **{field: audit_record[field] for field in ('stages', 'input_hashes',
                         'verifier_sha256', 'all_requested_stages_verified')})
        out = root / 'sealed'
        result = seal(data, out, root, audit, raw_budget=8192, chunk_bytes=2048)
        assert result['source_files'] == 4 and result['zip_members'] == 8 and result['archives'] > 1
        manifest = json.loads((out / 'SEAL.json').read_text())
        assert manifest['skipped'][0]['reason'] == 'symlink_not_followed'
        destination = root / 'restored'
        restored = restore(out, destination)
        assert restored['files'] == 4
        for source in manifest['files']:
            assert (destination / source).read_bytes() == (root / source).read_bytes()
        assert not (destination / 'data/external').exists()
        try:
            restore(out, destination)
        except AssertionError as exc:
            assert 'Preserve existing destination' in str(exc), exc
        else:
            raise AssertionError('Restore overwrote existing evidence')
        symlink_destination = root / 'restore-link'
        symlink_destination.symlink_to(destination, target_is_directory=True)
        try:
            restore(out, symlink_destination)
        except AssertionError as exc:
            assert 'symlink' in str(exc), exc
        else:
            raise AssertionError('Restore followed a destination symlink')
        for invalid in ('../outside.json', '/absolute.json', '.'):
            try:
                _restore_path(destination, invalid)
            except AssertionError:
                pass
            else:
                raise AssertionError(('Unsafe restoration path accepted', invalid))
        original = (data / 'large.jsonl').read_bytes()
        (data / 'large.jsonl').write_bytes(original + b'changed after audit')
        try:
            check_audit_inputs(audit, root)
        except AssertionError as exc:
            assert 'Input changed after independent audit' in str(exc), exc
        else:
            raise AssertionError('Changed audited input was accepted')
        (data / 'large.jsonl').write_bytes(original)
        # A valid outer checksum is insufficient if the seal claims a different
        # audit result than the report actually stored in the archives.
        manifest['independent_audit']['stages'] = {'invented': {'status': 'VERIFIED'}}
        write_json(out / 'SEAL.json', manifest)
        lines = (out / 'SHA256SUMS').read_text().splitlines()
        lines[-1] = digest(out / 'SEAL.json') + '  SEAL.json'
        (out / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')
        try:
            verify(out)
        except AssertionError as exc:
            assert 'Audit metadata differs from archived report' in str(exc), exc
        else:
            raise AssertionError('Invented archived audit metadata was accepted')
        manifest['independent_audit']['stages'] = {}
        # Recompute the outer seal checksum after corrupting the inner source
        # digest: verification must still reject the false reconstruction claim.
        manifest['files']['data/large.jsonl']['sha256'] = '0' * 64
        write_json(out / 'SEAL.json', manifest)
        lines = (out / 'SHA256SUMS').read_text().splitlines()
        lines[-1] = digest(out / 'SEAL.json') + '  SEAL.json'
        (out / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')
        try:
            verify(out)
        except AssertionError as exc:
            assert 'Reassembled source' in str(exc), exc
        else:
            raise AssertionError('Corrupted reconstruction manifest was accepted')
    print('PACKAGE SELF TEST PASS: reconstruction, empty files, audit binding, collision/symlink refusal and tamper rejection', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--verify', action='store_true')
    action.add_argument('--self-test', action='store_true')
    action.add_argument('--restore', type=Path, metavar='TARGET', help='Verify then reconstruct original files under TARGET; refuse overwrites and symlinks.')
    parser.add_argument('--evidence', type=Path, default=OUT, help='Sealed archive directory; raw inputs remain the fixed v9 dataset.')
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif args.verify:
        verify(args.evidence)
    elif args.restore is not None:
        restore(args.evidence, args.restore)
    else:
        assert not args.evidence.exists(), ('Preserve existing sealed/partial output', args.evidence)
        audit = complete_audit(DATA)
        snapshot(DATA)
        seal(DATA, args.evidence, ROOT, audit)


if __name__ == '__main__':
    main()
