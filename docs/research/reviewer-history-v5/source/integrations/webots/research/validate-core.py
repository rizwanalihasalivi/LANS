import hashlib,json,math
from pathlib import Path
import numpy as np
from core import advance,derivative,fiala,Supervisor,reference,path_values,Sensor,lqr
from comparison import configure_lqr
from tracking import tracking_lqr as lqr
configure_lqr()

out=Path(__file__).resolve().parents[1]/'results/research-core'
out.mkdir(parents=True,exist_ok=True)
checks={}
for load in (1650*9.81*1.4/2.6,1650*9.81*1.2/2.6):
    assert abs(fiala(1e-7,80000,load,.9)/1e-7-80000)<.1
    assert abs(fiala(.5,80000,load,.9))<=.9*load+1e-8
    assert fiala(.02,80000,load,.9)==-fiala(-.02,80000,load,.9)
checks['fiala_small_slip_slope_and_saturation']='passed'
s=np.zeros(6)
for _ in range(100):
    before=s[5];s=advance(s,.5,20)
    assert abs(s[5]-before)<=.0035000001
assert abs(s[5]-.35)<1e-9
checks['actuator_rate']='passed'
# Satisfies common Q/R noisy-observer development check, before held-out policies.
checks['lqr_development']={}
for v in (15,20,25):
    path=(1,0.,0.,0.);s=np.zeros(6);sensor=Sensor(9000);errors=[]
    for i in range(1600):
        _,est,k=sensor.measure(s,v,path);s=advance(s,lqr(est,v,k),v)
        errors.append(s[1]-path_values(s[0],path)[0])
    checks['lqr_development'][str(v)]={'rmse_m':float(np.sqrt(np.mean(np.square(errors)))),'max_error_m':float(np.max(np.abs(errors)))}
    assert max(np.abs(errors))<.5
checks['convergence']={}
for dt in (.01,.005,.002,.001,.0005):
    s=np.zeros(6)
    for i in range(1000):s=advance(s,.01*math.sin(i*.01),25,dt)
    checks['convergence'][str(dt)]=s.tolist()
reference_state=np.array(checks['convergence']['0.0005'])
checks['one_ms_vs_half_ms_max_state_difference']=float(np.max(np.abs(np.array(checks['convergence']['0.001'])-reference_state)))
assert checks['one_ms_vs_half_ms_max_state_difference']<1e-4
# Screen supplied short section lengths and explicitly stretched development geometry.
def screen(first,hold,second,total):
    maximum=0.
    for length in (first,second):
        for u in np.linspace(0,1,10001):
            dy=3.5*(30*u*u-60*u**3+30*u**4)/length
            ddy=3.5*(60*u-180*u*u+120*u**3)/length**2
            maximum=max(maximum,abs(ddy)/(1+dy*dy)**1.5)
    return {'length_m':total,'max_curvature_per_m':maximum,'margin_limit_m_s2':.8*.9*9.81,
            'speeds':{str(v):{'lateral_accel_m_s2':v*v*maximum,'passes_margin':bool(v*v*maximum<=.8*.9*9.81)} for v in (15,20,25)}}
checks['path_screen']={'candidate125':screen(30,25,25,125),'development220':screen(60,30,60,220)}
assert all(x['passes_margin'] for x in checks['path_screen']['development220']['speeds'].values())
sup=Supervisor();est=np.zeros(4)
for i in range(30):outval,w,reason=sup.fuse(i*.01,.02,(i,i*.01,.1),est)
assert w>.1
for bad in ((31,0.,float('nan')),(31,0.,.1),(1,.31,.1)):
    command,w,reason=sup.fuse(.31,.02,bad,est);assert command==.02 and w==0
checks['supervisor_invalid_stale_out_of_order']='passed'
checks['source_sha256']={p:hashlib.sha256(Path(__file__).with_name(p).read_bytes()).hexdigest() for p in ('core.py','protocol.json','validate-core.py','comparison.py','comparison-protocol.json','tracking.py','tracking-protocol.json')}
(Path(__file__).resolve().parents[1]/'results/research-core/checks.json').write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(checks,indent=2))
