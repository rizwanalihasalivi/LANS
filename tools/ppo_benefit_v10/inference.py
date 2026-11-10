"""Versioned 30-feature inference worker for integration into the shared owner."""
from pathlib import Path
import json,multiprocessing as mp,time
from queue import Empty,Full
import numpy as np
from integrations.unified_lans.controller import Proposal
from integrations.unified_lans.inference import sha
from .core import CONTRACT


def load_policy(folder,bc=False):
    from stable_baselines3 import PPO
    folder=Path(folder);record=json.loads((folder/'manifest.json').read_text())
    if record.get('contract')!=CONTRACT:raise ValueError('incompatible queue-aware policy contract')
    name='bc-policy.zip' if bc else 'policy.zip';key='bc_policy_sha256' if bc else 'policy_sha256'
    if sha(folder/name)!=record[key]:raise ValueError('policy hash mismatch')
    model=PPO.load(folder/name,device='cpu')
    if model.observation_space.shape!=(30,) or model.action_space.shape!=(1,):raise ValueError('expected 30 features and scalar action')
    if not np.array_equal(model.action_space.low,[-1.]) or not np.array_equal(model.action_space.high,[1.]):raise ValueError('invalid action bounds')
    return model


def _worker(folder,incoming,outgoing):
    try:
        import torch
        torch.set_num_threads(1);model=load_policy(folder)
        value,_=model.predict(np.zeros(30,np.float32),deterministic=True)
        if not np.isfinite(value).all():raise ValueError('nonfinite startup probe')
        outgoing.put(('ready',None))
        while True:
            item=incoming.get()
            if item is None:return
            sequence,observed,submitted,wall,features=item
            value,_=model.predict(np.asarray(features,np.float32),deterministic=True)
            residual=float(np.asarray(value).ravel()[0])*.08
            outgoing.put(('proposal',Proposal(sequence,observed,submitted,residual,wall)))
    except Exception as exc:outgoing.put(('error',type(exc).__name__+': '+str(exc)))


class AsyncPolicy:
    """One pending request; received timestamps are never rewritten as fresh."""
    def __init__(self,folder):
        context=mp.get_context('spawn');self.incoming=context.Queue(maxsize=1);self.outgoing=context.Queue(maxsize=2)
        self.process=context.Process(target=_worker,args=(str(folder),self.incoming,self.outgoing),daemon=True)
        self.request=None;self.sequence=0;self.failed=False;self.error='';self.closed=False
        self.process.start()
        try:
            kind,payload=self.outgoing.get(timeout=30)
            if kind!='ready':raise RuntimeError(payload)
        except BaseException:self.close();raise
    def submit(self,features,observed,now):
        if self.closed or self.failed or self.request is not None:return False
        if not self.process.is_alive():self.failed=True;self.error='worker exited';return False
        value=np.asarray(features,dtype=np.float32)
        if value.shape!=(30,) or not np.isfinite(value).all():raise ValueError('finite 30-feature observation required')
        if not np.isfinite([observed,now]).all() or not 0<=observed<=now:raise ValueError('invalid received timestamps')
        key=(self.sequence+1,float(observed),float(now),time.monotonic())
        try:self.incoming.put_nowait((*key,tuple(value)))
        except Full:return False
        self.sequence+=1;self.request=key;return True
    def poll(self):
        if self.closed:return None
        try:kind,payload=self.outgoing.get_nowait()
        except Empty:
            if not self.process.is_alive():self.failed=True;self.error='worker exited'
            return None
        if kind!='proposal' or not isinstance(payload,Proposal) or self.request is None or (payload.sequence,payload.observed_s,payload.submitted_s,payload.wall_observed)!=self.request:
            self.failed=True;self.error=str(payload);self.request=None;return None
        self.request=None;return payload
    def close(self):
        if self.closed:return
        self.closed=True
        if self.process.is_alive():
            try:self.incoming.put_nowait(None)
            except Full:pass
            self.process.join(timeout=1)
            if self.process.is_alive():self.process.terminate();self.process.join(timeout=2)
        else:self.process.join(timeout=1)
        for queue in (self.incoming,self.outgoing):queue.cancel_join_thread();queue.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
