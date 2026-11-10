import numpy as np
import pytest
from integrations.unified_lans.physics import Config, Route, Command, constrain
from integrations.unified_lans.traffic import Packet
from tools.unified_control_v8.control import Controller as V8
from tools.unified_control_v9.learning import run_episode
from .control import Controller
from .regressions import CASES


@pytest.mark.parametrize('case', CASES, ids=lambda c:str(c['id']))
def test_shared_training_crossing_failure_and_new_recovery(case):
    original,_=run_episode(case,'lqr',grid=False,controller_factory=V8,
                           controller_kwargs=dict(adaptive=False,mpc=False))
    fixed,rows=run_episode(case,'lqr',grid=False,controller_factory=Controller,
                          controller_kwargs=dict(adaptive=False,mpc=False))
    assert original['failed'] and original['collisions']>0
    assert not fixed['failed'] and fixed['collisions']==0
    assert all(-6<=r['issued_accel']<=2.5 and abs(r['issued_steering'])<=.5 for r in rows)
    delay=round(case['delay']/.05)
    for i,row in enumerate(rows):
        expected=rows[i-delay] if i>=delay else {'issued_accel':0.,'issued_steering':0.}
        assert row['applied_accel']==expected['issued_accel']
        assert row['applied_steering']==expected['issued_steering']
        if row['recovery'] is not None and row['source']=='recovery_lqr':
            selected=row['recovery']['selected']
            assert selected['physical_margin']>0
            assert selected['margin']>=0 or row['recovery']['mode']=='uncertified_emergency_improvement'


def test_cached_cost_preserves_v8_values_and_does_not_alias_changed_state():
    cfg=Config(horizon=2.)
    c=Controller(Route('straight'),cfg=cfg,adaptive=False,mpc=False,recovery=False,penalty=16.)
    original=V8(Route('straight'),cfg=cfg,adaptive=False,mpc=False,penalty=16.)
    for y in (.3,.1):
        z=np.array([0.,y,.005,12.,0.,0.])
        for residual in np.linspace(-.08,.08,17):
            u=constrain(Command(c.baseline_fn(z,c.route)+residual,0.),Command(),cfg)
            a=c.cost(z,u,residual,0.,(),2.)
            assert a==original.cost(z,u,residual,0.,(),2.)
            assert c.cost(z,u,residual,0.,(),2.)==a
    assert c.cache_hits>0


@pytest.mark.parametrize('missing',['ego','traffic','stale_ego'])
def test_recovery_never_invents_missing_knowledge(missing):
    c=Controller(Route('straight'),penalty=16.,mpc=False)
    c.expected={'cross'}
    c.inbox.ingest(Packet('ego',0,0.,(0.,.1,0.,16.,0.,0.)),0.)
    c.inbox.ingest(Packet('cross',0,0.,(25.,-20.,np.pi/2,10.,0.,0.)),0.)
    now=0.
    if missing=='ego':c.inbox.latest.pop('ego')
    elif missing=='traffic':c.inbox.latest.pop('cross')
    else:now=.3
    result=c.decide(now)
    assert result['issued_accel']==-6. and result['recovery'] is None
