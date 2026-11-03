from dataclasses import asdict
import json
import numpy as np
import pytest
from integrations.connected_v2v import V2VEndpoint, Beacon, encode_beacon
from integrations.connected_v2v.recovery.controller import RangeObservation
from integrations.connected_v2v.recovery import study as v2_study, verify as v2_verify
from .controller import FormationFollower, following_for
from .adapter import configured
from .metrics import settling, compute


def test_nominal_analytical_poles_and_discrete_sampled_poles():
    config=following_for('damped',12.)
    poles=np.roots([1.,config.time_headway_s*config.position_gain+config.velocity_gain,config.position_gain])
    np.testing.assert_allclose(poles,[-.8,-.8],atol=2e-8,rtol=0)
    d=.05;h=config.time_headway_s;kp=config.position_gain;kv=config.velocity_gain
    matrix=np.array([[1-(h*d+.5*d*d)*kp,d-(h*d+.5*d*d)*kv],[-d*kp,1-d*kv]])
    assert np.max(np.abs(np.linalg.eigvals(matrix))) < 1.


@pytest.mark.parametrize('variant',['baseline','damped'])
def test_blind_braking_and_source_ttl_are_unchanged(variant):
    node=V2VEndpoint('follower');node.observe_local([0.,0.,0.,12.,0.,0.],0.,0.)
    control=FormationFollower(node,'leader',method=variant)
    assert control.decide(0.)[0].accel==-6.
    observation=RangeObservation('leader',0,0.,(0.,0.,0.,12.,0.,0.),20.4,0.)
    control.observe_radar(observation,0.)
    assert control.decide(0.)[1]['sensor_source']=='radar'
    node.observe_local([0.,0.,0.,12.,0.,0.],.25,.25)
    command,info=control.decide(.25)
    assert command.accel==-6. and info['sensor_source']=='none'


def test_speed_envelope_cannot_expand_authority_or_reduce_emergency_braking():
    node=V2VEndpoint('follower');node.observe_local([0.,0.,0.,19.99,0.,0.],0.,0.)
    node.receive(encode_beacon(Beacon('leader',0,0.,(100.,0.,0.,25.,0.,0.))),0.)
    control=FormationFollower(node,'leader')
    command,info=control.decide(0.)
    assert command.accel==pytest.approx(.2) and info['speed_envelope_active']
    node.observe_local([0.,0.,0.,20.,0.,0.],.5,.5)
    assert control.decide(.5)[0].accel==-6.


def test_handover_preserves_analytical_settings_and_previous_command():
    node=V2VEndpoint('follower');control=FormationFollower(node,'leader')
    node.observe_local([0.,0.,0.,12.,0.,0.],0.,0.);control.decide(0.)
    before=control.base.previous;control.retarget('cut-in')
    assert control.base.previous==before and control.base.following==following_for('damped',12.)


def test_scoped_adapter_restores_frozen_v2_modules_even_after_exception():
    old=v2_study.FusionFollower,v2_study.FollowingConfig,v2_verify.FusionFollower
    with pytest.raises(RuntimeError):
        with configured('damped'):
            assert v2_study.FusionFollower is FormationFollower
            raise RuntimeError('test failure')
    assert old==(v2_study.FusionFollower,v2_study.FollowingConfig,v2_verify.FusionFollower)


def test_settling_is_censored_without_two_seconds_or_after_a_late_violation():
    assert settling([(1.,True),(2.,True)],0.,2.)['censored']
    assert settling([(1.,False),(2.,True),(3.,True),(4.,True)],0.,4.)==dict(duration_s=2.,censored=False)
    assert settling([(1.,True),(2.,True),(3.,False),(4.,True)],0.,4.)['censored']


@pytest.mark.parametrize('variant',['baseline','damped'])
def test_closed_loop_variant_replay_uses_true_declared_gains(tmp_path,variant):
    path=tmp_path/variant
    with configured(variant):
        summary=v2_study.run_episode(path,'nominal',variant,12.,42,seconds=4.)
        assert v2_verify.replay(path)['passed']
    case=json.loads((path/'case.json').read_text())
    assert case['following']==asdict(following_for(variant,12.))
    metrics=compute(path)
    assert metrics['vehicle_ticks']==240 and metrics['blind_brake_violations']==0
    assert metrics['actuator_violations']==0 and metrics['speed_violations']==0


def test_gate_rejects_censoring_progress_loss_or_one_safety_failure():
    from .campaign import assess, PROTOCOL
    rows=[]
    for seed in [1,2,3]:
        for speed in [8.,12.,16.]:
            for scenario in PROTOCOL['scenarios']:
                for variant in ['baseline','damped']:
                    row=dict(seed=seed,speed=speed,scenario=scenario,variant=variant,
                        first20_spacing_rms_m=1.,jerk_rms_m_s3=1.,
                        first20_progress_m={'follower-1':100.,'follower-2':100.},
                        progress_m={'follower-1':150.,'follower-2':150.},settling={})
                    for name in ['collision_pair_ticks','corridor_ticks','stale_source_ticks',
                                 'blind_brake_violations','actuator_violations','speed_violations']:row[name]=0
                    event='dual' if scenario=='dual_blackout' else 'cut_out'
                    if scenario in ('dual_blackout','cut_in'):
                        row['settling'][event]=dict(duration_s=10. if variant=='baseline' else 6.,censored=False)
                    rows.append(row)
    assert assess(rows)['passed']
    target=next(r for r in rows if r['variant']=='damped' and r['scenario']=='dual_blackout')
    target['settling']['dual']['censored']=True
    assert not assess(rows)['passed'];target['settling']['dual']['censored']=False
    target['blind_brake_violations']=1
    assert not assess(rows)['passed'];target['blind_brake_violations']=0
    target['first20_progress_m']['follower-1']=98.
    assert not assess(rows)['passed']
