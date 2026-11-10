"""Default pytest collection must not create an unloadable JIT cache alias."""
from . import recovery,traffic_guard


def test_cli_and_default_pytest_share_canonical_module_identity():
    assert recovery.__name__=='tools.v8_reliability.recovery'
    assert recovery.margins.py_func.__module__=='tools.v8_reliability.recovery'
    assert traffic_guard.__name__=='tools.v8_reliability.traffic_guard'
