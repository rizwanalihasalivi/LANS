"""Fixed-headway formation metrics, including censoring and first-20 s scores."""
import json
import math
from pathlib import Path

FOLLOWERS = ('follower-1', 'follower-2')


def settling(samples, start, end):
    segment = [(t, good) for t, good in samples if start < t <= end+1e-9]
    bad = [t for t, good in segment if not good]
    last_bad = max(bad, default=start)
    candidates = [t for t, good in segment if good and t > last_bad+1e-9]
    if candidates and end-candidates[0] >= 2.-1e-9:
        return dict(duration_s=max(0., candidates[0]-start), censored=False)
    return dict(duration_s=end-start, censored=True)


def compute(path):
    path = Path(path)
    case = json.loads((path/'case.json').read_text())
    rows = [json.loads(s) for s in (path/'ticks.jsonl').read_text().splitlines()]
    target = {'follower-1':'leader', 'follower-2':'follower-1'}
    errors, prefix, jerks, gaps, samples = [], [], [], [], []
    previous_accel = {name:0. for name in FOLLOWERS}
    previous_steer = {name:0. for name in FOLLOWERS}
    blind = stale = bounds = speed_violations = collisions = corridor = 0
    peaks = {name:0. for name in ('leader', *FOLLOWERS)}
    for row in rows:
        target.update(row['membership']); good = True
        owned = ('leader', *FOLLOWERS)
        for name in owned:
            velocity = row['after'][name][3]
            peaks[name] = max(peaks[name], velocity)
            speed_violations += velocity > case['speed']+(8. if name != 'leader' else 0.)+1e-8
        values=list(row['after'].values())
        for i,a in enumerate(values):
            for b in values[i+1:]:collisions += math.hypot(a[0]-b[0],a[1]-b[1]) <= 4.6
        for name in FOLLOWERS:
            own,front = row['after'][name],row['after'][target[name]]
            gap = front[0]-own[0]-4.6; error = gap-6.-1.2*own[3]
            errors.append(error**2);gaps.append(gap)
            if row['time_s'] < 20.-1e-9:prefix.append(error**2)
            info = row['controls'][name]['decision']; command = row['controls'][name]['command']
            fresh = info['sensor_source'] in ('v2v','radar')
            good &= abs(error) <= 1. and fresh
            if fresh:
                age = row['time_s']-info['selected_observed_s']
                stale += not 0 <= age <= (.2 if info['sensor_source']=='radar' else .4)+1e-9
            if info['sensor_source'] in ('none','disagreement'):
                blind += command['accel'] != -6.
            bounds += not (-6. <= command['accel'] <= 2.5 and abs(command['steering']) <= .5+1e-9
                           and abs(command['steering']-previous_steer[name]) <= .03+1e-9)
            corridor += abs(own[1]) > 1.75
            jerks.append(((command['accel']-previous_accel[name])/.05)**2)
            previous_accel[name],previous_steer[name] = command['accel'],command['steering']
        samples.append((row['time_s']+.05,bool(good)))
    end = case['seconds'];shift = case['shift']
    result=dict(first20_spacing_rms_m=math.sqrt(math.fsum(prefix)/len(prefix)),
                spacing_rms_m=math.sqrt(math.fsum(errors)/len(errors)),
                jerk_rms_m_s3=math.sqrt(math.fsum(jerks)/len(jerks)),
                collision_pair_ticks=int(collisions),corridor_ticks=int(corridor),
                stale_source_ticks=int(stale),blind_brake_violations=int(blind),
                actuator_violations=int(bounds),speed_violations=int(speed_violations),
                min_gap_m=min(gaps),peak_speeds_m_s=peaks,vehicle_ticks=3*len(rows))
    index = min(len(rows),400)-1
    result['first20_progress_m']={name:rows[index]['after'][name][0]-rows[0]['before'][name][0] for name in FOLLOWERS}
    result['progress_m']={name:rows[-1]['after'][name][0]-rows[0]['before'][name][0] for name in FOLLOWERS}
    result['settling']={}
    if case['scenario']=='dual_blackout':result['settling']['dual']=settling(samples,2.5+shift,end)
    if case['scenario']=='cut_in':
        result['settling']['cut_in']=settling(samples,3.5+shift,min(12.5+shift,end))
        result['settling']['cut_out']=settling(samples,12.5+shift,end)
    return result
