"""Standard-library-only recomputation; imports no controller/model/metric helper."""
import argparse
import json
import math
import statistics
from pathlib import Path


def independent_settling(flags,start,end):
    relevant=[(t,good) for t,good in flags if start<t<=end+1e-9]
    suffix=[False]*len(relevant);all_good=True
    for index in range(len(relevant)-1,-1,-1):
        all_good=all_good and relevant[index][1];suffix[index]=all_good
    for index,(time,_) in enumerate(relevant):
        if suffix[index] and end-time>=2.-1e-9:
            return dict(duration_s=max(0.,time-start),censored=False)
    return dict(duration_s=end-start,censored=True)


def check_case(folder,stored):
    folder=Path(folder);case=json.loads((folder/'case.json').read_text())
    frames=[json.loads(s) for s in (folder/'ticks.jsonl').read_text().splitlines()]
    targets={'follower-1':'leader','follower-2':'follower-1'}
    first=[];all_errors=[];jerks=[];gaps=[];flags=[]
    last_accel={key:0. for key in targets};last_steer=dict(last_accel)
    violations={key:0 for key in ['collision_pair_ticks','corridor_ticks','stale_source_ticks',
        'blind_brake_violations','actuator_violations','speed_violations']}
    peaks={name:0. for name in ('leader',*targets)}
    for row in frames:
        targets.update(row['membership']);good=True
        positions=list(row['after'].values())
        for index,a in enumerate(positions):
            for b in positions[index+1:]:violations['collision_pair_ticks']+=math.dist(a[:2],b[:2])<=4.6
        for name in peaks:
            speed=row['after'][name][3];peaks[name]=max(peaks[name],speed)
            violations['speed_violations']+=speed>case['speed']+(0 if name=='leader' else 8)+1e-8
        for name,target in targets.items():
            own=row['after'][name];front=row['after'][target]
            gap=front[0]-own[0]-4.6;error=gap-6-1.2*own[3]
            all_errors.append(error*error);gaps.append(gap)
            if row['time_s']<20.-1e-9:first.append(error*error)
            decision=row['controls'][name]['decision'];command=row['controls'][name]['command']
            known=decision['sensor_source'] in ('v2v','radar');good=good and known and abs(error)<=1.
            if known:
                age=row['time_s']-decision['selected_observed_s']
                violations['stale_source_ticks']+=not 0<=age<=(.2 if decision['sensor_source']=='radar' else .4)+1e-9
            else:violations['blind_brake_violations']+=command['accel']!=-6.
            violations['actuator_violations']+=not (-6<=command['accel']<=2.5 and abs(command['steering'])<=.5+1e-9 and abs(command['steering']-last_steer[name])<=.03+1e-9)
            violations['corridor_ticks']+=abs(own[1])>1.75
            jerks.append(((command['accel']-last_accel[name])/.05)**2)
            last_accel[name]=command['accel'];last_steer[name]=command['steering']
        flags.append((row['time_s']+.05,good))
    expected=dict(first20_spacing_rms_m=math.sqrt(statistics.fmean(first)),
        spacing_rms_m=math.sqrt(statistics.fmean(all_errors)),jerk_rms_m_s3=math.sqrt(statistics.fmean(jerks)),
        min_gap_m=min(gaps),**violations)
    for key,value in expected.items():
        assert math.isclose(value,stored[key],rel_tol=0,abs_tol=1e-10),('Independent score mismatch',key)
    assert peaks==stored['peak_speeds_m_s']
    for metric,end_index in [('first20_progress_m',399),('progress_m',len(frames)-1)]:
        for name in targets:
            distance=frames[end_index]['after'][name][0]-frames[0]['before'][name][0]
            assert math.isclose(distance,stored[metric][name],abs_tol=1e-10,rel_tol=0)
    events={};shift=case['shift'];end=case['seconds']
    if case['scenario']=='dual_blackout':events['dual']=independent_settling(flags,2.5+shift,end)
    if case['scenario']=='cut_in':
        events['cut_in']=independent_settling(flags,3.5+shift,12.5+shift)
        events['cut_out']=independent_settling(flags,12.5+shift,end)
    assert events==stored['settling'],'Independent settling/censoring mismatch'
    assert 3*len(frames)==stored['vehicle_ticks']
    return expected


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('study');args=parser.parse_args()
    root=Path(args.study);count=ticks=0;selected=None
    for stage in ['development','confirmation']:
        rows=json.loads((root/stage/'summary.json').read_text())
        for row in rows:
            folder=root/stage/f'{row["seed"]}-{int(row["speed"])}-{row["scenario"]}-{row["variant"]}'
            check_case(folder,row);count+=1;ticks+=row['vehicle_ticks'];selected=folder,row
        gate=json.loads((root/stage/'gate.json').read_text())
        for scenario,event in [('dual_blackout','dual'),('cut_in','cut_out')]:
            means={variant:statistics.fmean(r['settling'][event]['duration_s'] for r in rows if r['scenario']==scenario and r['variant']==variant) for variant in ['baseline','damped']}
            gain=100*(1-means['damped']/means['baseline'])
            assert math.isclose(gain,gate['recovery'][event]['gain_percent'],abs_tol=1e-10,rel_tol=0)
    folder,row=selected
    changed=dict(row,first20_spacing_rms_m=row['first20_spacing_rms_m']+.1)
    try:check_case(folder,changed)
    except AssertionError:negative=True
    else:raise AssertionError('Corrupt summary accepted')
    report=dict(passed=True,episodes=count,vehicle_ticks=ticks,negative_summary_check=negative,
        implementation='independent stdlib first20/full scores, constraints, progress, settling/censoring and mean gains',
        limitations='control/physics replay uses original shared kernels; bootstrap coverage not independently validated')
    (root/'independent.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
