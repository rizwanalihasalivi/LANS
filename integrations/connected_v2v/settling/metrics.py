"""Strict association/settling gates on complete long-horizon episodes."""
import math
from integrations.connected_v2v.robustness.metrics import measure as prior_measure


def measure(rows,road,speed,*,native=False):
    result=prior_measure(rows,road,speed,native=native)
    stable=0;longest=0;first_stable=None;tail_errors=[];tail_speeds=[];tail_correct=0
    settled_ticks=0;first_settled=None;tail_leader=[]
    exit_time=23. if native else 22.
    tail_start=rows[-1]['time_s']-5.+.05
    for row in rows:
        t=row['time_s'];info=row['decision'];ego=row['before']
        lead=row['traffic_before']['leader']
        gap=road.project(lead[:2])[0]-road.project(ego[:2])[0]-4.6
        fresh=info['sensor_source'] in ('radar','v2v') and info['target_gap_m'] is not None
        correct=fresh and abs(info['target_gap_m']-gap)<2. and info.get('selected_radio_id') in (None,'leader')
        if t>=exit_time:
            stable=stable+1 if correct else 0;longest=max(longest,stable)
            if stable>=40 and first_stable is None:first_stable=max(0.,t-exit_time-1.95)
            error=gap-6.-1.2*ego[3]
            settled_ticks=settled_ticks+1 if correct and abs(error)<=2. and abs(ego[3]-lead[3])<=.5 else 0
            if settled_ticks>=40 and first_settled is None:first_settled=max(0.,t-exit_time-1.95)
        if t>=tail_start-1e-8:
            tail_errors.append(gap-6.-1.2*ego[3]);tail_speeds.append(ego[3]-lead[3]);tail_correct+=bool(correct)
            tail_leader.append(lead[3]-speed)
    rms=math.sqrt(math.fsum(z*z for z in tail_errors)/len(tail_errors))
    maxerr=max(map(abs,tail_errors));speedrms=math.sqrt(math.fsum(z*z for z in tail_speeds)/len(tail_speeds))
    ratio=tail_correct/len(tail_errors)
    leader_rms=math.sqrt(math.fsum(z*z for z in tail_leader)/len(tail_leader))
    base=result['passed']
    result.update(original_gate_passed=base,stable_return_2s_s=first_stable,
        stable_return_censored=first_stable is None,longest_correct_run_s=longest*.05,
        tail_spacing_rms_m=rms,tail_spacing_max_abs_m=maxerr,tail_speed_rms_m_s=speedrms,
        tail_correct_fraction=ratio,tail_leader_cruise_rms_m_s=leader_rms,settling_delay_2s_s=first_settled)
    result['passed']=bool(base and first_stable is not None and first_settled is not None and
        exit_time+first_settled<=60. and rms<=2. and maxerr<=5. and speedrms<=.5 and leader_rms<=.5 and ratio>=.95 and
        result['progress_m']>.6*speed*len(rows)*.05)
    return result
