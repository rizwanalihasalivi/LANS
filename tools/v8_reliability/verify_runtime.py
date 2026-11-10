"""Independent raw timing and native-frame consistency checks."""
from pathlib import Path
import argparse,json,math
from .verify import sha,episode,close


def timing(out,summary,rows):
    p=out/'timing.jsonl';assert sha(p)==summary['timing_sha256']
    ts=[json.loads(x) for x in p.read_text().splitlines()];assert len(ts)==len(rows)
    for i,(r,t) in enumerate(zip(rows,ts)):
        assert r['tick']==t['tick']==i
        assert t['complete_cycle_ms']>=r['response_ms']>=0
        assert t['scheduled_cycle_ms']>=r['scheduled_response_ms']>=0
        # Release is sampled after the perf-counter start; preemption there is
        # inside response_ms. End sampling follows the perf-counter cycle end.
        # An arbitrary sub-millisecond equality tolerance would reject valid
        # non-atomic observations. Keep each clock's ordering and this bound.
        assert t['scheduled_cycle_ms']-t['complete_cycle_ms']-r['release_lateness_ms']>=-r['response_ms']-1e-6
        if 'owner_cpu_ms' in t:
            assert t['owner_cpu_ms']>=t['response_cpu_ms']>=0 and t['trace_write_ms']>=0
            assert t['voluntary_context_switches']>=0 and t['involuntary_context_switches']>=0
            phase='native_physics_wall_ms' if 'native_physics_wall_ms' in t else 'plant_wall_ms'
            assert t[phase]>=0 and t[phase]+t['trace_write_ms']<=t['complete_cycle_ms']+1e-6
            assert t['response_cpu_ms']==r['response_cpu_ms'] and t[phase]==r[phase]
    for key,source,field in [('response_misses',rows,'response_ms'),('cycle_misses',ts,'complete_cycle_ms'),
                             ('scheduled_response_misses',rows,'scheduled_response_ms'),('scheduled_cycle_misses',ts,'scheduled_cycle_ms')]:
        assert summary[key]==sum(r[field]>50. for r in source)
    assert close(summary['response_max_ms'],max(r['response_ms'] for r in rows))
    assert close(summary['cycle_max_ms'],max(r['complete_cycle_ms'] for r in ts))
    return ts


def native(out,s):
    raw=out/'ticks.jsonl';assert sha(raw)==s['raw_sha256'];rows=[json.loads(x) for x in raw.read_text().splitlines()]
    assert len(rows)==s['ticks']==len({r['tick'] for r in rows})
    timing(out,s,rows);frame=json.loads((out/'map-frame.json').read_text());origin=frame['origin_world_cg_m'];angle=frame['angle_rad'];offset=frame['offset_map_m']
    c,ss=math.cos(angle),math.sin(angle);case=s['case'];sq=[];hh=[];rates=[];last_command=0.;last_state=None;actuator=0.
    expected=round(case['duration']/.05);assert s['expected_ticks']==expected
    for i,r in enumerate(rows):
        assert close(r['time_s'],i*.05) and close(r['sim_time_after_s']-r['sim_time_before_s'],.05,1e-7)
        if last_state is not None:assert all(close(x,y) for x,y in zip(last_state,r['state_before']))
        for suffix in ('before','after'):
            w=r['world_state_'+suffix];m=r['state_'+suffix];x,y=w[0]-origin[0],w[1]-origin[1]
            expected_map=[c*x-ss*y+offset[0],ss*x+c*y+offset[1],math.atan2(math.sin(w[2]+angle),math.cos(w[2]+angle)),*w[3:]]
            assert all(close(x,y,1e-8) for x,y in zip(expected_map,m))
        state=r['state_after'];x=state[0]+case['phase'];w=2*math.pi/120
        ref=case['amplitude']*1.5*math.sin(w*x) if case['route']=='sine' else 0.
        heading=math.atan(case['amplitude']*1.5*w*math.cos(w*x)) if case['route']=='sine' else 0.
        err=state[1]-ref;ep=math.atan2(math.sin(state[2]-heading),math.cos(state[2]-heading))
        assert close(err,r['error']) and close(ep,r['heading_error'])
        assert r['collision_assessed'] is False and abs(r['applied_steering']-last_command)<=.03+1e-9
        assert r['applied_steering']==r['issued_steering'] and r['applied_accel']==r['issued_accel']
        assert abs(r['applied_steering'])<=.5+1e-9 and -6<=r['applied_accel']<=2.5
        assert close(actuator,r['actuator_before']) and r['max_actuator_rate']<=.59+1e-9
        assert abs(r['actuator_after']-actuator)<=.59*.05+1e-9
        assert r['max_measured_rate']+1e-8>=abs(r['measured_steering_after']-r['measured_steering_before'])/.05
        if r['source']=='ppo':assert 0<=r['proposal_age']<.15 and 0<=r['proposal_wall_age']<.15
        if r.get('planned_candidate_selected') and 'planner_backend' in r:
            assert 0<=r['planner_proposal_age']<.15 and 0<=r['planner_proposal_wall_age']<.15
        rate=(r['applied_steering']-last_command)/.05;assert close(rate,r['steering_rate'])
        sq.append(err*err);hh.append(ep*ep);rates.append(rate*rate);actuator=r['actuator_after'];last_command=r['applied_steering'];last_state=state
    assert close(math.sqrt((math.fsum(sq)+(expected-len(rows))*6.25)/expected),s['rmse_m'])
    assert close(math.sqrt(math.fsum(hh)/len(rows)),s['heading_rmse_rad'])
    assert close(math.sqrt(math.fsum(rates)/len(rows)),s['steering_rate_rms'])
    assert close(last_state[0],s['progress_m']) and s['corridor_exceedances']==sum(abs(r['error'])>1.75 for r in rows)
    assert close(s['max_measured_rate'],max(r['max_measured_rate'] for r in rows))
    assert s['completed']==(len(rows)==expected)
    return len(rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('kind',choices=('native','live'));p.add_argument('root',type=Path);a=p.parse_args();root=a.root
    summaries=json.loads((root/'summary.json').read_text());protocol=json.loads((root/'protocol.json').read_text())
    for name,h in protocol['source_hashes'].items():assert sha(root/'source'/name)==h
    counts=[]
    resumed=root/'interruption-1/resume-plan.json'
    if resumed.exists():
        rr=json.loads(resumed.read_text());assert rr['completed_outcomes_rerun']==rr['measured_failed_outcomes_rerun']==0
        for n,h in rr['source_hashes'].items():assert sha(resumed.parent/'source'/n)==h
        for d in rr['completed_preserved']:
            out=root/d['name'];assert sha(out/'summary.json')==d['summary_sha256'] and sha(out/'ticks.jsonl')==d['raw_sha256'] and sha(out/'timing.jsonl')==d['timing_sha256']
        for d in rr['startup_failures_retained']:assert sha(root/d['failure_path'])==d['failure_sha256']
    if a.kind=='native':
        assert len(summaries)==len(protocol['cases'])
        for c,s in zip(protocol['cases'],summaries):
            assert {k:v for k,v in s['case'].items() if k!='output'}==c
            out=root/c['name'];assert json.loads((out/'summary.json').read_text())==s;counts.append(native(out,s))
    else:
        assert len(summaries)==len(protocol['jobs'])==26
        for i,(job,s) in enumerate(zip(protocol['jobs'],summaries)):
            out=root/f'{i:02d}-{job["role"]}-{job["actor"]}-{job["case"]["scenario"]}-{job["ppo_fault"]}-{job["planner_fault"]}'
            assert json.loads((out/'summary.json').read_text())==s
            episode((out,job['case'],'hybrid',job['actor'],'actual_worker',None))
            rows=[json.loads(x) for x in (out/'ticks.jsonl').read_text().splitlines()];timing(out,s,rows)
            late=[r for r in rows if r['time_s']>=1.5]
            checked=True
            if job['ppo_fault']!='none':checked&=all(r['source']!='ppo' for r in late)
            if job['planner_fault']!='none':checked&=all(not r['planned_candidate_selected'] for r in late)
            assert checked==s['fault_checks_passed'];counts.append(len(rows))
    report=dict(passed=True,kind=a.kind,episodes=len(counts),ticks=sum(counts),
        scope='record consistency, source freshness and complete timing; native rigid-body physics not independently re-integrated; no WCET or universal safety')
    (root/'independent-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
