"""Timestamp validation, per-neighbor uncertainty, TTC and route conflict supervision."""
from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class Packet:
    vehicle_id: str
    sequence: int
    observed_s: float
    state: tuple


class Inbox:
    def __init__(self):
        self.latest = {}
        self.rejected = 0

    def ingest(self, packet, now):
        old = self.latest.get(packet.vehicle_id)
        valid = (type(packet.sequence) is int and packet.sequence >= 0
                 and isinstance(packet.vehicle_id,str) and bool(packet.vehicle_id)
                 and math.isfinite(packet.observed_s) and 0 <= packet.observed_s <= now+1e-9
                 and len(packet.state)==6 and np.isfinite(packet.state).all()
                 and packet.state[3]>=0)
        if old is not None:
            valid &= packet.sequence>old.sequence and packet.observed_s>=old.observed_s
        if not valid:
            self.rejected += 1
            return False
        self.latest[packet.vehicle_id] = packet
        return True


def velocity(state):
    _,_,heading,speed,vy,_ = state
    return np.array([speed*math.cos(heading)-vy*math.sin(heading),
                     speed*math.sin(heading)+vy*math.cos(heading)])


def extrapolate(state, age):
    z = np.array(state,dtype=float)
    z[:2] += velocity(z)*age
    return z


def contact_time(ego, other, radius):
    p = np.asarray(other[:2])-ego[:2]; v = velocity(other)-velocity(ego)
    c = float(p@p-radius**2)
    if c<=0:return 0.
    a,b = float(v@v),float(2*p@v)
    discriminant = b*b-4*a*c
    if a<1e-10 or b>=0 or discriminant<0:return math.inf
    return max(0.,(-b-math.sqrt(discriminant))/(2*a))


def conflict_time(ego, other, radius):
    """Intersect CV route rays and check radius-expanded occupancy intervals."""
    ve,vn = velocity(ego),velocity(other)
    matrix = np.column_stack((ve,-vn))
    if abs(np.linalg.det(matrix))<1e-6:return math.inf
    te,tn = np.linalg.solve(matrix,np.asarray(other[:2])-ego[:2])
    if te<0 or tn<0:return math.inf
    de,dn = radius/max(.1,np.linalg.norm(ve)),radius/max(.1,np.linalg.norm(vn))
    if max(te-de,tn-dn)>min(te+de,tn+dn):return math.inf
    # The overlap starts when BOTH expanded occupancy intervals have begun.
    # The earlier individual start can falsely report an immediate conflict.
    return float(max(0.,max(te-de,tn-dn)))


@dataclass
class Risk:
    state: str
    ttc: float
    clearance: float
    critical_id: str
    max_age: float
    missing: tuple
    vehicles: tuple


class Supervisor:
    THRESHOLDS = {'following':(1.5,3.),'merge':(1.8,3.5),
                  'crossing':(2.,4.),'curved':(1.5,3.)}

    def __init__(self, cfg, scenario):
        self.cfg = cfg; self.scenario = scenario; self.state = 'SAFE'

    def assess(self, ego, inbox, expected, now, application_s):
        vehicles=[];missing=[];ages=[];critical='';minimum=math.inf;clearance=math.inf
        for name in sorted(expected):
            packet = inbox.latest.get(name)
            if packet is None or now-packet.observed_s>self.cfg.traffic_ttl+1e-9:
                missing.append(name);continue
            age = max(0.,application_s-packet.observed_s);ages.append(age)
            other = extrapolate(packet.state,age)
            uncertainty = self.cfg.uncertainty_rate*age
            radius = 2*self.cfg.vehicle_radius+self.cfg.buffer+uncertainty
            distance = float(np.linalg.norm(other[:2]-ego[:2])-radius)
            t = min(contact_time(ego,other,radius),conflict_time(ego,other,radius))
            if (t,distance)<(minimum,clearance):minimum=t;critical=name
            clearance = min(clearance,distance)
            vehicles.append((name,other,uncertainty))
        danger,warning = self.THRESHOLDS[self.scenario]
        # Hysteresis only holds a state while the risk remains near its boundary.
        if missing or clearance<=0 or minimum<=danger+(0.4 if self.state=='DANGER' else 0.):
            self.state='DANGER'
        elif minimum<=warning+(0.4 if self.state!='SAFE' else 0.):
            self.state='WARNING'
        else:self.state='SAFE'
        return Risk(self.state,minimum,clearance,critical,max(ages,default=0.),tuple(missing),tuple(vehicles))

    def acceleration(self, nominal, risk):
        if risk.state=='DANGER':return min(nominal,-self.cfg.max_brake)
        if risk.state=='WARNING':
            _,warning = self.THRESHOLDS[self.scenario]
            return min(nominal,-self.cfg.max_brake*.5*max(0.,1-risk.ttc/warning))
        return nominal
