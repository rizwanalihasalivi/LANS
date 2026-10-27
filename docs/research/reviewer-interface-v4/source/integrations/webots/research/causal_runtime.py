"""Native causal student adapter. Monotonic IPC timestamps are never refreshed.

Wall and simulator ages are independently exposed; the gate uses their maximum.
No pending action or completion forecast is used in the actor observation.
"""
import multiprocessing as mp
import os
from pathlib import Path
import sys
import time
import numpy as np
REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/'tools/controller_review'))
from realtime_causal import worker_main, shutdown
from realtime_kernels import measure_fast
from kernels import path_values


class FastSensor:
    def __init__(self,seed,noise=1.,delay=0):
        if delay not in (0,1):raise ValueError('supported sensor delay:0/1 ticks')
        self.rng=np.random.default_rng(seed);self.noise=float(noise);self.delay=delay
        self.estimate=np.zeros(4);self.cov=np.eye(4)*.01;self.previous=np.zeros(4);self.tick=0
    def measure(self,state,speed,path):
        noise=self.rng.normal(0,np.array([.03,np.deg2rad(.17),.01,.1])*self.noise)
        raw_speed=max(5.,self.previous[3]) if self.delay and self.tick else max(5.,speed+noise[3])
        self.estimate,self.cov,self.previous,v,k=measure_fast(state,float(speed),path,noise,
            self.delay,self.estimate,self.cov,self.previous,self.tick==0,self.noise)
        ey,vy,ep,r=self.estimate
        previews=[path_values(state[0]+d,path)[2] for d in (0.,10.,20.)]
        obs=np.array([ey/3,ep/.3,(vy+raw_speed*ep)/5,r/.5,raw_speed/25,state[5]/.5,
            previews[0]/.02,previews[1]/.02,previews[2]/.02],dtype=np.float32)
        self.tick+=1
        return obs,self.estimate.copy(),k,float(v)


def packet_ages(packet,sim_time,wall_ns):
    if packet is None:return None
    sim_age=sim_time-packet['observed_sim_s']
    wall_age=(wall_ns-packet['observed_ns'])/1e9
    if sim_age < -1e-9 or wall_age<0:raise ValueError('future observation timestamp')
    return max(0.,sim_age),wall_age,max(0.,sim_age,wall_age)


def actor_observation(physical,gate,packet,age,last_command):
    if np.asarray(physical).shape!=(9,):raise ValueError('9 physical features required')
    history=[gate.weight,min(gate.good,3)/3,
        packet['residual']/.08 if packet else 0.,age/.1 if packet else 0.,float(packet is not None),
        0.,0.,0.,0.,last_command/.5,0.]
    result=np.concatenate((physical,np.asarray(history,dtype=np.float32))).astype(np.float32)
    if not np.isfinite(result).all():raise ValueError('finite causal features required')
    return result


class CausalWorker:
    def __init__(self,folder,delay_s=0.):
        if not np.isfinite(delay_s) or delay_s<0:raise ValueError('finite nonnegative delay required')
        ctx=mp.get_context('spawn');self.connection,child=ctx.Pipe()
        self.process=ctx.Process(target=worker_main,args=(child,str(folder),delay_s,max(os.sched_getaffinity(0))))
        self.closed=False;self.busy=False;self.sequence=0;self.pending=None;self.failed=None
        self.process.start();child.close()
        if not self.connection.poll(45):self.close();raise RuntimeError('causal worker startup timed out')
        status,message=self.connection.recv()
        if status!='ready':self.close();raise RuntimeError(message)
        self.startup_model_ms=message/1e6
    def submit(self,observation,observed_ns,observed_sim_s):
        if self.closed or self.failed or self.busy:return False
        if not self.process.is_alive():self.failed='worker exited';return False
        self.sequence+=1
        self.pending=(self.sequence,observed_ns,observed_sim_s)
        try:self.connection.send((self.sequence,observed_ns,observation.copy()))
        except (EOFError,OSError) as error:self.failed=str(error);return False
        self.busy=True;return True
    def poll(self):
        if self.closed or self.failed:return None
        try:
            if self.connection.poll():
                status,message=self.connection.recv()
                if status!='output':raise RuntimeError(message)
                if self.pending is None or (message['seq'],message['observed_ns'])!=self.pending[:2]:
                    raise RuntimeError('worker sequence/timestamp contract broken')
                message['observed_sim_s']=self.pending[2]
                message['received_ns']=time.perf_counter_ns()
                self.pending=None;self.busy=False
                return message
            if not self.process.is_alive():raise RuntimeError('worker exited')
        except (EOFError,OSError,RuntimeError) as error:self.failed=str(error)
        return None
    def close(self):
        if self.closed:return
        self.closed=True
        try:self.connection.send(None)
        except (EOFError,OSError):pass
        shutdown(self.process);self.connection.close()


class ReferenceFrame:
    """Rigidly align the unchanged map's initial tangent to the settled vehicle.

No vehicle pose is reset or teleported. Body-frame lateral velocity/yaw rate and
steering stay unchanged; only map coordinates and heading are transformed.
"""
    def __init__(self,initial,path):
        self.origin=initial[:2].copy()
        self.reference_y,self.reference_heading,_=path_values(0.,path)
        self.angle=self.reference_heading-initial[2]
        self.last_world=initial.copy()
    def transform(self,state):
        self.last_world=state.copy();result=state.copy()
        dx,dy=state[:2]-self.origin;c=np.cos(self.angle);s=np.sin(self.angle)
        result[0]=c*dx-s*dy;result[1]=s*dx+c*dy+self.reference_y
        result[2]=state[2]+self.angle
        return result
    def metadata(self):
        return dict(world_origin_cg_m=self.origin.tolist(),rotation_rad=float(self.angle),
            map_y_offset_m=float(self.reference_y),initial_map_heading_rad=float(self.reference_heading),
            note='Rigid coordinate alignment only; original path parameters and physical vehicle pose unchanged')
