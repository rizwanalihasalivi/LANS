"""Independent arithmetic and provenance audit of recorded native calibration.

This reads raw speed/time measurements instead of trusting the producer's
aggregate. It does not execute the actuator or claim final controller transfer.
"""
from pathlib import Path
import argparse,hashlib,json,math,statistics


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
    return h.hexdigest()


def close(actual,expected,label,tol=1e-8):
    assert math.isfinite(float(actual)) and math.isfinite(float(expected)),label
    assert math.isclose(actual,expected,rel_tol=1e-10,abs_tol=tol),(label,actual,expected)


def verify(folder):
    folder=Path(folder).resolve();protocol=json.loads((folder/'protocol.json').read_text())
    summary=json.loads((folder/'summary.json').read_text());prior=json.loads((folder/'verification.json').read_text())
    assert protocol['role']=='policy_free_actuator_calibration_before_final_native'
    assert summary['role']=='policy_free_native_actuation_calibration'
    assert summary['completed'] and prior['completed']
    assert summary['policy_tested'] is False and summary['final_controller_tested'] is False
    assert prior['policy_tested'] is False and prior['final_controller_tested'] is False
    close(summary['physics_step_s'],.001,'native physics timestep')
    assert digest(folder/'protocol.json')==prior['protocol_sha256']
    assert digest(folder/'summary.json')==prior['summary_sha256']
    for name,expected in protocol['source_sha256'].items():
        assert digest(folder/'source'/name)==expected,('Retained source changed',name)
    for name,expected in protocol['protos'].items():
        assert digest(folder/'project'/name)==expected,('Pinned physical PROTO changed',name)
    assert digest(folder/'project/worlds/calibration.wbt')==protocol['world_sha256']
    cases=protocol['cases'];records=summary['records'];dt=.001;results=[]
    assert summary['conditions']==prior['conditions']==len(records)==len(cases)
    assert set(prior['raw_sha256'])=={f'condition-{i:03d}.jsonl' for i in range(len(cases))}
    assert len(list(folder.glob('condition-*.jsonl')))==len(cases)
    for index,(case,claimed) in enumerate(zip(cases,records)):
        assert claimed['case']==case
        name=f'condition-{index:03d}.jsonl';path=folder/name
        assert digest(path)==prior['raw_sha256'][name]
        rows=[json.loads(line) for line in path.open()];n=len(rows)
        assert n==round(protocol['duration_s']/dt)==claimed['rows']
        acceleration=[]
        for tick,row in enumerate(rows):
            assert row['index']==index and row['tick']==tick
            assert row['actuation_method']==protocol['actuation_method']
            close(row['requested_accel'],case['requested_accel_m_s2'],'requested acceleration')
            close(row['simulation_after_s']-row['simulation_before_s'],dt,'native sample period')
            close(row['measured_speed_m_s'],row['speed_before_m_s'],'sensor measurement precedes actuation')
            value=(row['speed_after_m_s']-row['speed_before_m_s'])/dt
            close(row['achieved_accel_m_s2'],value,'independent finite difference')
            acceleration.append(value)
            if tick:
                previous=rows[tick-1]
                close(row['simulation_before_s'],previous['simulation_after_s'],'native clock continuity')
                close(row['speed_before_m_s'],previous['speed_after_m_s'],'native speed continuity')
                for now,old in zip(row['physical_position_before'],previous['physical_position_after']):
                    close(now,old,'native position continuity')
                close(row['measured_accel_m_s2'],acceleration[tick-1],'causal delayed acceleration sensor')
            else:assert row['measured_accel_m_s2'] is None
            if protocol['actuation_method']=='torque_pi':
                assert row['engine_model_used'] is True
                assert 0<=row['throttle']<=1 and 0<=row['brake_intensity']<=1
                assert not (row['throttle']>0 and row['brake_intensity']>0)
                close(row['wheel_joint_damping'],protocol['wheel_joint_damping'],'frozen damping')
                close(row['brake_coefficient_nm'],protocol['brake_coefficient_nm'],'frozen brakes')
        # Exactly the producer's prespecified settling exclusion, applied to
        # independently derived accelerations rather than its logged scalar.
        settled=[a for tick,a in enumerate(acceleration) if tick*dt>=.2]
        requested=case['requested_accel_m_s2'];rmse=math.sqrt(statistics.mean((a-requested)**2 for a in settled))
        reached=next((tick*dt for tick,a in enumerate(acceleration) if abs(a-requested)<=.25),None)
        measures=dict(initial_measured_speed_m_s=rows[0]['speed_before_m_s'],
            measured_duration_s=rows[-1]['simulation_after_s']-rows[0]['simulation_before_s'],
            mean_accel_m_s2=statistics.mean(acceleration),settled_mean_accel_m_s2=statistics.mean(settled),
            settled_accel_rmse_m_s2=rmse,settled_min_accel_m_s2=min(settled),settled_max_accel_m_s2=max(settled),
            final_speed_m_s=rows[-1]['speed_after_m_s'])
        for key,value in measures.items():close(claimed[key],value,f'Condition{index}:{key}')
        if reached is None:assert claimed['first_reach_within_025_s'] is None
        else:close(claimed['first_reach_within_025_s'],reached,'first reach time')
        assert claimed['native_body_integrated'] is True
        assert all(claimed[k] is False for k in ('python_ego_integrated','pose_overwritten','velocity_overwritten'))
        results.append(dict(index=index,case=case,raw_sha256=digest(path),ticks=n,**measures))
    ranks={str(t):statistics.mean(r['settled_accel_rmse_m_s2'] for r in results if r['case']['lookahead_s']==t)
        for t in sorted({c['lookahead_s'] for c in cases})}
    assert set(ranks)==set(prior['aggregate_settled_accel_rmse_m_s2'])
    for key,value in ranks.items():close(value,prior['aggregate_settled_accel_rmse_m_s2'][key],'aggregate settled RMSE')
    selected=min(ranks,key=ranks.get)
    close(float(selected),prior['selected_common_lookahead_s'],'global common mapping')
    settled=all(abs(r['initial_measured_speed_m_s']-r['case']['initial_speed_m_s'])<=.1 for r in results)
    assert settled==prior['all_initial_speeds_settled']
    return dict(verified=True,numerical_calibration_recomputed=True,conditions=len(results),
        raw_physics_steps=sum(r['ticks'] for r in results),all_initial_speeds_settled=settled,
        aggregate_settled_accel_rmse_m_s2=ranks,records=results,
        policy_tested=False,final_controller_tested=False,
        protocol_sha256=digest(folder/'protocol.json'),summary_sha256=digest(folder/'summary.json'),
        producer_verification_sha256=digest(folder/'verification.json'),verifier_sha256=digest(__file__),
        scope='Recorded native calibration arithmetic and source/world/PROTO provenance only; no final policy, traffic, safety or deadline claim.',
        limitations=['Warmup step count is a producer declaration; no separate warmup raw trace is retained.',
            'Native body integration and absence of overwrites are source/producer declarations, not inferred from a scalar acceleration trace.'])


def main():
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--output',type=Path)
    args=p.parse_args();result=verify(args.folder)
    if args.output:
        with args.output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2,allow_nan=False),flush=True)


if __name__=='__main__':main()
