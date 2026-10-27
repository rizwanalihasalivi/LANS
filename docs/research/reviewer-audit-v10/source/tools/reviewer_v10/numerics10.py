"""Independent DOP853 reference and descriptive old/new predictor discrepancy."""
import boot10
import argparse
import json
import math
import time
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp
from rollout10 import rk_cost
from expiry_cost8 import expiry_cost
from core import GAINS

def reference(args):
    z0,actuator,speed,ks,gain,f,res,w,n=args;z=np.r_[z0,actuator];total=0.
    def curvature(t):return float(np.interp(speed*t,[0,10,20],ks))
    def rhs(t,z,u):
        ey,vy,ep,r,delta=z;k=curvature(t);front=80000*(delta-(vy+1.2*r)/speed);rear=80000*(-(vy-1.4*r)/speed)
        return [vy+speed*ep,(front+rear)/1650-speed*r,r-speed*k,(1.2*front-1.4*rear)/4224,np.clip((u-delta)/.05,-.35,.35)]
    for i in range(100):
        k=curvature(i*.01);vyref=(1.4*speed-1650*1.2*speed**3/(2.6*80000))*k
        ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*speed**2)*k
        base=np.clip(ff-gain@(z[:4]-[0,vyref,-vyref/speed,speed*k]),-.5,.5)
        if i and i<n:f+=(1-math.exp(-.01/.3))*(res-f)
        u=np.clip(base+(w*f if i<n else 0),-.5,.5);old=z[4]
        solution=solve_ivp(lambda t,y:rhs(t,y,u),(i*.01,(i+1)*.01),z,method='DOP853',rtol=1e-11,atol=1e-12,max_step=.001)
        assert solution.success;z=solution.y[:,-1];rate=(z[4]-old)/.01
        total+=.01*((z[0]/.5)**2+.2*(z[2]/.1)**2+.2*(rate/.35)**2+.005*(u/.5)**2)
    return total

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();rng=np.random.default_rng(10031);checks=[];disagreement=0;errors=[];times=[]
    # Warmup is outside all measured kernel calls.
    for i in range(100):
        speed=(15.,25.)[i%2];args=(rng.normal(size=4)*[.15,.1,.02,.02],float(rng.uniform(-.04,.04)),speed,rng.normal(size=3)*.002,GAINS[int(speed)],float(rng.uniform(-.04,.04)),float(rng.choice([-.08,0,.08])),float(rng.choice([.05,.1,.25])),int(rng.choice([1,2,4])))
        old0=expiry_cost(*args[:7],0.,0);old1=expiry_cost(*args);new0=rk_cost(*args[:7],0.,0);new1=rk_cost(*args)
        if i<4:
            exact=reference(args);error=abs(new1-exact);assert error<2e-6,(error,args)
            checks.append(dict(row=i,speed=speed,rk4_cost=new1,independent_dop853_cost=exact,absolute_error=error))
        errors.append(abs(old1-new1)/max(1e-12,abs(new1)))
        disagreement+=((old0-old1>=max(1e-7,.001*old0))!=(new0-new1>=max(1e-7,.001*new0)))
        start=time.perf_counter_ns();rk_cost(*args);times.append(time.perf_counter_ns()-start)
    a.output.write_text(json.dumps(dict(scope='Same nominal linear model; numerical integration/average-rate correction jointly assessed, not true hidden-plant accuracy or hard real-time timing',samples=100,independent_checks=checks,relative_cost_error_old_vs_new_median=float(np.median(errors)),relative_cost_error_p95=float(np.percentile(errors,95)),admission_disagreements=disagreement,kernel_ns_median=float(np.median(times)),kernel_ns_max=max(times)),indent=2)+'\n')
    print(a.output.read_text())
if __name__=='__main__':main()
