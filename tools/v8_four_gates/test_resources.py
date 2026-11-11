from types import SimpleNamespace
import pytest
from . import resources


def test_owned_affinity_restores_only_declared_processes_after_failure(monkeypatch):
    monkeypatch.setenv('LANS_RUNTIME_CPUS','24,25,26,27');monkeypatch.setattr(resources.os,'getpid',lambda:100)
    masks={100:{30,31},200:{32,33},300:{34,35}};original={p:set(m) for p,m in masks.items()};changes=[]
    monkeypatch.setattr(resources.os,'sched_getaffinity',lambda pid:set(masks[pid]))
    def setmask(pid,mask):masks[pid]=set(mask);changes.append((pid,set(mask)))
    monkeypatch.setattr(resources.os,'sched_setaffinity',setmask)
    workers=[SimpleNamespace(pid=p,is_alive=lambda:True) for p in (200,300)]
    with pytest.raises(RuntimeError,match='exercise cleanup'):
        with resources.owned_affinity(workers) as result:
            assert result['applied'] and masks=={100:{24},200:{26},300:{27}}
            raise RuntimeError('exercise cleanup')
    assert masks==original
    assert [p for p,_ in changes]==[100,200,300,300,200,100]


def test_duplicate_affinity_roles_are_rejected_before_changes(monkeypatch):
    monkeypatch.setenv('LANS_RUNTIME_CPUS','24,24,26,27')
    with pytest.raises(ValueError,match='distinct'):
        with resources.owned_affinity():pytest.fail('invalid affinity entered')
