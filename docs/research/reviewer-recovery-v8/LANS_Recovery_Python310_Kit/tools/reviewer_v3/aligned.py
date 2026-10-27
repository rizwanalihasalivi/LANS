import boot3
import json
import math
import numpy as np
from numba import njit
from filtered import FilteredController
from environment import CausalEnv
from supervisor import observation

P=json.loads((boot3.HERE/'protocol.json').read_text())


@njit(cache=True)
def trajectory_cost(z0,actuator,speed,ks,gain,filtered,residual,weight):
    z=z0.copy();delta=actuator;f=filtered;cost=0.;alpha=1-math.exp(-.01/.3)
    for i in range(100):
        d=speed*i*.01
        k=ks[0]+(ks[1]-ks[0])*d/10 if d<10 else (ks[1]+(ks[2]-ks[1])*(d-10)/10 if d<20 else ks[2])
        vyref=(1.4*speed-1650*1.2*speed**3/(2.6*80000))*k
        target=np.array([0.,vyref,-vyref/speed,speed*k])
        ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*speed*speed)*k
        base=max(-.5,min(.5,ff-np.dot(gain,z-target)))
        if i:f+=alpha*(residual-f)
        u=max(-.5,min(.5,base+weight*f));rate=max(-.35,min(.35,(u-delta)/.05));delta+=.01*rate
        ey,vy,ep,r=z
        front=80000*(delta-(vy+1.2*r)/speed);rear=80000*(-(vy-1.4*r)/speed)
        z+=.01*np.array([vy+speed*ep,(front+rear)/1650-speed*r,r-speed*k,(1.2*front-1.4*rear)/4224])
        cost+=.01*((z[0]/.5)**2+.2*(z[2]/.1)**2+.2*(rate/.35)**2+.005*(u/.5)**2)
    return cost


class AlignedController(FilteredController):
    def __init__(self):super().__init__('age_filtered')
    def choose(self,t,baseline,estimate,actuator,speed,curvature,gain):
        previous=self.filtered;prior_weight=self.weight;prior_good=self.good
        command,reason=super().choose(t,baseline,estimate,actuator,speed,curvature,gain)
        if reason!='age_filtered':return command,reason
        residual=float(np.clip(self.packet[2],-.08,.08));age=t-self.packet[1]
        self.filtered=previous+(1-math.exp(-.01/.3))*(residual-previous)
        cap=.25*math.exp(-.8*max(0.,age*1000-5.));weight=min(cap,prior_weight+.05)
        ks=self.previews.copy();ks[0]=curvature
        base=trajectory_cost(estimate,actuator,speed,ks,gain,self.filtered,residual,0.)
        candidate=trajectory_cost(estimate,actuator,speed,ks,gain,self.filtered,residual,weight)
        self.last_costs=(base,candidate)
        reason='accepted'
        if not np.isfinite([base,candidate]).all():reason='prediction_invalid';self.filtered=0.
        elif base-candidate<max(1e-7,.001*base):reason='cost'
        else:
            self.good=prior_good+1
            if self.good<3:reason='recovery'
        if reason!='accepted':
            self.weight=0.;self.last_command=baseline
            if reason!='recovery':self.good=0
            return baseline,reason
        self.weight=weight;self.last_command=float(np.clip(baseline+weight*self.filtered,-.5,.5))
        return self.last_command,reason


class AlignedEnv(CausalEnv):
    def __init__(self,pair=0,slot=0,seed=3701,case=None,baseline=False):
        self.baseline_only=baseline
        super().__init__(pair,slot,seed,mode='lqr',case=case)
    def reset(self,**kwargs):
        super().reset(**kwargs)
        if not self.fixed_case:
            # Override only training namespace; scenario stream remains seeded.
            self.noise_id=P['training']['noise_base']+self.pair*1000000+self.slot*10000+self.index
            self.noise=np.random.default_rng(self.noise_id).normal(0,[.03,math.radians(.17),.01,.1],(self.horizon+1,4))
            self.estimate=np.zeros(4);self.cov=np.eye(4)*.01;self.previous=np.zeros(4);self._sense()
        if not self.baseline_only:self.ctrl=AlignedController()
        self.ctrl.previews=self.obs[6:9].astype(float)*.02
        self.obs=observation(self.state,self.estimate,self.measured_speed,self.ctrl.previews,self.ctrl,self.tick*.01)
        return self.obs.copy(),{'noise_id':self.noise_id}
    def _sense(self):
        super()._sense()
        self.ctrl.previews=self.obs[6:9].astype(float)*.02
    def step_residual(self,residual):
        obs,_,failed,done,row=super().step_residual(residual)
        reward=-(row['lateral_error']/.5)**2-.2*(row['heading_error']/.1)**2-.2*(row['steering_rate']/.35)**2-.005*(row['command']/.5)**2-10*failed
        row.update(reward=reward,filtered_residual=getattr(self.ctrl,'filtered',0.),
            predicted_base=self.ctrl.last_costs[0],predicted_candidate=self.ctrl.last_costs[1])
        return obs,float(reward),failed,done,row
