import boot
import json
import math
import numpy as np
from numba import njit
from supervisor import Controller

P=json.loads((boot.HERE/'protocol.json').read_text())


@njit(cache=True)
def rate_cost(estimate,actuator,command,speed,curvature,gain,previews,preview):
    z=estimate.copy();delta=actuator;cost=0.
    for i in range(20):
        distance=speed*i*.01
        k=curvature
        if preview:
            if distance<10:k=curvature+(previews[1]-curvature)*distance/10
            elif distance<20:k=previews[1]+(previews[2]-previews[1])*(distance-10)/10
            else:k=previews[2]
        vyref=(1.4*speed-1650*1.2*speed**3/(2.6*80000))*k
        target=np.array([0.,vyref,-vyref/speed,speed*k])
        ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*speed**2)*k
        u=command if i<5 else max(-.5,min(.5,ff-np.dot(gain,z-target)))
        rate=max(-.35,min(.35,(u-delta)/.05));delta+=.01*rate
        ey,vy,ep,r=z
        front=80000*(delta-(vy+1.2*r)/speed);rear=80000*(-(vy-1.4*r)/speed)
        z+=.01*np.array([vy+speed*ep,(front+rear)/1650-speed*r,r-speed*k,(1.2*front-1.4*rear)/4224])
        cost+=.01*((z[0]/.5)**2+.2*(z[2]/.1)**2+.01*((z[3]-speed*k)/.2)**2
                    +.001*(u/.5)**2+.02*(rate/.35)**2)
    return cost+.1*((z[0]/.5)**2+.2*(z[2]/.1)**2)


class FilteredController(Controller):
    def __init__(self,profile):
        super().__init__('latency' if profile=='age_original' else 'predictive')
        self.profile=profile;self.filtered=0.;self.previews=np.zeros(3)
        self.psf=None;self.tick=0

    def choose(self,t,baseline,estimate,actuator,speed,curvature,gain):
        self.tick+=1
        if self.profile=='age_original':
            out=super().choose(t,baseline,estimate,actuator,speed,curvature,gain)
            self.filtered=self.packet[2] if self.packet and self.weight else 0.
            return out
        self.last_costs=(math.nan,math.nan)
        def reject(reason,clear=True):
            if clear:self.filtered=0.
            self.weight=0.;self.good=0;self.last_command=baseline
            return baseline,reason
        if self.packet is None:return reject('missing')
        seq,observed,residual=self.packet;age=t-observed
        if not np.isfinite([t,baseline,observed,residual,actuator,speed,curvature,*estimate]).all():return reject('nonfinite')
        if age<0 or age>=.05-1e-12:return reject('age')
        if seq<self.last_sequence:return reject('sequence')
        self.last_sequence=seq
        if abs(estimate[0])>1.5 or abs(estimate[2])>.25:return reject('envelope')
        if self.profile=='nominal_psf':
            desired=float(np.clip(baseline+.5*residual,-.5,.5))
            command,status=self.psf.command(estimate,actuator,speed,curvature,desired,baseline,self.tick)
            self.weight=0. if command==baseline else .5
            self.filtered=residual;self.last_command=command
            return command,'psf_'+status
        alpha=1-math.exp(-.01/.1)
        self.filtered+=alpha*(float(np.clip(residual,-.08,.08))-self.filtered)
        if self.profile=='age_filtered':
            self.weight=.25*math.exp(-.8*max(0.,age*1000-5.))
            self.last_command=float(np.clip(baseline+self.weight*self.filtered,-.5,.5))
            return self.last_command,'age_filtered'
        preview=self.profile=='preview_filtered'
        base=rate_cost(estimate,actuator,baseline,speed,curvature,gain,self.previews,preview)
        best=base;selected=0.;command=baseline;fresh=min(1.,max(0.,(.05-age)/.04))
        for cap in (.1,.25):
            weight=min(cap*fresh,self.weight+.05)
            candidate=float(np.clip(baseline+weight*self.filtered,-.5,.5))
            cost=rate_cost(estimate,actuator,candidate,speed,curvature,gain,self.previews,preview)
            if cost<best:best,selected,command=cost,weight,candidate
        self.last_costs=(base,best)
        if not np.isfinite([base,best]).all():return reject('prediction_invalid')
        if selected==0 or base-best<max(1e-7,.01*base):return reject('cost',False)
        self.good+=1
        if self.good<3:self.weight=0.;self.last_command=baseline;return baseline,'recovery'
        self.weight=selected;self.last_command=command
        return command,'accepted'
