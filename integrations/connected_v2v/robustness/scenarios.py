"""Fixed broad-validation fixtures, kept outside the observation-only controller."""
from dataclasses import dataclass
import math
import numpy as np
from integrations.connected_v2v.autonomy.controller import Detection, Scan
from integrations.connected_v2v.autonomy.road import Road
from integrations.unified_lans.traffic import velocity


@dataclass(frozen=True)
class Profile:
    radius: float = 0.
    dense: bool = False
    nonconnected: bool = False
    range_noise: float = .15
    bearing_noise: float = .002
    rate_noise: float = .08
    miss: float = .10
    burst: bool = False
    brake: bool = False
    radio_blackout: bool = False
    radar_blackout: bool = False
    latency: float = .05
    latency_jitter: float = 0.


PROFILES = {
    'curved': Profile(radius=800.),
    'dense_curved': Profile(radius=800.,dense=True,nonconnected=True),
    'noisy_nonconnected': Profile(nonconnected=True,range_noise=.30,bearing_noise=.003,
                                  rate_noise=.15,miss=.20,latency=.10,latency_jitter=.02),
    'burst_misses': Profile(radius=800.,nonconnected=True,burst=True),
    'occlusion_brake': Profile(dense=True,nonconnected=True,brake=True,miss=.15),
    'dual_blackout': Profile(radius=800.,radio_blackout=True,radar_blackout=True),
    'v2v_blackout': Profile(radio_blackout=True),
    'combined': Profile(radius=800.,dense=True,nonconnected=True,brake=True,burst=True,
                        radio_blackout=True,range_noise=.30,bearing_noise=.003,
                        rate_noise=.15,miss=.20,latency=.10,latency_jitter=.02),
}
DEV_SEEDS = (701,709,719)
VALIDATION_SEEDS = (1009,1013,1019,1021,1031,1033,1039,1049,1051,1061)
SPEEDS = (8.,12.,16.)
NATIVE_CASES = tuple(name for name in PROFILES if name not in ('v2v_blackout','combined'))


def ramp(t,start,duration):
    return min(max(t-start,0.),duration)


def integral_ramp(t,start,duration):
    q=max(0.,t-start)
    return .5*min(q,duration)**2+duration*max(0.,q-duration)


def smooth(t,start,end):
    q=min(1.,max(0.,(t-start)/(end-start)))
    return q*q*(3-2*q), 6*q*(1-q)/(end-start) if start<t<end else 0.


def maneuver(t, native=False):
    enter, denter=smooth(t,6. if native else 4.,9. if native else 6.)
    leave, dleave=smooth(t,20.,23. if native else 22.)
    return 3.5*(1-enter+leave),3.5*(-denter+dleave)


def intruder_speed(t,speed,brake):
    return speed-2.-(2.5*ramp(t,12.,1.2)-ramp(t,14.,3.) if brake else 0.)


class Scene:
    def __init__(self,case,speed,seed):
        self.profile=PROFILES[case]
        self.speed=float(speed)
        self.road=Road(self.profile.radius)
        rng=np.random.default_rng(np.random.SeedSequence([seed,7]))
        self.leader_s=70.+float(rng.uniform(-2.,2.))
        self.intruder_s=36.+float(rng.uniform(-2.,2.))
        self.offsets={'leader':self.leader_s,'intruder':self.intruder_s}
        if self.profile.dense:
            self.offsets.update({f'adjacent-{i}':offset for i,offset in enumerate((-70.,-40.,65.,95.,125.))})
        self.connected=tuple(name for name in self.offsets if not (
            self.profile.nonconnected and (name=='intruder' or name in ('adjacent-0','adjacent-2','adjacent-4'))))

    def states(self,t):
        result={}
        for name,offset in self.offsets.items():
            s, d, speed, lateral=offset+self.speed*t,0.,self.speed,0.
            if name.startswith('adjacent'):
                d=3.5
                if name in ('adjacent-0','adjacent-1'):
                    speed=self.speed-2.*ramp(t,18.,1.)
                    s=offset+self.speed*t-2.*integral_ramp(t,18.,1.)
            if name=='intruder':
                d,lateral=maneuver(t)
                speed=intruder_speed(t,self.speed,self.profile.brake)
                s=offset+(self.speed-2.)*t
                if self.profile.brake:
                    s-=2.5*integral_ramp(t,12.,1.2)-integral_ramp(t,14.,3.)
            position=self.road.position(s,d)
            heading=s/self.road.radius if self.road.radius else 0.
            tangential=speed*(1-d/self.road.radius) if self.road.radius else speed
            result[name]=np.array([*position,heading,tangential,lateral,speed/self.road.radius if self.road.radius else 0.])
        return result


def ray_hits(start,end,box):
    """Finite centre ray intersects an oriented vehicle bounding box."""
    c,s=math.cos(box[2]),math.sin(box[2])
    rotation=np.array([[c,s],[-s,c]])
    origin=rotation@(np.array(start)-box[:2])
    direction=rotation@(np.array(end)-start)
    lo,hi=0.,1.
    for coordinate,delta,half in zip(origin,direction,(2.3,.9)):
        if abs(delta)<1e-12:
            if abs(coordinate)>half:return False
        else:
            a,b=(-half-coordinate)/delta,(half-coordinate)/delta
            lo,hi=max(lo,min(a,b)),min(hi,max(a,b))
            if lo>hi:return False
    return lo<=hi and hi>0 and lo<1.


def radar_scan(sequence,now,ego,traffic,profile,rng):
    returns=[]
    for name,state in traffic.items():
        delta=state[:2]-ego[:2]
        distance=float(np.linalg.norm(delta))
        bearing=math.atan2(delta[1],delta[0])-ego[2]
        bearing=math.atan2(math.sin(bearing),math.cos(bearing))
        if not .5<distance<119. or abs(bearing)>.33:
            continue
        occluded=any(other!=name and np.linalg.norm(z[:2]-ego[:2])<distance and
                     ray_hits(ego[:2],state[:2],z) for other,z in traffic.items())
        missed=rng.random()<profile.miss or profile.burst and 10.<=now<11.
        if occluded or missed:
            continue
        rate=float((velocity(state)-velocity(ego))@(delta/distance))
        values=(distance+float(rng.normal(0.,profile.range_noise)),
                bearing+float(rng.normal(0.,profile.bearing_noise)),
                rate+float(rng.normal(0.,profile.rate_noise)))
        try:returns.append(Detection(*values))
        except ValueError:pass  # Out-of-envelope returns are unavailable, never clamped into certainty.
    rng.shuffle(returns)
    return Scan(sequence,now,tuple(ego),tuple(returns),complete=False)
