"""Single-request, gate-mediated counterfactual credit; training-only forecast."""
import numpy as np
from numba import njit
from bootstrap import RESEARCH
from kernels import initial_executor,execution_step,measure,lqr,path_values
from plant import advance


def numeric_worker(execution):
    out=initial_executor();g=execution.gate
    out[:3]=[g.weight,g.good,g.last_sequence]
    if execution.packet:out[3:6]=execution.packet
    if execution.pending:out[6]=execution.pending[0];out[7:10]=execution.pending[1]
    out[10:]=[execution.sequence,execution.last_command]
    return out


@njit(cache=True)
def single_request_cost(state,estimate,cov,previous_raw,executor,tick,proposal,service,speed,path,mu,stiffness,delay,noise_scale,measured,curvature,gains):
    z=state.copy();est=estimate.copy();variance=cov.copy();previous=previous_raw.copy();worker=executor.copy()
    v=measured;k=curvature;cost=0.;applied=0;new_sequence=worker[10]+1
    for j in range(20):
        baseline,gain=lqr(est,v,k,gains)
        command,weight,_,_=execution_step(worker,(tick+j)*.01,proposal if j==0 else 0.,service,baseline,est,z[5],v,k,gain,False)
        if worker[3]==new_sequence and weight>0 and command!=baseline:applied+=1
        z=advance(z,command,speed,mu,stiffness)
        y,h,_=path_values(z[0],path);error=z[1]-y;cost+=error*error
        if abs(error)>2.5 or abs(z[2]-h)>.6 or not np.isfinite(z).all():return cost+(19-j)*6.25,applied
        if j<19:est,variance,previous,v,k=measure(z,speed,path,np.zeros(4),delay,est,variance,previous,False,noise_scale)
    return cost,applied


def proposal_credit(env,proposal):
    worker=numeric_worker(env.execution);tick=env.steps
    available=worker[7]<0 or worker[6]<=tick*.01+1e-9
    if not available or proposal==0.:return 0.,0.,0.,0,bool(available)
    from core import GAINS
    gains=np.array([GAINS[v] for v in (15,20,25)])
    args=(env.state,env.estimate,env.sensor.cov,env.sensor.queue[-1],worker,tick)
    tail=(env.service_ticks,float(env.speed),env.path,env.mu,env.stiffness,env.delay,float(env.noise),max(5.,float(env.obs[4])*25),env.kappa,gains)
    zero,_=single_request_cost(*args,0.,*tail);candidate,applied=single_request_cost(*args,proposal,*tail)
    reward=float(np.clip((zero-candidate)/max(zero,1e-4),-1.,1.))
    if not applied:assert abs(reward)<1e-12
    return reward,float(zero),float(candidate),int(applied),True
