"""Versioned eight-knot inference; immutable proposals retain original times."""
from pathlib import Path
from dataclasses import replace
from queue import Empty,Full
import json,multiprocessing as mp,time
import numpy as np
from integrations.unified_lans.inference import sha
from .control import Controller,PlanProposal
from .learning import CONTRACT


class InferenceOwner(Controller):
    def accept_plan(self,proposal,now):
        if not isinstance(proposal,PlanProposal):return False
        try:proposal=replace(proposal,knots=tuple(float(v) for v in proposal.knots))
        except (ValueError,TypeError):return False
        return super().accept_plan(proposal,now)


def load_policy(folder,bc=False):
    from stable_baselines3 import PPO
    folder=Path(folder);record=json.loads((folder/'manifest.json').read_text())
    if record.get('contract')!=CONTRACT:raise ValueError('incompatible sequence policy contract')
    name='bc-policy.zip' if bc else 'policy.zip';key='bc_policy_sha256' if bc else 'policy_sha256'
    if sha(folder/name)!=record[key]:raise ValueError('policy hash mismatch')
    model=PPO.load(folder/name,device='cpu')
    if model.observation_space.shape!=(40,) or model.action_space.shape!=(8,):raise ValueError('40 features and eight knots required')
    if not np.all(model.action_space.low==-1) or not np.all(model.action_space.high==1):raise ValueError('normalized knots required')
    return model


def _worker(folder,incoming,outgoing):
    try:
        import torch
        torch.set_num_threads(1);model=load_policy(folder)
        value,_=model.predict(np.zeros(40,np.float32),deterministic=True)
        if not np.isfinite(value).all():raise ValueError('nonfinite startup')
        outgoing.put(('ready',None))
        while True:
            request=incoming.get()
            if request is None:return
            sequence,observed,submitted,wall,query=request
            value,_=model.predict(np.asarray(query,np.float32),deterministic=True)
            outgoing.put(('plan',PlanProposal(sequence,observed,submitted,wall,tuple(float(x) for x in np.asarray(value).ravel()))))
    except Exception as exc:outgoing.put(('error',type(exc).__name__+': '+str(exc)))


class AsyncPlan:
    def __init__(self,folder):
        context=mp.get_context('spawn');self.incoming=context.Queue(maxsize=1);self.outgoing=context.Queue(maxsize=2)
        self.process=context.Process(target=_worker,args=(str(folder),self.incoming,self.outgoing),daemon=True)
        self.failed=False;self.error='';self.sequence=0;self.request=None;self.closed=False;self.process.start()
        try:
            kind,payload=self.outgoing.get(timeout=30)
            if kind!='ready':raise RuntimeError(payload)
        except BaseException:self.close();raise
    def submit(self,query,observed,now):
        if self.closed or self.failed or self.request is not None:return False
        if not self.process.is_alive():self.failed=True;self.error='worker exited';return False
        value=np.asarray(query,np.float32)
        if value.shape!=(40,) or not np.isfinite(value).all():raise ValueError('finite forty-feature query required')
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
        if kind!='plan' or not isinstance(payload,PlanProposal) or self.request is None or (payload.sequence,payload.observed_s,payload.submitted_s,payload.wall_observed)!=self.request:
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
