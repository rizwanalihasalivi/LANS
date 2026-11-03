"""Post-control scoring only. Never imported by the target-selection controller."""
import itertools
import math
from integrations.connected_v2v.autonomy.study import overlaps


def measure(rows,road,speed,*,native=False):
    counts=dict(collisions=0,bound_violations=0,stale_source_ticks=0,blind_brake_violations=0,corridor_ticks=0)
    acquired=returned=0
    errors=[];events={};sources={};minimum=math.inf
    exit_s=23. if native else 22.
    stable=0;recovery=None;stop_ticks=0
    for row in rows:
        now=row['time_s'];ego=row['after'];info=row['decision'];command=row['command']
        traffic=row['traffic_after']
        for a,b in itertools.combinations([ego,*traffic.values()],2):
            counts['collisions']+=overlaps(a,b)
        counts['bound_violations']+=not(-6.<=command['accel']<=2.5 and abs(command['steering'])<=.5+1e-9)
        counts['blind_brake_violations']+=info['selection_brake'] and command['accel']!=-6.
        counts['corridor_ticks']+=abs(road.project(ego[:2])[1])>1.75
        source=info['sensor_source'];sources[source]=sources.get(source,0)+1
        if source in ('radar','v2v'):
            age=now-info['selected_observed_s']
            counts['stale_source_ticks']+=not(-1e-9<=age<=(.2 if source=='radar' else .4)+1e-9)
        event=info['selection_event'];events[event]=events.get(event,0)+1
        stop_ticks+=ego[3]<.1
        s=road.project(row['before'][:2])[0]
        nearest=[]
        for z in row['traffic_before'].values():
            front,d,_=road.project(z[:2])
            if abs(d)<1.8 and front>s:
                nearest.append(front-s-4.6)
        if nearest:minimum=min(minimum,min(nearest))
        target='intruder' if 11.5<=now<18. else 'leader' if now>=exit_s else None
        correct=False
        if target and info['target_gap_m'] is not None and info['sensor_source'] in ('v2v','radar'):
            gap=road.project(row['traffic_before'][target][:2])[0]-s-4.6
            correct=abs(gap-info['target_gap_m'])<2.
            acquired+=correct and target=='intruder'
            returned+=correct and target=='leader'
            if correct:errors.append((gap-6.-1.2*row['before'][3])**2)
        if now>=exit_s:
            stable=stable+1 if correct else 0
            if stable>=20 and recovery is None:recovery=now-exit_s-.95
    progress=road.project(rows[-1]['after'][:2])[0]-road.project(rows[0]['before'][:2])[0]
    seconds=len(rows)*.05
    passed=not any(counts.values()) and progress>max(25.,.4*speed*seconds) and acquired>=20 and returned>=20
    return dict(passed=bool(passed),**{k:int(v) for k,v in counts.items()},ticks=len(rows),
        progress_m=progress,acquired_intruder_ticks=int(acquired),recovered_leader_ticks=int(returned),
        return_delay_s=recovery,return_censored=recovery is None,
        spacing_rms_on_correct_target_m=math.sqrt(math.fsum(errors)/len(errors)) if errors else None,
        min_inlane_gap_m=minimum if math.isfinite(minimum) else None,
        stopped_ticks=int(stop_ticks),events=events,sensor_sources=sources)
