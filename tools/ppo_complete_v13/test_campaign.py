"""Protect recorded timing missions and failed attempts during continuation."""
import json,subprocess
from types import SimpleNamespace
import pytest
from . import campaign


def test_resume_consumes_existing_mission_without_a_favorable_rerun(tmp_path,monkeypatch):
    root=tmp_path/'repo';root.mkdir();monkeypatch.setattr(campaign,'ROOT',root)
    finished={'runtime'};calls=[];remaining=iter(['native','qualify','audit','package'])
    monkeypatch.setattr(campaign,'completed',lambda stage:stage in finished)
    def execute(command,**kwargs):
        stage=next(remaining);calls.append(stage);finished.add(stage)
        module,*arguments=campaign.COMMANDS[stage]
        assert command[-(len(arguments)+1):]==['tools.ppo_complete_v13.'+module,*arguments]
        kwargs['stdout'].write('All recorded failures remain. Qualification may be false.\n')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(campaign.subprocess,'run',execute)
    campaign.run('runtime',resume=True)
    assert calls==['native','qualify','audit','package']
    records=[json.loads(l) for l in (tmp_path/'cloud-setup/ppo-complete-v13-pipeline-journal.jsonl').open()]
    assert [r['stage'] for r in records]==calls and all(r['returncode']==0 for r in records)


def test_failed_attempt_is_retained_and_not_automatically_retried(tmp_path,monkeypatch):
    root=tmp_path/'repo';root.mkdir();monkeypatch.setattr(campaign,'ROOT',root)
    monkeypatch.setattr(campaign,'completed',lambda stage:False);calls=[]
    def execute(command,**kwargs):
        calls.append(command);kwargs['stdout'].write('Original execution error retained\n')
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(campaign.subprocess,'run',execute)
    with pytest.raises(subprocess.CalledProcessError):campaign.run('native',resume=True)
    log=tmp_path/'cloud-setup/ppo-complete-v13-pipeline-native.log';original=log.read_bytes()
    with pytest.raises(RuntimeError,match='Prior native attempt retained'):
        campaign.run('native',resume=True)
    assert len(calls)==1 and log.read_bytes()==original
