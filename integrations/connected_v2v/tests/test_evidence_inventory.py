"""The evidence verifier must not turn absent/incomplete archives into a pass."""
import hashlib
import json
import zipfile

import pytest

from integrations.connected_v2v.settling.package import verify


def archive(root, name='evidence.zip', *, duplicate=False, empty=False):
    data = b'original evidence bytes\n'
    manifest = {} if empty else {'results/run/data.txt': dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())}
    path = root / name
    with zipfile.ZipFile(path, 'w') as z:
        if not empty:
            z.writestr('results/run/data.txt', data)
            if duplicate:
                with pytest.warns(UserWarning, match='Duplicate name'):
                    z.writestr('results/run/data.txt', data)
        z.writestr('MEMBER-SHA256.json', json.dumps(manifest))
    return dict(archive=name, bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), members=len(manifest))


def inventory(root, entries, listed=None):
    (root / 'inventory.json').write_text(json.dumps(entries))
    (root / 'SHA256SUMS').write_text(''.join(f"{r['sha256']}  {r['archive']}\n" for r in (entries if listed is None else listed)))


def test_empty_evidence_is_not_a_success(tmp_path):
    inventory(tmp_path, [])
    with pytest.raises(ValueError):
        verify(tmp_path)


def test_checksum_file_cannot_silently_omit_a_declared_archive(tmp_path):
    entries = [archive(tmp_path, name) for name in ('one.zip', 'two.zip')]
    inventory(tmp_path, entries, entries[:1])
    with pytest.raises(ValueError):
        verify(tmp_path)


def test_duplicate_zip_member_cannot_hide_behind_a_set_comparison(tmp_path):
    inventory(tmp_path, [archive(tmp_path, duplicate=True)])
    with pytest.raises(ValueError):
        verify(tmp_path)


def test_archive_without_evidence_members_is_not_a_success(tmp_path):
    inventory(tmp_path, [archive(tmp_path, empty=True)])
    with pytest.raises(ValueError):
        verify(tmp_path)


def test_inventory_metadata_must_agree_with_actual_archive(tmp_path):
    entry = archive(tmp_path)
    inventory(tmp_path, [dict(entry, bytes=entry['bytes'] + 1)])
    with pytest.raises(ValueError):
        verify(tmp_path)


def test_valid_archive_verifies_and_extracts_exact_bytes(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    inventory(source, [archive(source)])
    out = tmp_path / 'extracted'
    result = verify(source, out)
    assert result == dict(passed=True, archives=1, ordinary_members=1)
    assert (out / 'results/run/data.txt').read_bytes() == b'original evidence bytes\n'
