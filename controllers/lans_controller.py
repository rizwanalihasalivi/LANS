"""Corrected root controller; learned control requires a versioned policy bundle.

Synchronous API only. tau_ms is compute duration, NOT asynchronous action age.
Use the isolated research worker for plant-independent real-process timing.
"""
import time
import numpy as np
from models.bicycle_model import VEHICLE_PARAMS, get_error_state_from_measurements
from controllers.lqr_controller import get_lqr_controller
from controllers.policy_bundle import PolicyBundle


class LANSController:
    def __init__(self, vx=25., params=None, load_ppo_model=False, policy_bundle=None):
        self.vx=float(vx); self.params=dict(VEHICLE_PARAMS if params is None else params)
        self.K_lqr,self.lqr_control=get_lqr_controller(self.vx,self.params)
        if load_ppo_model and policy_bundle is None:
            raise ValueError('learned control requires a corrected policy_bundle with normalization and manifest')
        self.ppo_model=PolicyBundle(policy_bundle) if policy_bundle is not None else None
        self.last_error_state=np.zeros(4); self.last_delta_lqr=0.; self.last_delta_rl=0.
        self.latency_history=[]; self.last_latency=0.

    def update_error_state(self,y_actual,y_ref,psi_actual,psi_ref,vy,r,kappa):
        self.last_error_state=get_error_state_from_measurements(y_actual,y_ref,psi_actual,psi_ref,self.vx,vy,r,kappa)
        return self.last_error_state

    def compute_delta_lqr(self,error_state=None,curvature=0.):
        self.last_delta_lqr=self.lqr_control(self.last_error_state if error_state is None else error_state,curvature)
        return self.last_delta_lqr

    def compute_delta_rl(self,observation,deterministic=True):
        if self.ppo_model is None:
            return 0.
        action,_=self.ppo_model.predict(observation,deterministic)
        self.last_delta_rl=.08*float(np.clip(np.asarray(action).item(),-1,1))
        return self.last_delta_rl

    def step(self,y_actual,y_ref,psi_actual,psi_ref,vy,r,kappa,*,preview_y=None):
        start=time.perf_counter()
        state=self.update_error_state(y_actual,y_ref,psi_actual,psi_ref,vy,r,kappa)
        if preview_y is None:
            if self.ppo_model is not None:
                raise ValueError('learned control requires four actual path previews at vx*dt offsets')
            preview_y=[y_ref]*4
        if len(preview_y)!=4:
            raise ValueError('four path previews required')
        # Synchronous training observation has zero packet age; do not substitute wall runtime.
        observation=np.asarray([*state,self.vx,*[y_actual-y for y in preview_y],0.,0.],dtype=np.float32)
        baseline=self.compute_delta_lqr(state,kappa); residual=self.compute_delta_rl(observation)
        command=float(np.clip(baseline+residual,-.5,.5))
        return command,dict(error_state=state,delta_lqr=baseline,delta_rl=residual,beta=1.,
                            tau_ms=(time.perf_counter()-start)*1000,delta_total=command,
                            observation=observation,mode='residual' if self.ppo_model else 'lqr')
