from .timing import Schedule


def test_schedule_preserves_release_grid_after_an_overrun():
    class Clock:
        value=100.
        def now(self):return self.value
        def sleep(self,delay):self.value+=max(delay,.00005)
    c=Clock();s=Schedule(clock=c.now,sleep=c.sleep)
    s.wait(1);assert .05<=c.value-100.<.0501
    c.value=100.12
    assert s.wait(2)>=.01999
    assert s.target(3)==100.15
    s.wait(3);assert 100.15<=c.value<100.1501


def test_no_work_or_release_is_skipped_to_hide_a_miss():
    class Clock:
        def __init__(self):self.t=0.
        def now(self):return self.t
        def sleep(self,d):self.t+=max(d,.00001)
    c=Clock();s=Schedule(clock=c.now,sleep=c.sleep)
    measured=[]
    for tick,duration in enumerate((.07,.01,.01)):
        s.wait(tick);start=c.now();c.t+=duration
        measured.append(dict(tick=tick,release=start-s.target(tick),miss=c.now()>s.target(tick+1)))
    assert len(measured)==3 and measured[0]['miss'] and measured[1]['release']>0
