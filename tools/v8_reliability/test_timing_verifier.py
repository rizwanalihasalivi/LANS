import json
import pytest
from .verify import sha
from .verify_runtime import timing


@pytest.mark.parametrize('impossible',[False,True])
def test_non_atomic_clock_samples_preserve_real_misses(tmp_path,impossible):
    row=dict(tick=0,response_ms=31.,scheduled_response_ms=31.1,release_lateness_ms=1.)
    # Perf start, actual-release sample, response and end can be preempted
    # separately. A legitimate0.9ms sampling skew is not a clock contradiction.
    t=dict(tick=0,complete_cycle_ms=70. if impossible else 40.,scheduled_cycle_ms=31.5 if impossible else 40.1)
    p=tmp_path/'timing.jsonl';p.write_text(json.dumps(t)+'\n')
    s=dict(timing_sha256=sha(p),response_misses=0,cycle_misses=int(impossible),scheduled_response_misses=0,
        scheduled_cycle_misses=0,response_max_ms=31.,cycle_max_ms=t['complete_cycle_ms'])
    if impossible:
        with pytest.raises(AssertionError):timing(tmp_path,s,[row])
    else:assert timing(tmp_path,s,[row])==[t]
