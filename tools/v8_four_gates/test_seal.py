import hashlib,json,zipfile
import pytest
from . import seal


def fixture_bundle(folder):
    name='results/v8-four-gates/check/ticks.jsonl';data=b'{"tick":0}\n';p=folder/'raw-001.zip'
    with zipfile.ZipFile(p,'w') as z:z.writestr(name,data)
    manifest=dict(files={name:dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),archive=p.name)},archives={p.name:dict(bytes=p.stat().st_size,sha256=seal.sha(p))},raw_bytes=len(data))
    (folder/'manifest.json').write_text(json.dumps(manifest));return p,manifest


def test_seal_checks_exact_nonempty_archive_and_file_coverage(tmp_path,monkeypatch):
    monkeypatch.setattr(seal,'OUT',tmp_path);p,manifest=fixture_bundle(tmp_path)
    assert seal.verify()['files']==1
    p.unlink()
    with pytest.raises(AssertionError):seal.verify()


def test_empty_or_corrupted_evidence_cannot_pass(tmp_path,monkeypatch):
    monkeypatch.setattr(seal,'OUT',tmp_path);p,manifest=fixture_bundle(tmp_path)
    p.write_bytes(p.read_bytes()+b'corruption')
    with pytest.raises(AssertionError):seal.verify()
    p.unlink();(tmp_path/'manifest.json').write_text(json.dumps(dict(files={},archives={},raw_bytes=0)))
    with pytest.raises(AssertionError):seal.verify()
