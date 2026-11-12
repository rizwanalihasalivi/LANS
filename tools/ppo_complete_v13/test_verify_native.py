"""Geometry/initialization counterexamples for the native record auditor."""
import copy
import json
from pathlib import Path
import math

import numpy as np
import pytest

from .verify_native import ROOT,check_initialization,check_timing,physical_interval,pose_metrics,route_geometry,verify


def straight_case():
    return dict(id=0,route_kind='straight',phase=0.,mirror=1,amplitude=1.,
        initial_ego=[0.,0.,0.,20.,0.,0.],initial_npcs={'cross':[.5,4.59,0.,0.,0.,0.]})


def tangent_crossing_interval():
    """Both50ms endpoints clear; an intermediate native sample collides."""
    case=straight_case();traffic=case['initial_npcs'];samples=[]
    for i in range(50):
        t=(i+1)*.001;ego=[20*t,0.,0.,20.,0.,0.];m=pose_metrics(case,ego,traffic)
        samples.append(dict(substep=i,simulation_time_s=10.+t,state=ego,traffic=traffic,
            clearance=m['clearance'],error=0.,equivalent_bicycle_steering=0.,
            measured_steering_rate=0.,actuator_target=0.,actuator_target_rate=0.,
            measured_speed_m_s=20.,achieved_accel_m_s2=0.,requested_accel=0.,
            bounded_requested_accel=0.,actuation_method='torque_pi',engine_model_used=True,
            throttle=0.,brake_intensity=0.))
    row=dict(state_before=case['initial_ego'],npc_truth_before=traffic,physics=samples,time_s=0.,
        applied_steering=0.,applied_accel=0.,state_after=samples[-1]['state'],npc_truth=traffic,
        error=0.,native_error=0.,heading_error=0.,true_clearance=-.01,max_interval_error=0.,
        collision=True,corridor_exceeded=False,measured_equivalent_steering=0.,
        measured_steering_rate_max=0.,measured_steering_rate_rms=0.,actual_accel_mean=0.)
    return case,row


def test_intersample_circle_collision_cannot_be_hidden_by_safe_endpoints():
    case,row=tangent_crossing_interval()
    assert pose_metrics(case,row['state_before'],row['npc_truth_before'])['collision'] is False
    assert pose_metrics(case,row['state_after'],row['npc_truth'])['collision'] is False
    result=physical_interval(case,row,case['initial_ego'],case['initial_npcs'],0.,0.,10.)
    assert len(result['rates'])==50
    row['collision']=False
    with pytest.raises(AssertionError,match='intersample native safety'):
        physical_interval(case,row,case['initial_ego'],case['initial_npcs'],0.,0.,10.)


def test_physical_steering_rate_must_come_from_measured_wheel_motion():
    case,row=tangent_crossing_interval();row['physics'][20]['equivalent_bicycle_steering']=.001
    with pytest.raises(AssertionError,match='actual measured steering derivative'):
        physical_interval(case,row,case['initial_ego'],case['initial_npcs'],0.,0.,10.)


def test_mirrored_scaled_route_heading_uses_scaled_derivative():
    case=dict(route_kind='sine',phase=12.,mirror=-1,amplitude=1.3)
    y,h=route_geometry(case,0.)
    assert y==pytest.approx(-1.3*1.5*math.sin(2*math.pi/120*12.))
    assert h==pytest.approx(math.atan(-1.3*1.5*2*math.pi/120*math.cos(2*math.pi/120*12.)))


def test_stale_supervisor_traffic_sensor_rejected_before_other_contract_checks():
    case=straight_case()
    init=dict(initial_traffic={'cross':[100.,100.,0.,0.,0.,0.]})
    with pytest.raises(AssertionError,match='unsynchronized initial native traffic'):
        check_initialization(case,init)


def test_no_teleport_initialization_and_speed_fidelity_are_separate_from_raw_validity():
    case=straight_case();case['scene_calibration']='/synthetic/policy-free-calibration'
    actual=copy.deepcopy(case['initial_npcs']);actual['cross'][3]=.2
    init=dict(initial_traffic=actual,initial_ego=case['initial_ego'],
        ego_pose_overwritten=False,npc_pose_overwritten_during_measurement=False,
        ego_python_integrated=False,npc_python_integrated=False,
        npc_pose_initializations={'cross':0},frame={'physical_pose_changed':False},
        initial_equivalent_bicycle_steering=0.)
    result=check_initialization(case,init)
    assert result['npc_pose_initializations']==0
    assert result['all_initial_speeds_within_01_m_s'] is False
    assert result['maximum_absolute_speed_error_m_s']==pytest.approx(.2)
    init['npc_pose_initializations']['cross']=1
    with pytest.raises(AssertionError):check_initialization(case,init)


def test_recorded_native_v1_stale_initialization_is_not_qualified_evidence():
    folder=ROOT/'results/ppo-complete-v13/native-opened53-adaptive-v1'
    if not folder.exists():pytest.skip('retained historical native development attempt is absent')
    with pytest.raises(AssertionError,match='unsynchronized initial native traffic'):
        verify(folder)


class ConstantPolicy:
    def predict(self,observation,deterministic):return np.full(8,.1),None


def selected_timing_row():
    source=100.001;issue=100.01;action=[.1]*8
    reply=dict(wall_observed=source,observed_s=0.,sequence=1,wall_submitted=100.002,
        worker_started_wall=100.003,worker_finished_wall=100.004,action=action)
    row=dict(owner_release_wall=100.,owner_deadline_wall=100.05,owner_issued_wall=issue,
        complete_decision_ms=1000*(issue-100.),cycle_ms=20.,owner_response_miss=False,
        scheduled_release_wall=100.,scheduled_owner_response_ms=1000*(issue-100.),scheduled_owner_response_miss=False,
        original_frame_wall=source,source_ego_sequence=1,tick=0,source_ego_observed_s=0.,time_s=0.,
        runtime_reply=reply,reply_sequence=1,runtime_observation=[0.]*55,runtime_action=action,
        proposal_wall_age_at_issue=issue+.1-source,proposal_logical_age_at_issue=.1,
        runtime_selected=True,sequence_plan_selected=True,source='ppo_anchor',runtime_postcheck_fallback=False,
        projection_scale=.5,applied_score_values=[[1.,.5,.01,.01]]*3,
        lqr_model_values=[[1.3,.5,.01,.01]]*3,anchor_model_values=[[1.2,.5,.01,.01]]*3,
        sequence_cost=1.,anchor_reference_cost=1.2)
    return dict(network='nominal',delay=.1),row


def test_selected_native_guard_values_and_original_wall_age_are_checked():
    case,row=selected_timing_row();check_timing(row,case,ConstantPolicy())
    row['applied_score_values'][1]=[1.,.5,.1,.01]
    with pytest.raises(AssertionError,match='all-model original heading gate'):
        check_timing(row,case,ConstantPolicy())
    case,row=selected_timing_row();case['network']='ego_blackout'
    row['original_frame_wall']=99.9;row['runtime_reply']['wall_observed']=99.9
    row['proposal_wall_age_at_issue']=row['owner_issued_wall']+.1-99.9
    with pytest.raises(AssertionError):check_timing(row,case,ConstantPolicy())


def test_recorded_no_teleport_native_scene_and_physics():
    folder=ROOT/'results/ppo-complete-v13/native-opened53-adaptive-v4'
    if not folder.exists():pytest.skip('retained development native run is absent')
    result=verify(folder)
    assert result['verified'] and result['raw_physics_steps']==6000 and result['ticks']==120
    assert result['scene_calibration']['verified']
    assert result['initial_state_fidelity']['npc_pose_initializations']==0
    assert result['initial_state_fidelity']['all_initial_speeds_within_01_m_s']
    assert result['qualification'] is False and result['timing_gate_passed'] is False
