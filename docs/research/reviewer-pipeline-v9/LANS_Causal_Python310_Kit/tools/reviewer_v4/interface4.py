import boot4
import copy
import json
import math
import types
import numpy as np
from aligned import AlignedController,AlignedEnv
from scalar_cost import scalar_cost

P=json.loads((boot4.HERE/'protocol.json').read_text())
# Preserve the original choose closure/super class while substituting only its
# predictor global in this isolated subclass; no frozen module is monkeypatched.
_globals=dict(AlignedController.choose.__globals__,trajectory_cost=scalar_cost)
_choose=types.FunctionType(AlignedController.choose.__code__,_globals,
    name='choose',argdefs=AlignedController.choose.__defaults__,closure=AlignedController.choose.__closure__)


class ScalarAligned(AlignedController):
    choose=_choose


class FreshController(ScalarAligned):
    def choose(self,t,baseline,estimate,actuator,speed,curvature,gain):
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
        residual=max(-.08,min(.08,float(residual)))
        self.filtered+=(1-math.exp(-.01/.3))*(residual-self.filtered)
        weight=min(.25,self.weight+.05)
        ks=self.previews.copy();ks[0]=curvature
        base=scalar_cost(estimate,actuator,speed,ks,gain,self.filtered,residual,0.)
        candidate=scalar_cost(estimate,actuator,speed,ks,gain,self.filtered,residual,weight)
        self.last_costs=(base,candidate)
        if not np.isfinite([base,candidate]).all():return reject('prediction_invalid')
        if base-candidate<max(1e-7,.001*base):return reject('cost',False)
        self.good+=1
        if self.good<3:self.weight=0.;self.last_command=baseline;return baseline,'recovery'
        self.weight=weight;self.last_command=float(np.clip(baseline+weight*self.filtered,-.5,.5))
        return self.last_command,'accepted'


class AsyncEnv(AlignedEnv):
    def __init__(self,case,source):self.source=source;super().__init__(case=case,baseline=source=='lqr')
    def reset(self,**kwargs):
        obs,info=super().reset(**kwargs)
        self.service=max(.01,self.service)  # At least one parent polling period.
        if self.source!='lqr':
            self.ctrl=ScalarAligned() if self.source=='oldage_ppo' else FreshController()
            self.ctrl.previews=self.obs[6:9].astype(float)*.02
        return obs,info


def planner(env):
    """Causal finite nominal planner; no true plant/friction/future noise input."""
    c=copy.copy(env.ctrl);c.previews=env.ctrl.previews.copy()
    command,_=c.choose(env.tick*.01,env.baseline,env.estimate,env.state[5],env.measured_speed,env.curvature,env.gain)
    # Predict one common control tick before a healthy next-tick delivery.
    speed=env.measured_speed;k=env.curvature;ey,vy,ep,r=env.estimate
    delta=env.state[5]+.01*max(-.35,min(.35,(command-env.state[5])/.05))
    front=80000*(delta-(vy+1.2*r)/speed);rear=80000*(-(vy-1.4*r)/speed)
    z=env.estimate+.01*np.array([vy+speed*ep,(front+rear)/1650-speed*r,r-speed*k,(1.2*front-1.4*rear)/4224])
    ks=np.interp(np.array([0.,10.,20.])+speed*.01,[0.,10.,20.],c.previews)
    values=[]
    for residual in (-.08,-.04,0.,.04,.08):
        f=c.filtered+(1-math.exp(-.01/.3))*(residual-c.filtered)
        cost=scalar_cost(z,delta,speed,ks,env.gain,f,residual,min(.25,c.weight+.05))
        values.append((cost,abs(residual),residual))
    return min(values)[2]
