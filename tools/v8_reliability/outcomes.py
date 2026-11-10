"""Machine-readable outcome ledger; consistency audits never override failed gates."""
from pathlib import Path
import json,statistics
from .confirm import DATA
from .calibrate import write


def read(path):return json.loads(Path(path).read_text())


def native_report():
    root=DATA/'native-validation-v1';records=read(root/'summary.json');assert len(records)==28
    assert read(root/'independent-verification.json')['passed']
    baselines={(r['case']['route'],r['case']['speed']):r for r in records if r['case']['mode']=='lqr'}
    result={}
    for name,execution in [('lqr','sync'),('original_v8','original-v8'),('current_v2','process')]:
        rr=[r for r in records if r['case']['execution']==execution];rows=[];times=[]
        for r in rr:
            out=root/r['case']['name'];rows.extend(json.loads(x) for x in (out/'ticks.jsonl').read_text().splitlines())
            times.extend(json.loads(x) for x in (out/'timing.jsonl').read_text().splitlines())
        result[name]=dict(episodes=len(rr),ticks=len(rows),incomplete_runs=sum(not r['completed'] for r in rr),
            corridor_ticks=sum(r['corridor_exceedances'] for r in rr),response_misses=sum(r['response_misses'] for r in rr),
            local_complete_cycle_misses=sum(r['cycle_misses'] for r in rr),
            scheduled_response_misses=sum(r['scheduled_response_misses'] for r in rr),
            scheduled_complete_cycle_misses=sum(r['scheduled_cycle_misses'] for r in rr),
            response_max_ms=max(r['response_ms'] for r in rows),response_owner_cpu_max_ms=max(t['response_cpu_ms'] for t in times),
            complete_cycle_max_ms=max(t['complete_cycle_ms'] for t in times),
            native_physics_max_ms=max(t['native_physics_wall_ms'] for t in times),
            trace_write_max_ms=max(t['trace_write_ms'] for t in times),
            max_measured_center_steering_rate=max(r['max_measured_rate'] for r in rr),
            rmse_m=statistics.fmean(r['rmse_m'] for r in rr),
            heading_rms_rad=statistics.fmean(r['heading_rmse_rad'] for r in rr),
            steering_rate_rms=statistics.fmean(r['steering_rate_rms'] for r in rr),
            minimum_lqr_progress_ratio=min(r['progress_m']/baselines[r['case']['route'],r['case']['speed']]['progress_m'] for r in rr))
    result['current_v2']['heading_ratio_to_lqr']=result['current_v2']['heading_rms_rad']/result['lqr']['heading_rms_rad']
    result['current_v2']['rate_ratio_to_lqr']=result['current_v2']['steering_rate_rms']/result['lqr']['steering_rate_rms']
    result['startup_failures_retained']=read(root/'STATUS.json').get('startup_failures_retained',0)
    result['scope']='Four road/speed cells with three frozen actors; single ideal-sensor car, actual 1ms Webots physics, no native traffic/collision or WCET claim.'
    return result


def live_report():
    root=DATA/'live-v1';records=read(root/'summary.json');assert len(records)==26
    assert read(root/'independent-verification.json')['passed']
    result={}
    for label,role,paired in [('old','old',False),('new','new',False),('new_matched_only','new',True)]:
        rr=[r for r in records if r['role']==role and (not paired or r['planner_fault']=='none')]
        result[label]=dict(episodes=len(rr),ticks=sum(r['ticks'] for r in rr),
            functional_failures=sum(r['failed'] or not r['fault_checks_passed'] for r in rr),
            response_misses=sum(r['response_misses'] for r in rr),scheduled_response_misses=sum(r['scheduled_response_misses'] for r in rr),
            local_complete_cycle_misses=sum(r['cycle_misses'] for r in rr),scheduled_complete_cycle_misses=sum(r['scheduled_cycle_misses'] for r in rr),
            response_max_ms=max(r['response_max_ms'] for r in rr),complete_cycle_max_ms=max(r['cycle_max_ms'] for r in rr))
    result['startup_failures_retained']=read(root/'STATUS.json').get('startup_failures_retained',0)
    result['scope']='Twelve matched conditions per role plus two current-owner planner fault checks; counts are engineering observations, not independent traffic seeds or WCET.'
    return result


def main():
    v1=read(DATA/'confirmation-v1/final-assessment.json');v2=read(DATA/'confirmation-v2/final-assessment.json')
    native=native_report();live=live_report();outstanding=list(v2['reasons'])
    if not v2['no_quality_regression_to_lqr']:outstanding.append('all_heading_and_rate_metrics_improve_over_lqr')
    if native['current_v2']['response_misses'] or native['current_v2']['scheduled_complete_cycle_misses']:outstanding.append('strict_native_50ms_timing_gate')
    if native['current_v2']['incomplete_runs'] or native['current_v2']['corridor_ticks']:outstanding.append('native_tracking_gate')
    if native['current_v2']['max_measured_center_steering_rate']>.6+1e-9:outstanding.append('native_physical_steering_rate_gate')
    if native['current_v2']['minimum_lqr_progress_ratio']<.99:outstanding.append('native_progress_gate')
    if live['new']['response_misses'] or live['new']['scheduled_complete_cycle_misses']:outstanding.append('strict_actual_worker_50ms_timing_gate')
    if live['new']['functional_failures']:outstanding.append('actual_worker_functional_gate')
    result=dict(controller_revision=2,policies_changed=False,training_steps=0,
        original_v8_verified_development_result_preserved=True,
        v1_final=dict(original_gate_passed=v1['original_gate_passed'],reasons=v1['reasons'],comparisons=v1['comparisons']),
        v2_final=dict(original_gate_passed=v2['original_gate_passed'],reasons=v2['reasons'],comparisons=v2['comparisons']),
        exposed_regression_development=read(DATA/'v2-exposed-development/STATUS.json'),
        v2_finite_python_safety=read(DATA/'confirmation-v2/safety-summary.json'),native=native,actual_workers=live,
        production_promotion=False,outstanding_measured_gates=outstanding,
        publication_scope=dict(closest_method='LANS-model CBF mechanism adaptation with explicit source audit',
            full_original_paper_reproduction=False,universal_novelty_claim=False,universal_safety_proof=False,full_native_traffic_validation=False),
        separate_agent_scope='PPO incremental benefit, policy/reward/features/training; no such changes made here',
        ledger_semantics='Audits establish recorded-data consistency. Failed scientific, progress, quality and timing gates remain failed; no promotion or universal proof follows from zero sampled collisions.')
    write(DATA/'outcome-ledger.json',result);print(json.dumps(dict(production_promotion=False,outstanding=outstanding,native=native['current_v2'],actual_workers=live['new'])),flush=True)


if __name__=='__main__':main()
