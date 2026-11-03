"""Independent stdlib-only exact trajectory/certificate checker.

No imports from the controller, simulation plant, Z3 or NumPy. Fixture truth is
used to CHECK premises, never as the controller's received obstacle state.
"""
import argparse
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def flow(x, v, a, t):
    # Integral until stop, then zero speed. Intentionally expressed differently
    # from shield.envelope, with the same declared physical contract.
    moving = min(t, v/(-a)) if a < 0 else t
    return x+v*moving+a*moving*moving/2, max(F(0), v+a*t)


def gap_minimum(x, v, a, p, w, c, h):
    """Exact minimum of two stopped constant-acceleration trajectories."""
    points={F(0),h}
    if a<0 and 0<v/(-a)<h:points.add(v/(-a))
    if c<0 and 0<w/(-c)<h:points.add(w/(-c))
    base=sorted(points)
    for left,right in zip(base,base[1:]):
        mid=(left+right)/2
        af=a if v+a*mid>0 else F(0)
        al=c if w+c*mid>0 else F(0)
        relative=flow(p,w,c,left)[1]-flow(x,v,a,left)[1]
        if al!=af:
            critical=left-relative/(al-af)
            if left<critical<right:points.add(critical)
    return min(flow(p,w,c,t)[0]-flow(x,v,a,t)[0] for t in points)


def check_episode(path):
    path=Path(path);spec=json.loads((path/'case.json').read_text())
    rows=[json.loads(line) for line in (path/'ticks.jsonl').read_text().splitlines()]
    c={k:F(v) for k,v in spec['contract'].items()};h,b,m=c['horizon'],c['brake'],c['margin']
    assert len(rows)==int(F(spec['seconds'])/h)
    predicted_x,predicted_v=map(F,spec['initial_upper'])
    bounds={};history={};latest={};previous=None;old_obstacles={}
    smallest=None;small_q=None;interventions=memory_ticks=0;sum_error=F(0);stop_ticks=0
    for tick,row in enumerate(rows):
        now=tick*h
        assert row['tick']==tick and F(row['time'])==now
        x,v=map(F,row['ego_before']);assert v>=0
        if previous is not None:assert (x,v)==previous
        obs={n:tuple(map(F,state)) for n,state in row['obstacles_before'].items()}
        assert set(old_obstacles)<=set(obs),'protection was silently removed'
        for name,state in old_obstacles.items():assert obs[name]==state
        ex,ev=map(F,row['ego_measurement'])
        assert abs(ex-x)<=F('.05') and abs(ev-v)<=F('.05')
        X=min(predicted_x,ex+F('.05'));V=min(predicted_v,max(F(0),ev+F('.05')))
        assert X>=x and V>=v
        for event in row['arrivals']:
            message=event['message'];name,source=message['name'],message['source']
            seq=message['sequence'];stamp=F(message['observed']);ttl=F('.2') if source=='radar' else F('.4')
            key=(name,source);old=history.get(key)
            valid=(type(seq) is int and seq>=0 and 0<=stamp<=now and now-stamp<=ttl
                and (old is None or seq>old[0] and stamp>=old[1]))
            assert event['accepted']==valid,'source freshness/replay outcome mismatch'
            assert source in ('radar','v2v') and stamp/h==int(stamp/h)
            at=rows[int(stamp/h)]['obstacles_before'][name]
            true_p,true_v=map(F,at)
            error=F('.15') if source=='radar' else F('.10')
            assert abs(F(message['position'])-true_p)<=error
            assert abs(F(message['speed'])-true_v)<=F('.08')
            if valid:
                history[key]=(seq,stamp);lower=F(message['position'])-error
                bounds[name]=max(bounds.get(name,lower),lower);latest[key]=message
        assert set(obs)<=set(bounds),'an actual obstacle has not been admitted'
        assert set(bounds)==set(obs)
        for name,L in bounds.items():assert L<=obs[name][0]
        B=min(bounds.values());Q=2*b*(B-X-m)-V*V
        assert Q>=0,'initial/admission recoverability is false'
        cert=row['certificate'];u=F(row['command']);a=u+c['uncertainty']
        assert -b-c['uncertainty']<=u<=c['maximum_command']
        assert (u+b+c['uncertainty'])/c['quantum']==int((u+b+c['uncertainty'])/c['quantum'])
        expected_x,expected_v=flow(X,V,a,h);s=expected_x-X
        slack=2*b*(B-X-m)-2*b*s-expected_v*expected_v
        assert slack>=0,'unsafe command certificate'
        expected=dict(x=X,v=V,boundary=B,command=u,upper_accel=a,displacement=s,
            next_v=expected_v,next_x=expected_x,invariant_scaled=Q,guard_slack_scaled=slack)
        assert set(cert)==set(expected)
        for name,value in expected.items():assert F(cert[name])==value,('certificate field',name)
        fresh=[v for (name,source),v in latest.items() if now-F(v['observed']) <= (F('.2') if source=='radar' else F('.4'))]
        if spec['profile']=='adversarial_nominal':nominal=c['maximum_command']
        elif not fresh:nominal=-b-c['uncertainty']
        else:
            target=min(fresh,key=lambda z:F(z['position']))
            vg=max(F(0),F(target['speed']))
            nominal=min(F('.64')*(F(target['position'])-ex-6-F('1.2')*max(F(0),ev))
                +F('.832')*(vg-max(F(0),ev)),F('.8')*(F(spec['speed'])-max(F(0),ev)))
        assert F(row['nominal'])==nominal
        clipped=max(-b-c['uncertainty'],min(c['maximum_command'],nominal))
        assert u<=clipped
        # Maximality is not needed for safety, but checks correspondence to the
        # reference grid enumeration without importing the implementation.
        larger=u+c['quantum']
        if larger<=clipped:
            xx,vv=flow(X,V,larger+c['uncertainty'],h)
            assert 2*b*(xx-X)+vv*vv>2*b*(B-X-m)
        aa=F(row['actual_accel']);assert abs(aa-u)<=c['uncertainty']
        after=flow(x,v,aa,h);assert tuple(map(F,row['ego_after']))==after
        assert after[0]<=expected_x and after[1]<=expected_v
        ca={name:F(value) for name,value in row['obstacle_accels'].items()}
        next_obs={name:flow(p,w,ca[name],h) for name,(p,w) in obs.items()}
        assert next_obs=={name:tuple(map(F,state)) for name,state in row['obstacles_after'].items()}
        for name,(p,w) in obs.items():
            assert w>=0 and next_obs[name][0]>=p
            value=gap_minimum(x,v,aa,p,w,ca[name],h)
            assert value>=m,('continuous bumper-gap violation',tick,name,str(value))
            smallest=value if smallest is None else min(smallest,value)
        small_q=Q if small_q is None else min(small_q,Q)
        actual_front=min(p for p,w in obs.values())
        error=actual_front-x-6-F('1.2')*v;sum_error+=error*error
        interventions+=u<clipped
        memory_ticks+=not bool(fresh)
        stop_ticks+=v<F('.1')
        predicted_x,predicted_v=expected_x,expected_v
        previous=after;old_obstacles=next_obs
    result=dict(passed=True,ticks=len(rows),minimum_continuous_gap_m=float(smallest),
        minimum_invariant_scaled=float(small_q),progress_m=float(previous[0]-F(rows[0]['ego_before'][0])),
        stopped_s=float(stop_ticks*h),nominal_reductions=interventions,no_fresh_state_ticks=memory_ticks,
        spacing_rms_m=(float(sum_error/len(rows)))**.5,
        trace_sha256=sha(path/'ticks.jsonl'),case_sha256=sha(path/'case.json'))
    return result


def audit(root,stage='all'):
    root=Path(root);plan=json.loads((root/'plan.json').read_text())
    for name,expected in plan['sources'].items():assert sha(root/'source'/name)==expected
    stages=('development','validation') if stage=='all' else (stage,)
    result={}
    for which in stages:
        summary=json.loads((root/which/'summary.json').read_text());checked=[]
        expected_jobs={(p,s,k) for p in plan['profiles'] for s in plan['speeds']
            for k in plan[which+'_seeds']}
        assert {(z['profile'],z['speed'],z['seed']) for z in summary['results']}==expected_jobs
        assert len(summary['results'])==len(expected_jobs)
        for original in summary['results']:
            path=root/which/f"{original['profile']}-{original['speed']}-{original['seed']}"
            computed=check_episode(path)
            for key,value in computed.items():assert original[key]==value,('aggregate',path.name,key)
            assert json.loads((path/'summary.json').read_text())==original
            checked.append(computed)
        assert summary['passed'] is True and all(z['passed'] for z in checked)
        result[which]=dict(passed=True,episodes=len(checked),ticks=sum(z['ticks'] for z in checked),
            minimum_continuous_gap_m=min(z['minimum_continuous_gap_m'] for z in checked),
            maximum_spacing_rms_m=max(z['spacing_rms_m'] for z in checked),
            maximum_stopped_s=max(z['stopped_s'] for z in checked))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--stage',choices=('all','development','validation'),default='all')
    a=p.parse_args();print(json.dumps(audit(a.root,a.stage),indent=2))
