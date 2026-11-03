"""Standard-library scoring checker, independent of controller/report helpers."""
import argparse
import itertools
import json
import math
from pathlib import Path

FOLLOWERS=('follower-1','follower-2')


def compute(path):
    rows=[json.loads(s) for s in (Path(path)/'ticks.jsonl').read_text().splitlines()]
    target={'follower-1':'leader','follower-2':'follower-1'}
    squared=[];commands=[];executed=[];gaps=[]
    last_command={name:0. for name in FOLLOWERS};last_acceleration=dict(last_command)
    collisions=corridor=stale=bounds=fallback=rate_violations=0
    last_steering={name:0. for name in FOLLOWERS}
    for row in rows:
        target.update(row['membership'])
        for a,b in itertools.combinations(row['after'].values(),2):
            collisions+=math.hypot(a[0]-b[0],a[1]-b[1])<=4.6
        for name in FOLLOWERS:
            state=row['after'][name];before=row['before'][name]
            front=row['after'][target[name]]
            gap=front[0]-state[0]-4.6;gaps.append(gap)
            squared.append((gap-6.-1.2*state[3])**2)
            command=row['controls'][name]['command'];info=row['controls'][name]['decision']
            commands.append(((command['accel']-last_command[name])/.05)**2)
            actual_accel=(state[3]-before[3])/.05
            executed.append(((actual_accel-last_acceleration[name])/.05)**2)
            last_acceleration[name]=actual_accel;last_command[name]=command['accel']
            corridor+=abs(state[1])>1.75
            bounds+=not (-6.<=command['accel']<=2.5 and abs(command['steering'])<=.5+1e-9)
            rate_violations+=abs(command['steering']-last_steering[name])>.03+1e-9
            last_steering[name]=command['steering']
            if info['sensor_source'] in ('radar','v2v'):
                age=row['time_s']-info['selected_observed_s']
                stale+=not (0<=age<=(.2 if info['sensor_source']=='radar' else .4)+1e-9)
            fallback+=info['source'] in ('fallback_brake','hold_brake')
    return dict(spacing_rms_m=math.sqrt(math.fsum(squared)/len(squared)),
                jerk_rms_m_s3=math.sqrt(math.fsum(commands)/len(commands)),
                executed_jerk_rms_m_s3=math.sqrt(math.fsum(executed)/len(executed)),
                min_gap_m=min(gaps),collision_pair_ticks=int(collisions),corridor_ticks=int(corridor),
                stale_source_ticks=int(stale),bound_violations=int(bounds),fallback_ticks=int(fallback),
                steering_rate_violations=int(rate_violations),vehicle_ticks=3*len(rows),
                progress_m={name:rows[-1]['after'][name][0]-rows[0]['before'][name][0] for name in FOLLOWERS})


def check_case(path,summary):
    result=compute(path)
    for key in ['spacing_rms_m','jerk_rms_m_s3','min_gap_m']:
        assert math.isclose(result[key],summary[key],rel_tol=0,abs_tol=1e-10),('Independent metric mismatch',key)
    for key in ['collision_pair_ticks','corridor_ticks','stale_source_ticks','bound_violations','fallback_ticks','vehicle_ticks']:
        assert result[key]==summary[key],('Independent count mismatch',key)
    for name in FOLLOWERS:
        assert math.isclose(result['progress_m'][name],summary['progress_m'][name],rel_tol=0,abs_tol=1e-10)
    assert result['steering_rate_violations']==0
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('study');args=parser.parse_args()
    root=Path(args.study);stages={};ticks=0
    for stage in ['development','confirmation']:
        summaries=json.loads((root/stage/'summary.json').read_text());results=[]
        for row in summaries:
            folder=root/stage/f'{row["seed"]}-{int(row["speed"])}-{row["scenario"]}-{row["method"]}'
            result=check_case(folder,row);results.append(dict(method=row['method'],**result));ticks+=result['vehicle_ticks']
        stages[stage]={method:dict(
            command_jerk_mean=math.fsum(r['jerk_rms_m_s3'] for r in results if r['method']==method)/72,
            executed_jerk_mean=math.fsum(r['executed_jerk_rms_m_s3'] for r in results if r['method']==method)/72)
            for method in ['v2v_only','radar_acc','fusion']}
    # Negative check: altered summary must fail without changing original evidence.
    selected=summaries[0];folder=root/'confirmation'/f'{selected["seed"]}-{int(selected["speed"])}-{selected["scenario"]}-{selected["method"]}'
    tampered=dict(selected,spacing_rms_m=selected['spacing_rms_m']+.1)
    try:check_case(folder,tampered)
    except AssertionError:negative=True
    else:raise AssertionError('Independent checker accepted corrupted summary')
    report=dict(passed=True,episodes=432,vehicle_ticks=ticks,negative_summary_check=negative,
                implementation='stdlib only; imports no controller, simulation or reporter helper',
                stages=stages,note='Executed jerk is a posthoc diagnostic, not a replacement for frozen command-jerk gates')
    (root/'independent-metrics.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
