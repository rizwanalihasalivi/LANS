"""Evidence sealing checks use temporary bytes, never research outcomes."""
import json
from pathlib import Path

import pytest

from . import package


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def completed_negative_audit(root):
    data = root/'results/ppo-complete-v13'
    verifier = root/'tools/ppo_complete_v13/verify.py'
    verifier.parent.mkdir(parents=True)
    verifier.write_text('# independently audited source\n')
    qualification = data/'completion/qualification.json'
    dump(qualification, dict(overall_qualified=False, overall_mean_target_qualified=False))
    stages = {name: dict(status='VERIFIED', **{field: count})
              for name, (field, count) in package.STAGES.items()}
    stages['training']['shadow_steps'] = 196608
    report = dict(passed=True, all_requested_stages_verified=True, stages=stages,
        required_checks={name: dict(status='VERIFIED') for name in
            ('focused_tests', 'actuator_calibration', 'completion_qualification_record')},
        verifier_sha256=package.digest(verifier), overall_qualified=False,
        overall_mean_target_qualified=False, all_training_controller_queries_replayed=False,
        input_hashes={str(verifier.relative_to(root)): package.digest(verifier),
            str(qualification.relative_to(root)): package.digest(qualification)})
    dump(data/'verification.json', report)
    return data, report


def test_complete_evidence_can_seal_an_honest_negative_performance_result(tmp_path):
    data, _ = completed_negative_audit(tmp_path)
    audit = package.complete_audit(data, tmp_path)
    assert audit['all_requested_stages_verified'] is True
    assert audit['overall_qualified'] is False
    assert audit['overall_mean_target_qualified'] is False
    assert audit['sha256'] == package.digest(data/'verification.json')


@pytest.mark.parametrize('stage', tuple(package.STAGES))
def test_missing_one_registered_stage_cannot_be_called_complete(tmp_path, stage):
    data, report = completed_negative_audit(tmp_path)
    report['stages'][stage]['status'] = 'MISSING'
    dump(data/'verification.json', report)
    with pytest.raises(AssertionError, match='Incomplete stage'):
        package.complete_audit(data, tmp_path)


def test_post_audit_qualification_tamper_is_rejected(tmp_path):
    data, _ = completed_negative_audit(tmp_path)
    dump(data/'completion/qualification.json', dict(overall_qualified=True,
        overall_mean_target_qualified=True))
    with pytest.raises(AssertionError, match='Input changed after independent audit'):
        package.complete_audit(data, tmp_path)


def test_log_versions_are_retained_without_changing_failed_attempt(tmp_path):
    source = tmp_path/'incoming.log'
    source.write_text('first attempt failed\n')
    target = tmp_path/'saved/run.log'
    first = package.retain_file(source, target)
    source.write_text('second attempt passed\n')
    second = package.retain_file(source, target)
    assert first != second
    assert first.read_text() == 'first attempt failed\n'
    assert second.read_text() == 'second attempt passed\n'
    assert package.retain_file(source, target) == second


def test_bounded_archives_restore_every_raw_byte_and_retain_negative_audit(tmp_path):
    data, _ = completed_negative_audit(tmp_path)
    raw = data/'long-raw.jsonl'
    content = (b'{"failed":true,"metric":12.345}\n'*6000)+b'final partial bytes'
    raw.write_bytes(content)
    audit = package.complete_audit(data, tmp_path)
    archives = tmp_path/'evidence'
    sealed = package.seal(data, archives, tmp_path, audit, raw_budget=65536, chunk_bytes=16384)
    assert sealed['all_outer_member_crc_and_reconstructed_hashes_verified']
    assert sealed['archives'] > 1
    manifest = json.loads((archives/'SEAL.json').read_text())
    assert manifest['independent_audit']['overall_qualified'] is False
    restored = tmp_path/'restored'
    package.restore(archives, restored)
    assert (restored/raw.relative_to(tmp_path)).read_bytes() == content
    with pytest.raises(AssertionError, match='Preserve existing destination'):
        package.restore(archives, restored)


def test_snapshot_preserves_failed_logs_and_refuses_replacing_frozen_source(tmp_path, monkeypatch):
    data, _ = completed_negative_audit(tmp_path)
    own = tmp_path/'tools/ppo_complete_v13'
    (own/'package.py').write_text('# package source\n')
    (own/'PROTOCOL.md').write_text('Frozen before outcomes.\n')
    native = own/'native_assets/driver.py'
    native.parent.mkdir()
    native.write_text('# native source\n')
    generic = tmp_path/'tools/unified_control_v9/package.py'
    generic.parent.mkdir()
    generic.write_text('# bounded generic archive source\n')
    logs = tmp_path/'logs'
    logs.mkdir()
    (logs/'ppo-complete-v13-failed.log').write_text('failure retained\n')
    (logs/'ppo-complete-v13-package.log').write_text('self-referential packaging output\n')
    monkeypatch.setattr(package, 'version', lambda name: 'test-only-version')
    package.snapshot(data, tmp_path, logs)
    assert (data/'execution-logs/ppo-complete-v13-failed.log').read_text() == 'failure retained\n'
    assert not (data/'execution-logs/ppo-complete-v13-package.log').exists()
    assert (data/'final-source/tools/ppo_complete_v13/native_assets/driver.py').read_bytes() == native.read_bytes()
    manifest = json.loads((data/'execution_manifest.json').read_text())
    assert manifest['retained_execution_logs']
    with pytest.raises(AssertionError, match='Preserve an existing final snapshot'):
        package.snapshot(data, tmp_path, logs)
