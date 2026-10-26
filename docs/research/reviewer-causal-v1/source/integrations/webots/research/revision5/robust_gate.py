"""Experimental conservative gate using a declared nonlinear model bank.

Only estimated state, observed curvature/speed and actuator feedback enter.
The bank is fixed, not the episode's hidden parameters. Not a safety proof.
"""
import math
import numpy as np
from numba import njit
from bootstrap import RESEARCH
from gating import Gate
from plant import advance


@njit(cache=True)
def bank_cost(estimate,actuator,command,speed,kappa,gain,mu,stiffness):
    # Local parabolic road approximates observed curvature; no privileged map preview.
    z=np.array([0.,estimate[0],estimate[2],estimate[1],estimate[3],actuator]);cost=0.
    for i in range(20):
        x=z[0];slope=kappa*x;heading=math.atan(slope);curve=kappa/(1+slope*slope)**1.5
        vyref=(1.4*speed-1650*1.2*speed**3/(2.6*80000))*curve
        est=np.array([z[1]-.5*kappa*x*x,z[3],z[2]-heading,z[4]])
        target=np.array([0.,vyref,-vyref/speed,speed*curve])
        ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*speed**2)*curve
        u=command if i<5 else max(-.5,min(.5,ff-np.dot(gain,est-target)))
        z=advance(z,u,speed,mu,stiffness)
        x=z[0];ey=z[1]-.5*kappa*x*x;ep=z[2]-math.atan(kappa*x)
        curve=kappa/(1+(kappa*x)**2)**1.5
        cost+=.01*((ey/.5)**2+.2*(ep/.1)**2+.01*((z[4]-speed*curve)/.2)**2+.001*(u/.5)**2)
    return cost+.1*((ey/.5)**2+.2*(ep/.1)**2)


class RobustGate(Gate):
    bank=((.9,1.),(.9,.65),(.6,1.),(.6,.65))

    def choose(self,t,baseline,packet,estimate,actuator,speed,curvature,gain,role):
        # Reuse finite/age/sequence/envelope checks; independently score candidates.
        if packet is None:return self.reset(baseline,'missing')
        seq,observed,action=packet
        if not np.isfinite([t,baseline,observed,action,actuator,speed,curvature,*estimate]).all():return self.reset(baseline,'nonfinite')
        age=t-observed
        if age<0 or age>=.05:return self.reset(baseline,'age')
        if seq<self.last_sequence:return self.reset(baseline,'sequence')
        self.last_sequence=seq
        if abs(estimate[0])>1.5 or abs(estimate[2])>.25 or speed<=0:return self.reset(baseline,'envelope')
        candidate=float(np.clip(baseline+np.clip(action,-.08,.08),-.5,.5)) if role=='residual' else float(np.clip(action,-.5,.5))
        fresh=max(0.,min(1.,(.05-age)/.04))
        costs=[bank_cost(estimate,actuator,baseline,speed,curvature,gain,mu,stiffness) for mu,stiffness in self.bank]
        best=None
        for limit in (.1,.25,.5):
            w=min(limit*fresh,self.weight+.05);u=(1-w)*baseline+w*candidate
            values=[bank_cost(estimate,actuator,u,speed,curvature,gain,mu,stiffness) for mu,stiffness in self.bank]
            margins=[(a-b)/max(a,1e-4) for a,b in zip(costs,values)]
            if all(math.isfinite(v) for v in costs+values) and all(a-b>=max(1e-7,self.config['relative_margin']*a) for a,b in zip(costs,values)):
                score=min(margins)
                if best is None or score>best[0]:best=(score,w,u,values)
        if best is None:return self.reset(baseline,'cost',sum(costs)/4,sum(costs)/4)
        _,w,u,values=best;self.good+=1
        if self.good<3:
            self.weight=0.;return baseline,0.,'persistence',sum(costs)/4,sum(values)/4
        self.weight=w
        return u,w,'earned',sum(costs)/4,sum(values)/4
