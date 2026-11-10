"""A posteriori all-actor continuous 2-D trace certification and native refinement."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from fractions import Fraction as F
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
from .trace_certificate import certificate,A,OMEGA,POSE,L,W


def read(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(s) for s in Path(p).read_text().splitlines()]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pose(z):return z[:3]
def velocity(z):return z[3]*math.cos(z[2])-z[4]*math.sin(z[2]),z[3]*math.sin(z[2])+z[4]*math.cos(z[2])
def angle_delta(a,b):return math.atan2(math.sin(a-b),math.cos(a-b))


def native_refinement(path,spec,traces):
    reports={};initial={}
    for name,start in spec['starts'].items():
        s,d=start;R=spec['profile']['radius'];heading=s/R if R else 0.
        x,y=((R-d)*math.sin(heading),R-(R-d)*math.cos(heading)) if R else (s,d)
        initial[name]=[x+1.4*math.cos(heading),y+1.4*math.sin(heading),heading]
        data=rows(path/f'{name}-motion.jsonl');data=[z for z in data if z['time_s']<=spec['seconds']+1e-8]
        assert len(data)==round(spec['seconds']/.01)
        assert abs(data[0]['time_s']-.01)<1e-8 and abs(data[-1]['time_s']-spec['seconds'])<1e-8
        max_acc=max_yaw=max_bridge=max_command_error=max_planar_speed=0.
        speed_bound=traces[name][0].get('native_speed_cap_m_s')
        # Generated worlds start at rest; include their first 10 ms interval.
        start_motion=dict(time_s=0.,velocity=[0.,0.,0.],heading=heading,yaw_rate=0.)
        for before,after in zip([start_motion,*data[:-1]],data):
            dt=after['time_s']-before['time_s'];assert abs(dt-.01)<1e-8
            acceleration=max(abs(after['velocity'][i]-before['velocity'][i])/dt for i in (0,1))
            yaw=abs(angle_delta(after['heading'],before['heading']))/dt
            max_acc=max(max_acc,acceleration);max_yaw=max(max_yaw,yaw,abs(after['yaw_rate']))
        assert max_acc<=float(A)+1e-6 and max_yaw<=float(OMEGA)+1e-6,(name,'refinement bounds',max_acc,max_yaw)
        for z in data:
            assert all(math.isfinite(v) for v in [*z['position'],*z['velocity'],z['heading'],z['yaw_rate']])
            measured_speed=math.hypot(z['velocity'][0],z['velocity'][1])
            max_planar_speed=max(max_planar_speed,measured_speed)
            if speed_bound is not None:assert measured_speed<=speed_bound+.5,'10ms native speed-envelope qualification'
            t=z['time_s'];i=round(t/.05)-1
            if abs(t-(i+1)*.05)<1e-8 and 0<=i<len(traces[name]):
                raw=traces[name][i]
                assert all(abs(a-b)<1e-9 for a,b in zip(z['position'],raw['pose']['position']))
                assert abs(angle_delta(z['heading'],raw['state'][2]))<1e-9
            if t<.05:
                q0=dict(time_s=0.,state=initial[name]);q1=traces[name][0]
            else:
                left=min(len(traces[name])-2,max(0,math.floor((t+.000000001)/.05)-1))
                q0,q1=traces[name][left:left+2]
            h=q1['time_s']-q0['time_s'];f=(t-q0['time_s'])/h
            if not -1e-7<=f<=1+1e-7:continue
            for axis in (0,1):
                chord=(1-f)*q0['state'][axis]+f*q1['state'][axis]
                error=abs(z['position'][axis]-chord);max_bridge=max(max_bridge,error)
                assert error<=float(A)*h*h/8+2*float(POSE)+1e-8,(name,'native bridge',t,error)
        for sample in traces[name]:
            rpy=sample['pose']['rpy']
            assert len(rpy)==3 and all(math.isfinite(v) for v in rpy),'finite body pose required'
            assert max(abs(rpy[0]),abs(rpy[1]))<=.15,'planar-body pose qualification'
        for a,b in zip(traces[name],traces[name][1:]):
            dt=b['time_s']-a['time_s']
            max_command_error=max(max_command_error,abs((b['state'][3]-a['state'][3])/dt-a['command']['accel']))
        first=data[0]
        assert max(abs(first['position'][k]-initial[name][k]) for k in (0,1))<=float(POSE)+.5*float(A)*.01**2
        reports[name]=dict(motion_samples=len(data),max_sampled_coordinate_accel_m_s2=max_acc,
            max_sampled_yaw_rad_s=max_yaw,max_sampled_bridge_deviation_m=max_bridge,
            max_sampled_planar_speed_m_s=max_planar_speed,qualified_speed_cap_m_s=speed_bound,
            max_requested_vs_measured_accel_difference_m_s2=max_command_error)
    return reports,initial


def episode(path,output,native=False):
    path,output=Path(path),Path(output);output.mkdir(parents=True,exist_ok=False)
    native_info=None
    if native:
        spec=read(path/'config.json');traces={n:rows(path/f'{n}.jsonl') for n in spec['starts']}
        native_info,initial=native_refinement(path,spec,traces)
        frames=[(0.,initial)]
        frames += [(traces['follower'][i]['time_s'],{n:pose(z[i]['state']) for n,z in traces.items()}) for i in range(len(traces['follower']))]
    else:
        spec=read(path/'case.json');data=rows(path/'ticks.jsonl')
        frames=[(data[0]['time_s'],dict(follower=pose(data[0]['before']),**{n:pose(s) for n,s in data[0]['traffic_before'].items()}))]
        frames += [(z['time_s']+.05,dict(follower=pose(z['after']),**{n:pose(s) for n,s in z['traffic_after'].items()})) for z in data]
        # Finite checks qualify measured endpoints, not an unmeasured global ODE
        # bound. The analytical bridge contract remains explicit in the theorem.
        for row in data:
            for name,before in {'follower':row['before'],**row['traffic_before']}.items():
                after=row['after'] if name=='follower' else row['traffic_after'][name]
                vb,va=velocity(before),velocity(after)
                assert max(abs(a-b)/.05 for a,b in zip(va,vb))<=float(A)+1e-6
                assert abs(angle_delta(after[2],before[2]))/.05<=float(OMEGA)+1e-6
    pairs=0;minimum=None;clearance=None;missing=[]
    file=output/'witnesses.jsonl.gz'
    with gzip.open(file,'wt') as out:
        for index,((t0,old),(t1,new)) in enumerate(zip(frames,frames[1:])):
            h=F(str(t1))-F(str(t0));assert 0<h<=F('.05000000001')
            witness=[]
            for a,b in itertools.combinations(sorted(old),2):
                cert=certificate(old[a],new[a],old[b],new[b],h)
                pairs+=1
                if cert is None:
                    missing.append(dict(interval=index,time_s=t0,pair=[a,b]));continue
                minimum=cert['margin_um'] if minimum is None else min(minimum,cert['margin_um'])
                nx,ny=cert['axis']
                lower=F(cert['margin_um'],abs(nx)+abs(ny))
                clearance=lower if clearance is None else min(clearance,lower)
                witness.append([a,b,*cert['axis'],cert['separation_lower_um'],cert['occupancy_upper_um']])
            out.write(json.dumps(dict(interval=index,time_s=t0,witnesses=witness),separators=(',',':'))+'\n')
    result=dict(passed=not missing,intervals=len(frames)-1,pair_intervals=pairs,
        minimum_projection_margin_m=None if minimum is None else minimum/10**6,
        minimum_euclidean_clearance_lower_m=None if clearance is None else float(clearance),uncertified_pair_intervals=missing,
        witness_sha256=sha(file),native_refinement=native_info,
        contract=dict(coordinate_acceleration_bound_m_s2=str(A),yaw_rate_bound_rad_s=str(OMEGA),
            endpoint_coordinate_error_m=str(POSE),body_half_length_m=str(L),body_half_width_m=str(W)),
        scope='a posteriori finite continuous 2-D trace certificate under stated bounds; not prospective full-controller invariance')
    (output/'certificate.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def task(job):
    path,output,native=job
    try:return dict(case=Path(path).name,**episode(path,output,native))
    except Exception:
        import traceback
        Path(output).mkdir(parents=True,exist_ok=True);(Path(output)/'failure.txt').write_text(traceback.format_exc())
        return dict(case=Path(path).name,passed=False,error='see failure.txt')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--output',required=True)
    p.add_argument('--stage',choices=('development','validation','all'),default='all');p.add_argument('--native',action='store_true');a=p.parse_args()
    root,output=Path(a.root),Path(a.output);output.mkdir(parents=True,exist_ok=False)
    result={}
    for stage in (('development','validation') if a.stage=='all' else (a.stage,)):
        summary=read(root/stage/'summary.json');jobs=[]
        for r in summary['results']:
            name=f"{r['case']}-{r['speed']:g}-{r['seed']}";jobs.append((str(root/stage/name),str(output/stage/name),a.native))
        checked=[]
        with ProcessPoolExecutor(max_workers=3) as pool:
            for f in as_completed([pool.submit(task,j) for j in jobs]):
                r=f.result();checked.append(r);print(json.dumps({k:r[k] for k in ('case','passed')}),flush=True)
        result[stage]=dict(passed=all(r['passed'] for r in checked),results=sorted(checked,key=lambda r:r['case']))
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    if not all(z['passed'] for z in result.values()):raise SystemExit('trace certification failed; evidence retained')


if __name__=='__main__':main()
