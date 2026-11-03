"""Spawned CPU PPO inference. Control never waits for inference during a tick."""
import hashlib
import json
import math
import multiprocessing as mp
from pathlib import Path
from queue import Empty, Full
import time
import numpy as np
from .controller import Proposal

CONTRACT='unified-bicycle-traffic-residual-v1'
FEATURES='scaled-error4-speed-preview4-egoage-responseage-ttc-clearance-trafficage-applied2-busy'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_policy(folder):
    from stable_baselines3 import PPO
    path=Path(folder);m=json.loads((path/'manifest.json').read_text())
    if m.get('contract')!=CONTRACT or m.get('features')!=FEATURES or m.get('scale_rad')!=.08:
        raise ValueError('incompatible unified policy; historical policies cannot be relabeled')
    if sha(path/'policy.zip')!=m['policy_sha256']:raise ValueError('policy hash mismatch')
    model=PPO.load(path/'policy.zip',device='cpu')
    if (model.observation_space.shape!=(17,) or model.action_space.shape!=(1,)
            or not np.array_equal(model.action_space.low,[-1.])
            or not np.array_equal(model.action_space.high,[1.])):
        raise ValueError('unified PPO requires 17 features and normalized scalar residual')
    return model


def _worker(folder, incoming, outgoing, sleep_s):
    try:
        import torch
        torch.set_num_threads(1)
        model=load_policy(folder)
        probe,_=model.predict(np.zeros(17,dtype=np.float32),deterministic=True)
        if not np.isfinite(probe).all():raise ValueError('nonfinite policy startup probe')
        outgoing.put(('ready',None))
        while True:
            item=incoming.get()
            if item is None:return
            seq,observed,submitted,wall,features=item
            action,_=model.predict(np.array(features,dtype=np.float32),deterministic=True)
            if sleep_s:time.sleep(sleep_s)
            residual=float(np.asarray(action).reshape(-1)[0])*.08
            outgoing.put(('proposal',Proposal(seq,observed,submitted,residual,wall)))
    except Exception as exc:
        outgoing.put(('error',type(exc).__name__+': '+str(exc)))


class AsyncPPO:
    def __init__(self, folder, sleep_s=0.):
        if not math.isfinite(sleep_s) or sleep_s<0:raise ValueError('invalid inference delay')
        ctx=mp.get_context('spawn');self.incoming=ctx.Queue(maxsize=1);self.outgoing=ctx.Queue(maxsize=2)
        self.process=ctx.Process(target=_worker,args=(str(folder),self.incoming,self.outgoing,sleep_s),daemon=True)
        self.busy=False;self.failed=False;self.error='';self.sequence=0;self.request=None
        self.process.start()
        try:
            kind,payload=self.outgoing.get(timeout=30)
            if kind!='ready':raise RuntimeError(str(payload))
        except Exception:
            self.close();raise

    def submit(self, features, observed, now):
        if self.busy or self.failed:return False
        if not self.process.is_alive():self.failed=True;return False
        if features is None:return False
        wall=time.monotonic();self.sequence+=1
        self.request=(self.sequence,observed,now,wall)
        try:self.incoming.put_nowait((*self.request,tuple(features)))
        except Full:return False
        self.busy=True;return True

    def poll(self):
        try:kind,payload=self.outgoing.get_nowait()
        except Empty:
            if not self.process.is_alive():self.failed=True;self.error='worker exited'
            return None
        self.busy=False
        if kind=='error':self.failed=True;self.error=payload;return None
        if kind!='proposal' or self.request is None:return None
        if (payload.sequence,payload.observed_s,payload.submitted_s,payload.wall_observed)!=self.request:
            self.failed=True;self.error='response identity mismatch';return None
        self.request=None
        return payload

    def close(self):
        if self.process.is_alive():
            try:self.incoming.put_nowait(None)
            except Full:pass
            self.process.join(timeout=1)
            if self.process.is_alive():self.process.terminate();self.process.join(timeout=2)
        else:self.process.join(timeout=1)
        for q in (self.incoming,self.outgoing):
            q.cancel_join_thread();q.close()

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
