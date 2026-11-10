"""Bounded longitudinal recourse when the historical braking fallback fails.

Only original-age local/neighbor packets and committed FIFO inputs are used.
The unchanged uncertainty padding is retained. If no padded rollout is feasible,
a physical-envelope-positive, strictly better emergency can replace an already
infeasible brake. Such a result is explicitly NOT a safety certificate.
"""
import math
import numpy as np
from numba import njit
from tools.unified_control_v4.kernels import step, lqr, geometry
from integrations.unified_lans.traffic import velocity, extrapolate


@njit(cache=True)
def margins(initial, acceleration, first, previous, applied, pending, delay,
            stiffness, gains, route, feedback, vehicles, dt, cruise,angle,rate,radius,buffer,uncertainty):
    z=initial.copy();minimum=1e9;physical=1e9;steering=previous
    for i in range(80):
        t=i*dt
        if t < delay-1e-9:
            u=applied[0];a=applied[1]
            for j in range(len(pending)):
                if pending[j,0] <= t+1e-9:u=pending[j,1];a=pending[j,2]
        else:
            base=first if abs(t-delay)<1e-8 else lqr(z,gains,int(route[0]),route[1],route[2],route[3],feedback)
            u=min(angle,max(-angle,min(steering+rate*dt,max(steering-rate*dt,base))))
            a=acceleration if z[3]<cruise+4. else min(0.,acceleration)
        old=z.copy();z=step(z,u,a,dt,stiffness);steering=u
        y,_,_=geometry(z[0],int(route[0]),route[1],route[2],route[3])
        minimum=min(minimum,1.75-abs(z[1]-y));physical=min(physical,1.75-abs(z[1]-y))
        for n in vehicles:
            vx=n[3]*math.cos(n[2])-n[4]*math.sin(n[2]);vy=n[3]*math.sin(n[2])+n[4]*math.cos(n[2])
            p0=old[:2]-(n[:2]+np.array([vx,vy])*t)
            p1=z[:2]-(n[:2]+np.array([vx,vy])*(t+dt));delta=p1-p0
            q=max(0.,min(1.,-np.dot(p0,delta)/max(1e-15,np.dot(delta,delta))))
            distance=np.sqrt(np.sum((p0+q*delta)**2))
            # The bridge allowance is an engineering model check, not an ODE proof.
            base_radius=2*radius+buffer+n[6]+20.*dt*dt/8
            physical=min(physical,distance-base_radius)
            minimum=min(minimum,distance-base_radius-uncertainty*(t+dt))
    return minimum,physical


def choose(owner,now,command,nominal):
    ego=owner.inbox.latest.get('ego')
    if ego is None or not 0<=now-ego.observed_s<=owner.cfg.ego_ttl+1e-9:return None
    vehicles=[]
    for name in sorted(owner.expected):
        packet=owner.inbox.latest.get(name)
        if packet is None or not 0<=now-packet.observed_s<=owner.cfg.traffic_ttl+1e-9:return None
        age=now-packet.observed_s
        vehicles.append([*extrapolate(packet.state,age),owner.cfg.uncertainty_rate*age])
    z=owner.reconstruct(now)
    if z is None:return None
    pending=np.array([[due-now,c.steering,c.accel] for due,c in owner.pending[:-1]],float).reshape(-1,3)
    traffic=np.array(vehicles,float).reshape(-1,7)
    center=owner.stiffness_estimate if owner.adaptive else 1.
    width=owner.stiffness_uncertainty if owner.adaptive else .3
    models=sorted(set([max(.7,center-width),center,min(1.3,center+width)]))
    results=[]
    cfg=owner.cfg
    for a in (-cfg.max_brake,-cfg.max_brake/2,-min(1.,cfg.max_brake),0.,cfg.max_accel/2,cfg.max_accel):
        scores=[margins(z,a,command.steering,owner.applied.steering,
            np.array([owner.applied.steering,owner.applied.accel]),pending,owner.delay,
            model,owner._gains,owner._route,owner.feedback_stiffness,traffic,cfg.dt,owner.target_speed,
            cfg.steering_limit,cfg.steering_rate,cfg.vehicle_radius,cfg.buffer,cfg.uncertainty_rate)
            for model in models]
        results.append(dict(accel=a,margin=min(x[0] for x in scores),physical_margin=min(x[1] for x in scores)))
    brake=results[0]
    feasible=[r for r in results if r['margin']>=0]
    if feasible:
        best=min(feasible,key=lambda r:(abs(r['accel']-nominal),-r['margin']))
        mode='padded_rollout_feasible'
    else:
        admissible=[r for r in results if r['physical_margin']>0 and r['margin']>brake['margin']+.05]
        if not admissible:return dict(selected=brake,mode='no_feasible_recourse',candidates=results)
        best=max(admissible,key=lambda r:r['margin']);mode='uncertified_emergency_improvement'
    return dict(selected=best,mode=mode,candidates=results)
