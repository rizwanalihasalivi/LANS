"""Audit actual Webots telemetry, calibrated parameters and archived source provenance."""
import csv,hashlib,json,math
from pathlib import Path
from statistics import mean
import numpy as np
from geometry import corridor_margin

ROOT=Path(__file__).resolve().parents[1]

def inference_durations(rows):
    # Holding one packet for many control ticks must not count it as many inferences.
    seen=set();durations=[]
    for row in rows:
        if not row['ppo_available']:continue
        key=row.get('output_sequence',row['t_observation_s'])
        if key not in seen:
            seen.add(key);durations.append(row['inference_wall_s'])
    return durations


def audit(folder):
    metrics=json.loads((folder/'metrics.json').read_text());case=metrics['case']
    for path,digest in json.loads((folder/'inputs.json').read_text()).items():
        assert hashlib.sha256((folder/'source'/path).read_bytes()).hexdigest()==digest,(folder,path)
    with (folder/'telemetry.csv').open() as stream:
        rows=[]
        for row in csv.DictReader(stream):
            rows.append({k:(v if k=='supervisor_reason' else float(v)) for k,v in row.items()})
    assert len(rows)==metrics['steps'] and len(rows)>0
    scheduled=round(case['duration']/.01)
    assert 0<len(rows)<=scheduled
    if metrics['survived']:assert len(rows)==scheduled
    rmse=math.sqrt(mean(row['error_m']**2 for row in rows))
    maximum=max(abs(row['error_m']) for row in rows)
    assert math.isclose(rmse,metrics['rmse_m'],rel_tol=1e-12,abs_tol=1e-12),'RMSE disagrees with telemetry'
    assert math.isclose(maximum,metrics['max_abs_error_m'],rel_tol=1e-12,abs_tol=1e-12),'Maximum error disagrees with telemetry'
    if 'penalized_rmse_m' in metrics:
        score=math.sqrt((sum(row['error_m']**2 for row in rows)+(scheduled-len(rows))*6.25)/scheduled)
        assert math.isclose(score,metrics['penalized_rmse_m'],rel_tol=1e-12,abs_tol=1e-12),'Failure-penalized RMSE disagrees with telemetry'
    previous=0.;previous_time=rows[0]['t_command_s']-.01
    for row in rows:
        assert all(math.isfinite(v) for k,v in row.items() if k!='supervisor_reason')
        assert abs(row['t_state_s']-row['t_command_s']-.01)<1e-8
        assert abs(row['t_command_s']-previous_time-.01)<1e-8
        assert abs(row['command_rad'])<=.50000001 and abs(row['actuator_rad'])<=.50000001
        assert abs(row['actuator_rad']-previous)/.01<=.3500001
        if case['mode']=='fusion' and row['ppo_available']:
            assert row['inference_end_wall_s']>=row['inference_start_wall_s']>0
            assert abs(row['command_age_s']-(row['t_command_s']-row['t_observation_s']))<1e-8
            assert row['t_available_sim_s']<=row['t_command_s']+1e-8
        previous=row['actuator_rad'];previous_time=row['t_command_s']
    vehicle=json.loads((folder/'vehicle.json').read_text())
    assert abs(vehicle['mass_kg']-1650)<1e-8 and abs(vehicle['nominal_cg_x_m']-1.4)<1e-8
    assert abs(vehicle['nominal_yaw_inertia']-4224)<1e-7
    path=(1,0.,0.,0.) if case.get('path')=='dlc220' else (0,0.,120.,0.)
    margins=[corridor_margin(r['x_cg_m'],r['y_cg_m'],r['heading_rad'],path) for r in rows]
    ages=[r['command_age_s'] for r in rows if r['ppo_available']]
    durations=inference_durations(rows)
    return dict(mode=case['mode'],speed=case['speed'],noise=case.get('noise',0),seed=case.get('seed'),delay_ms=case.get('delay_ms',0),
                survived=metrics['survived'],steps=len(rows),rmse_m=rmse,max_error_m=maximum,
                corridor_min_margin_m=float(min(margins)),corridor_violation_fraction=float(np.mean(np.array(margins)<0)),
                max_actuator_wheel_mean_error_rad=max(abs(r['actuator_rad']-r['measured_center_angle_rad']) for r in rows),
                max_measured_wheel_mean_rate_rad_s=max((abs(a['measured_center_angle_rad']-b['measured_center_angle_rad'])/.01 for a,b in zip(rows,rows[1:])),default=0.),
                age_p99_s=float(np.quantile(ages,.99)) if ages else 0.,
                inference_p99_wall_s=float(np.quantile(durations,.99)) if durations else 0.,
                inference_unique_packets=len(durations),
                fallback_fraction=metrics['fallback_fraction']),rows

def main():
    result={'open_loop':{},'tracking':{},'transfer':{},'tire_identification':{},'physics_convergence':{}}
    calibration=ROOT/'results/physical-validated'
    for folder in sorted(calibration.glob('open-*')):
        data,rows=audit(folder);result['open_loop'][folder.name]=data
        angle=json.loads((folder/'case.json').read_text())['angle']
        steady=[r for r in rows if r['t_test_s']>=6]
        assert abs(mean(r['speed_truth_m_s'] for r in steady)-data['speed'])<.3
        if angle==0:
            assert max(abs(r['y_cg_m']) for r in rows)<.1
        else:
            assert rows[-1]['heading_rad']*angle>0 and rows[-1]['y_cg_m']*angle>0
            v=mean(r['speed_truth_m_s'] for r in steady);r=mean(r['yaw_rate_rad_s'] for r in steady)
            vy=mean(r['vy_truth_m_s'] for r in steady);delta=mean(r['measured_center_angle_rad'] for r in steady)
            af=delta-math.atan((vy+1.2*r)/v);ar=-math.atan((vy-1.4*r)/v)
            cf=1650*v*r*1.4/(2.6*math.cos(delta)*af);cr=1650*v*r*1.2/(2.6*ar)
            assert abs(cf/80000-1)<.15 and abs(cr/80000-1)<.15
            result['tire_identification'][folder.name]={'effective_Cf_N_rad':cf,'effective_Cr_N_rad':cr,'alpha_f_rad':af,'alpha_r_rad':ar}
    baseline=json.loads((calibration/'open-v25-d0.003/metrics.json').read_text())
    for step in (2,5,10):
        folder=calibration/f'convergence-{step}ms';data,rows=audit(folder)
        metrics=json.loads((folder/'metrics.json').read_text())
        result['physics_convergence'][str(step)]={'relative_curvature_difference_vs_1ms':abs(metrics['steady_curvature_per_m']/baseline['steady_curvature_per_m']-1),
               'final_y_difference_m':metrics['final']['y_cg_m']-baseline['final']['y_cg_m']}
    for folder in sorted((ROOT/'results/physical-tracking-final').glob('lqr-*')):
        data,_=audit(folder);assert data['survived'];result['tracking'][folder.name]=data
    for folder in sorted((ROOT/'results/physical-transfer-final').glob('*')):
        if folder.is_dir():result['transfer'][folder.name]=audit(folder)[0]
    assert len(result['open_loop'])==9 and len(result['tracking'])==9 and len(result['transfer'])==45
    destination=ROOT/'results/research-core/physical-audit.json';destination.write_text(json.dumps(result,indent=2)+'\n')
    print('Verified 9 open-loop, 3 convergence, 9 corrected-LQR and 45 actual Webots policy-transfer runs')
if __name__=='__main__':main()
