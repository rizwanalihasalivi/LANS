"""Uniform-error specialization of 1812.05506v4 Eq(6)/Algorithm2.

This scalar, fully observed bounded-error contract is deliberately separate
from the noisy nonlinear LANS vehicle. It is not a vehicle reproduction or
reproduction of the authors' numerical examples.
"""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from scipy import sparse
import osqp

H=10;A=.8;B=.2;W=.01;EPS=.06;ROOT_RHO=.6;TERMINAL=.2;ULIM=.5

def tightening(i):return EPS*(1-ROOT_RHO**i)/(1-ROOT_RHO)

def solve(x,request,horizon):
    if horizon<1:return None
    h=horizon;g=np.zeros((h+1,h));powers=A**np.arange(h+1)
    for i in range(1,h+1):g[i,:i]=B*A**np.arange(i-1,-1,-1)
    lo=[];hi=[];blocks=[]
    for i in range(h):
        row=np.zeros(h);row[i]=1.;blocks.append(row)
        bound=ULIM*(1-tightening(i));lo.append(-bound);hi.append(bound)
        blocks.append(g[i]);bound=1-tightening(i)
        lo.append(-bound-powers[i]*x);hi.append(bound-powers[i]*x)
    bound=TERMINAL*(1-tightening(h));blocks.append(g[h]);lo.append(-bound-powers[h]*x);hi.append(bound-powers[h]*x)
    matrix=np.array(blocks);q=np.zeros(h);q[0]=-2*request;diagonal=np.zeros(h);diagonal[0]=2.
    solver=osqp.OSQP();solver.setup(P=sparse.diags(diagonal,format='csc'),q=q,A=sparse.csc_matrix(matrix),
        l=np.array(lo),u=np.array(hi),verbose=False,eps_abs=1e-9,eps_rel=1e-9,max_iter=10000,polish=True)
    result=solver.solve()
    if result.info.status!='solved':return None
    v=result.x
    if np.max(np.maximum(np.array(lo)-matrix@v,matrix@v-np.array(hi)))>2e-7:return None
    return float(v[0])

class Filter:
    def __init__(self):self.last_full=None
    def choose(self,k,x,request,force_full_unavailable=False):
        u=None if force_full_unavailable else solve(x,request,H)
        if u is not None:self.last_full=k;return u,'full',H
        if self.last_full is not None and k<self.last_full+H:
            h=H-(k-self.last_full);u=solve(x,request,h)
            if u is None:raise RuntimeError('Required shrinking backup infeasible; no safety label issued')
            return u,'shrinking',h
        if self.last_full is None or abs(x)>TERMINAL+2e-7:raise RuntimeError('No certified initial/terminal contract')
        return -x,'terminal',0

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False)
    # Incremental V=e^2, correction pi=v-e, nominal closed-loop error=.6e.
    # State/input/terminal normalized sensitivities are1/2/5. EPS=.06 >5W.
    # Their errors decay at ROOT_RHO^i, so every shrinking-plan tightening
    # increment dominates the corresponding bounded disturbed shift.
    assert EPS>=max(1.,1/ULIM,1/TERMINAL)*W
    assert abs(ROOT_RHO-(A-B))<1e-12 and 0<ROOT_RHO<1
    assert ROOT_RHO*TERMINAL+W<=TERMINAL and TERMINAL<=ULIM
    rows=[];branches=set()
    for seed in (6101,6202,6303):
        rng=np.random.default_rng(seed)
        for initial in (-.95,-.4,0.,.4,.95):
            for fault in (False,True):
                f=Filter();x=initial
                for k in range(100):
                    requested=float(.9*np.sin(.37*k)+.2*rng.normal())
                    forced=fault and 20<=k<45
                    u,branch,h=f.choose(k,x,requested,forced);branches.add(branch)
                    # Endpoint disturbances alternate to test both signs;
                    # remaining cases sample declared bounded disturbances.
                    w=W*(-1 if k%2 else 1) if seed==6101 else float(rng.uniform(-W,W))
                    next_x=A*x+B*u+w
                    assert abs(x)<=1+2e-7 and abs(u)<=ULIM+2e-7 and abs(next_x)<=1+2e-7
                    if branch=='terminal':assert abs(x)<=TERMINAL+2e-7 and abs(next_x)<=TERMINAL+2e-7
                    rows.append(dict(seed=seed,initial=initial,fault=fault,k=k,x=x,requested=requested,u=u,w=w,next_x=next_x,branch=branch,horizon=h));x=next_x
    assert branches=={'full','shrinking','terminal'}
    try:Filter().choose(0,2.,0.)
    except RuntimeError:rejected=True
    else:rejected=False
    assert rejected
    with (out/'traces.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    result=dict(source='Wabersich/Zeilinger arXiv1812.05506v4 Eq6 without6e under uniform error Eq8, tighteningEq9/10, Algorithm2',
        specialization='Independent scalar bounded-error/full-state contract; NOT authors code, numerical-example reproduction or matched LANS vehicle comparator',
        parameters=dict(A=A,B=B,error_bound=W,horizon=H,epsilon=EPS,rho=ROOT_RHO**2,terminal_radius=TERMINAL,input_limit=ULIM),
        trajectories=30,transitions=len(rows),state_or_input_violations=0,branches=sorted(branches),uncertified_initial_state_rejected=rejected,
        assumptions='V=e^2, pi=v-e, contractionrho=.36, cl=cu=1, pimax=1; compact uniform error [-.01,.01], exact full-state sensing, terminalpi=-x invariant; EPS dominates normalized state/input/terminal shifts. No online confidence map is needed for uniform-bound specialization.',
        limitations='Does not supply a validated vehicle model-error confidence bound, vehicle terminal safe set, noisy-state certificate, target timing or LANS superiority. Current Gaussian sensing and nonlinear tire uncertainty do not inherit this contract.')
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
