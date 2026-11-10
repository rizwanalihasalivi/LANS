"""Geometric controller-family adaptations through the shared causal interface.

These are Stanley and pure-pursuit adaptations, not full paper reproductions.
See BASELINE_PROVENANCE.md for equations, source evidence and changed assumptions.
"""
import math
import numpy as np
from numba import njit
from models.bicycle_model import VEHICLE_PARAMS
from tools.unified_control_v4.control import Controller as Previous
from tools.unified_control_v4.kernels import geometry,step

LF=float(VEHICLE_PARAMS['lf']);LR=float(VEHICLE_PARAMS['lr']);WHEELBASE=LF+LR
METHODS={'stanley':0,'pure_pursuit':1}
PARAMETERS={'stanley':(.5,1.,2.),'pure_pursuit':(.1,.3,.5)}


@njit(cache=True)
def nearest_x(x,y,route):
    """Bounded local normal projection onto the shared analytic road graph."""
    q=x
    for _ in range(8):
        ref,h,k=geometry(q,int(route[0]),route[1],route[2],route[3])
        d=math.tan(h);dd=k*(1+d*d)**1.5
        derivative=1+d*d+(ref-y)*dd
        if derivative<=1e-8:break
        change=(q-x+(ref-y)*d)/derivative
        q-=min(5.,max(-5.,change))
    return q


@njit(cache=True)
def steering(state,route,method,parameter):
    x,y,psi,v=state[:4]
    if method==0:
        fx=x+LF*math.cos(psi);fy=y+LF*math.sin(psi)
        target_x=nearest_x(fx,fy,route)
        target_y,h,_=geometry(target_x,int(route[0]),route[1],route[2],route[3])
        error=math.sin(h)*(fx-target_x)-math.cos(h)*(fy-target_y)
        heading=math.atan2(math.sin(h-psi),math.cos(h-psi))
        command=heading+math.atan2(parameter*error,max(.1,v))
    else:
        rx=x-LR*math.cos(psi);ry=y-LR*math.sin(psi)
        near=nearest_x(rx,ry,route);lookahead=2.+parameter*max(0.,v)
        lo=near;hi=near+lookahead
        for _ in range(8):
            ref,_,_=geometry(hi,int(route[0]),route[1],route[2],route[3])
            if (hi-rx)**2+(ref-ry)**2>=lookahead**2:break
            hi=near+2*(hi-near)
        ref,_,_=geometry(lo,int(route[0]),route[1],route[2],route[3])
        if (lo-rx)**2+(ref-ry)**2<lookahead**2:
            for _ in range(24):
                mid=(lo+hi)/2;ref,_,_=geometry(mid,int(route[0]),route[1],route[2],route[3])
                if (mid-rx)**2+(ref-ry)**2<lookahead**2:lo=mid
                else:hi=mid
        target_y,_,_=geometry(hi,int(route[0]),route[1],route[2],route[3])
        dx=hi-rx;dy=target_y-ry;body_y=-math.sin(psi)*dx+math.cos(psi)*dy
        command=math.atan2(2*WHEELBASE*body_y,max(1e-12,dx*dx+dy*dy))
    return min(.5,max(-.5,command))


@njit(cache=True)
def predict_geometric(z,first,accel,previous,dt,horizon,stiffness,route,npcs,radius,
                      buffer,uncertainty_rate,angle,rate,method,parameter):
    state=z.copy();total=0.;margin=1e9
    for i in range(int(math.ceil(horizon/dt))):
        proposed=first if i==0 else steering(state,route,method,parameter)
        u=min(angle,max(-angle,min(previous+rate*dt,max(previous-rate*dt,proposed))))
        state=step(state,u,accel,dt,stiffness)
        ref,h,_=geometry(state[0],int(route[0]),route[1],route[2],route[3])
        ey=state[1]-ref;ep=math.atan2(math.sin(state[2]-h),math.cos(state[2]-h))
        total+=dt*(8*ey*ey+2*ep*ep+.03*u*u+.02*((u-previous)/dt)**2)
        margin=min(margin,1.75-abs(ey));time=(i+1)*dt
        for n in npcs:
            vx=n[3]*math.cos(n[2])-n[4]*math.sin(n[2]);vy=n[3]*math.sin(n[2])+n[4]*math.cos(n[2])
            dx=n[0]+vx*time-state[0];dy=n[1]+vy*time-state[1]
            clearance=math.sqrt(dx*dx+dy*dy)-2*radius-buffer-n[6]-uncertainty_rate*time
            margin=min(margin,clearance)
        previous=u
    return total,margin


class Controller(Previous):
    """Same packet/FIFO/forecast/supervisor/actuator policy, geometric steering."""
    def __init__(self,*args,method='stanley',parameter=1.,**kwargs):
        if method not in METHODS or not math.isfinite(parameter) or parameter<=0:
            raise ValueError('Known geometric method and positive finite parameter required')
        self.method=method;self.parameter=float(parameter);self.method_id=METHODS[method]
        kwargs.update(mode='lqr',adaptive=False,mpc=False,deterministic_grid=())
        kwargs.setdefault('penalty',16.)
        super().__init__(*args,**kwargs)
        self.baseline_fn=self.geometric_command

    def geometric_command(self,state,route):
        return float(steering(np.asarray(state),self._route,self.method_id,self.parameter))

    def cost(self,z,first,residual,accel,vehicles,lifetime):
        cfg=self.cfg
        npcs=np.array([[*other,unc] for _,other,unc in vehicles],float).reshape(-1,7)
        values=[predict_geometric(z,first.steering,accel,self.issued.steering,cfg.dt,cfg.horizon,
            stiffness,self._route,npcs,cfg.vehicle_radius,cfg.buffer,cfg.uncertainty_rate,
            cfg.steering_limit,cfg.steering_rate,self.method_id,self.parameter) for stiffness in (.7,1.,1.3)]
        return float(np.mean([v[0] for v in values])),float(min(v[1] for v in values))

    def decide(self,*args,**kwargs):
        result=super().decide(*args,**kwargs)
        result.update(geometric_method=self.method,geometric_parameter=self.parameter)
        # Existing source='lqr' is the pipeline's fallback-role label. Preserve it
        # for common interface auditors; metadata identifies the actual tracker.
        return result
