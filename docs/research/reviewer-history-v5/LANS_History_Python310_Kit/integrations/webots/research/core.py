"""Isolated training/transfer surrogate. Does not import or modify primary models."""
import json
import math
from pathlib import Path
import numpy as np
from numba import njit
from scipy.linalg import solve_continuous_are

PROTOCOL = json.loads((Path(__file__).with_name('protocol.json')).read_text())

@njit(cache=True)
def reference(x, kind, amplitude, wavelength, phase):
    if kind == 0:
        k = 2 * math.pi / wavelength
        z = k * x + phase
        return amplitude * math.sin(z), amplitude * k * math.cos(z), -amplitude * k * k * math.sin(z)
    # Explicit development DLC: 15 / 60 / 30 / 60 / 55 = 220 m.
    if x < 15: return 0., 0., 0.
    if x < 75:
        u = (x - 15) / 60; sign = 1.
    elif x < 105: return 3.5, 0., 0.
    elif x < 165:
        u = (x - 105) / 60; sign = -1.
    else: return 0., 0., 0.
    s = 10*u**3 - 15*u**4 + 6*u**5
    d = (30*u**2 - 60*u**3 + 30*u**4) / 60
    dd = (60*u - 180*u**2 + 120*u**3) / 3600
    return (3.5*s if sign > 0 else 3.5*(1-s)), sign*3.5*d, sign*3.5*dd

@njit(cache=True)
def fiala(alpha, stiffness, load, mu):
    z = math.tan(alpha)
    bound = 3 * mu * load / stiffness
    if abs(z) >= bound: return math.copysign(mu * load, z)
    return stiffness*z - stiffness**2/(3*mu*load)*abs(z)*z + stiffness**3/(27*mu**2*load**2)*z**3

@njit(cache=True)
def derivative(s, command, speed, mu):
    # state = world x,y, heading, body lateral velocity, yaw rate, actual steering.
    x,y,psi,vy,r,delta = s
    front = fiala(delta-math.atan2(vy+1.2*r, speed), 80000., 1650.*9.81*1.4/2.6, mu)
    rear = fiala(-math.atan2(vy-1.4*r, speed), 80000., 1650.*9.81*1.2/2.6, mu)
    dd = max(-.35,min(.35,(max(-.5,min(.5,command))-delta)/.05))
    return np.array([speed*math.cos(psi)-vy*math.sin(psi), speed*math.sin(psi)+vy*math.cos(psi), r,
                     (front*math.cos(delta)+rear)/1650.-speed*r,
                     (1.2*front*math.cos(delta)-1.4*rear)/4224., dd])

@njit(cache=True)
def advance(s, command, speed, dt=.001, period=.01, mu=.9):
    value = s.copy()
    for _ in range(round(period/dt)):
        a=derivative(value,command,speed,mu)
        b=derivative(value+.5*dt*a,command,speed,mu)
        c=derivative(value+.5*dt*b,command,speed,mu)
        d=derivative(value+dt*c,command,speed,mu)
        value += dt/6*(a+2*b+2*c+d)
        value[5]=max(-.5,min(.5,value[5]))
    return value

def gain(speed):
    m, iz, lf, lr, cf, cr = 1650.,4224.,1.2,1.4,80000.,80000.
    v=float(speed)
    a=np.array([[0,1,v,0],[0,-(cf+cr)/(m*v),0,(cr*lr-cf*lf)/(m*v)-v],
                [0,0,0,1],[0,(cr*lr-cf*lf)/(iz*v),0,-(cf*lf*lf+cr*lr*lr)/(iz*v)]])
    b=np.array([[0],[cf/m],[0],[cf*lf/iz]])
    p=solve_continuous_are(a,b,np.diag(PROTOCOL['lqr_Q']),np.array([[PROTOCOL['lqr_R']]]))
    return (b.T@p/PROTOCOL['lqr_R']).ravel()

GAINS={v:gain(v) for v in (15,20,25)}

def path_values(x,path):
    y,d,dd=reference(x,*path)
    return y,math.atan(d),dd/(1+d*d)**1.5

class Sensor:
    """Linear Kalman state estimator, using only noisy lateral/heading/yaw observations."""
    def __init__(self, seed, noise=1., delay_steps=0):
        self.rng=np.random.default_rng(seed); self.noise=noise; self.delay_steps=delay_steps
        self.estimate=None; self.cov=np.eye(4)*.01; self.queue=[]
        self.h=np.array([[1.,0,0,0],[0,0,1.,0],[0,0,0,1.]])
        self.measurement_cov=np.diag(np.array([.03,math.radians(.17),.01])**2*max(noise,.01)**2)
        self.process_cov=np.diag([1e-7,1e-4,1e-8,1e-5])
    def measure(self,state,speed,path):
        y,heading,kappa=path_values(state[0],path)
        scales=np.array([.03,math.radians(.17),.01,.1])*self.noise
        z=np.array([state[1]-y,state[2]-heading,state[4],speed])+self.rng.normal(0,scales)
        self.queue.append(z)
        z=self.queue[max(0,len(self.queue)-1-self.delay_steps)].copy()
        if len(self.queue)>self.delay_steps+1:self.queue.pop(0)
        v=max(5.,z[3]);m=1650.;iz=4224.;cf=cr=80000.;lf=1.2;lr=1.4
        a=np.array([[0,1,v,0],[0,-(cf+cr)/(m*v),0,(cr*lr-cf*lf)/(m*v)-v],
                    [0,0,0,1],[0,(cr*lr-cf*lf)/(iz*v),0,-(cf*lf*lf+cr*lr*lr)/(iz*v)]])
        ad=np.eye(4)+.01*a;b=np.array([0,cf/m,0,cf*lf/iz])*.01
        if self.estimate is None:self.estimate=np.array([z[0],0.,z[1],z[2]])
        else:self.estimate=ad@self.estimate+b*state[5]+np.array([0,0,-v*kappa*.01,0])
        self.cov=ad@self.cov@ad.T+self.process_cov
        innovation_cov=self.h@self.cov@self.h.T+self.measurement_cov
        kalman=np.linalg.solve(innovation_cov,(self.cov@self.h.T).T).T
        self.estimate += kalman@(z[:3]-self.h@self.estimate)
        self.cov=(np.eye(4)-kalman@self.h)@self.cov
        ey,vy,ep,r=self.estimate
        previews=[path_values(state[0]+distance,path)[2] for distance in (0,10,20)]
        obs=np.array([ey/3,ep/.3,(vy+v*ep)/5,r/.5,v/25,state[5]/.5,
                      previews[0]/.02,previews[1]/.02,previews[2]/.02],dtype=np.float32)
        return obs,self.estimate.copy(),kappa

def lqr(estimates,speed,kappa):
    # Common Q/R and predefined speed-specific gains; steady-state feedforward.
    ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*speed**2)*kappa
    return float(np.clip(-GAINS[int(speed)]@estimates+ff,-.5,.5))

class Supervisor:
    def __init__(self):self.weight=0.;self.good_since=None;self.last_sequence=-1
    def fuse(self, t, baseline, output, estimates):
        reason='missing'; target=0.
        if output is not None:
            seq,observed,angle=output
            age=t-observed
            finite=math.isfinite(angle) and math.isfinite(age)
            envelope=abs(estimates[0])<=1.5 and abs(estimates[2])<=.25
            if not finite:reason='nonfinite'
            elif age<0 or age>=.05:reason='age'
            elif seq<self.last_sequence:reason='out_of_order'
            elif not envelope:reason='envelope'
            else:
                self.last_sequence=seq; reason='accept'
                target=.7*max(0.,min(1.,(.05-age)/.04))
        if reason!='accept':
            self.weight=0.;self.good_since=None
            return baseline,0.,reason
        if abs(estimates[0])>.75 or abs(estimates[2])>.12:
            self.good_since=None; self.weight=min(self.weight,target)
        else:
            if self.good_since is None:self.good_since=t
            if t-self.good_since>=.1:self.weight=min(target,self.weight+.014)
        # Explicit branch avoids NaN*0. Clip complete PPO action before fusion.
        if self.weight==0:return baseline,0.,'recovering'
        return float(np.clip(self.weight*np.clip(output[2],-.5,.5)+(1-self.weight)*baseline,-.5,.5)),self.weight,reason
