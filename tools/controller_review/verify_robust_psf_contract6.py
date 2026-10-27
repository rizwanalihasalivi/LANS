"""Independent LP optimal-input interval and bounded-error trajectory replay."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.optimize import linprog

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();out=a.run
    meta=json.loads((out/'summary.json').read_text());v=meta['parameters'];rows=list(csv.DictReader((out/'traces.csv').open()));last={};full={};count=0
    aa,bb,wlim=v['A'],v['B'],v['error_bound'];root=np.sqrt(v['rho']);eps=v['epsilon'];ulim=v['input_limit'];term=v['terminal_radius'];N=v['horizon']
    assert eps>max(1,1/ulim,1/term)*wlim and abs(aa-bb-root)<1e-12
    for row in rows:
        key=(row['seed'],row['initial'],row['fault']);k=int(row['k']);x=float(row['x']);u=float(row['u']);w=float(row['w']);nx=float(row['next_x']);h=int(row['horizon'])
        if k:assert abs(x-last[key])<1e-12
        else:assert x==float(row['initial'])
        assert abs(nx-(aa*x+bb*u+w))<1e-12 and abs(w)<=wlim+1e-12 and abs(u)<=ulim+2e-7 and abs(nx)<=1+2e-7
        if row['branch']=='full':assert h==N;full[key]=k
        elif row['branch']=='shrinking':assert h==N-(k-full[key]) and 0<h<N
        else:
            assert k>=full[key]+N and abs(x)<=term+2e-7 and abs(nx)<=term+2e-7 and u==-x
        if h:
            # Eliminate states by independently propagating affine coefficients.
            coefficient=np.zeros(h);constant=x;M=[];upper=[];bounds=[]
            for i in range(h):
                tightening=eps*sum(root**j for j in range(i))
                M += [coefficient.copy(),-coefficient.copy()];upper += [1-tightening-constant,1-tightening+constant]
                bound=ulim*(1-tightening);bounds.append((-bound,bound))
                coefficient*=aa;coefficient[i]+=bb;constant*=aa
            target=term*(1-eps*sum(root**j for j in range(h)))
            M += [coefficient.copy(),-coefficient.copy()];upper += [target-constant,target+constant]
            objective=np.zeros(h);objective[0]=1
            low=linprog(objective,A_ub=np.array(M),b_ub=np.array(upper),bounds=bounds,method='highs')
            high=linprog(-objective,A_ub=np.array(M),b_ub=np.array(upper),bounds=bounds,method='highs')
            assert low.success and high.success
            expected=np.clip(float(row['requested']),low.fun,-high.fun)
            assert abs(u-expected)<2e-6,(row,u,expected)
            count+=1
        last[key]=nx
    result=dict(transitions=len(rows),independent_lp_projections=count,original_state_and_disturbance_replay=True,shrinking_clock_verified=True,
        terminal_invariance_verified=True,source_sha256=hashlib.sha256((Path(__file__).parent/'robust_psf_contract6.py').read_bytes()).hexdigest(),
        verified_scope='Scalar uniform-bound specialization only; no matched nonlinear-vehicle reproduction')
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(result)

if __name__=='__main__':main()
