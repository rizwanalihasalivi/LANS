"""LQR-default, estimated-state predictive gate; no ground-truth plant inputs."""
import math
import numpy as np
from numba import njit

@njit(cache=True)
def predict_cost(estimate, actuator, command, speed, curvature, gain, horizon):
    # Nominal linear bicycle, 10 ms Euler predictor, explicit rate/lag actuator.
    # Candidate held for 50 ms, then identical local-curvature LQR continuation.
    z=estimate.copy();delta=actuator;cost=0.
    vyref=(1.4*speed-1650*1.2*speed**3/(2.6*80000))*curvature
    target=np.array([0.,vyref,-vyref/speed,speed*curvature])
    ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*speed**2)*curvature
    for i in range(horizon):
        u=command if i<5 else max(-.5,min(.5,ff-np.dot(gain,z-target)))
        delta+=.01*max(-.35,min(.35,(u-delta)/.05))
        ey,vy,ep,r=z
        front=80000*(delta-(vy+1.2*r)/speed);rear=80000*(-(vy-1.4*r)/speed)
        z=z+.01*np.array([vy+speed*ep,(front+rear)/1650-speed*r,r-speed*curvature,(1.2*front-1.4*rear)/4224])
        cost+=.01*((z[0]/.5)**2+.2*(z[2]/.1)**2+.01*((z[3]-target[3])/.2)**2+.001*(u/.5)**2)
    return cost+.1*((z[0]/.5)**2+.2*(z[2]/.1)**2)

class Gate:
    def __init__(self,config):
        self.config=config;self.weight=0.;self.good=0;self.last_sequence=-1
    def reset(self,baseline,reason,j0=math.nan,j1=math.nan):
        self.weight=0.;self.good=0
        return baseline,0.,reason,j0,j1
    def choose(self,t,baseline,packet,estimate,actuator,speed,curvature,gain,role):
        if packet is None:return self.reset(baseline,'missing')
        seq,observed,action=packet
        if not np.isfinite([t,baseline,observed,action,actuator,speed,curvature,*estimate]).all():return self.reset(baseline,'nonfinite')
        age=t-observed
        if age<0 or age>=.05:return self.reset(baseline,'age')
        if seq<self.last_sequence:return self.reset(baseline,'sequence')
        self.last_sequence=seq
        if abs(estimate[0])>1.5 or abs(estimate[2])>.25:return self.reset(baseline,'envelope')
        # A residual is converted to a complete candidate command before blending.
        candidate=float(np.clip(baseline+np.clip(action,-.08,.08),-.5,.5)) if role=='residual' else float(np.clip(action,-.5,.5))
        fresh=max(0.,min(1.,(.05-age)/.04))
        j0=predict_cost(estimate,actuator,baseline,speed,curvature,gain,self.config['horizon_steps'])
        best=(j0,0.,baseline)
        for limit in (.1,.25,.5):
            w=min(limit*fresh,self.weight+.05)
            u=(1-w)*baseline+w*candidate
            j=predict_cost(estimate,actuator,u,speed,curvature,gain,self.config['horizon_steps'])
            if j<best[0]:best=(j,w,u)
        j,w,u=best
        if not math.isfinite(j0) or not math.isfinite(j):return self.reset(baseline,'prediction_invalid',j0,j)
        if w==0 or j0-j<max(1e-7,self.config['relative_margin']*j0):return self.reset(baseline,'cost',j0,j)
        self.good+=1
        if self.good<3:
            self.weight=0.
            return baseline,0.,'persistence',j0,j
        self.weight=w
        return u,w,'earned',j0,j
