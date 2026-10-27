"""Numerical nominal augmented-model check, never a nonlinear safety proof."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'integrations/webots/research'))
from comparison import configure_lqr
from core import GAINS
import numpy as np
from scipy.linalg import expm, solve_continuous_lyapunov


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();configure_lqr();result=[]
    for v in (15,20,25):
        cf=cr=80000.;m=1650.;iz=4224.;lf=1.2;lr=1.4
        a=np.array([[0.,1.,v,0.],[0.,-(cf+cr)/(m*v),0.,(cr*lr-cf*lf)/(m*v)-v],
                    [0.,0.,0.,1.],[0.,(cr*lr-cf*lf)/(iz*v),0.,-(cf*lf*lf+cr*lr*lr)/(iz*v)]])
        b=np.array([0.,cf/m,0.,cf*lf/iz])
        aug=np.zeros((5,5));aug[:4,:4]=a;aug[:4,4]=b
        aug[4,:4]=-GAINS[v]/.05;aug[4,4]=-1/.05
        eig=np.linalg.eigvals(aug);hurwitz=bool(np.max(eig.real)<0)
        # Exact discretization of the continuously applied feedback model only;
        # sampled/held digital feedback, clipping and rate limit are NOT this matrix.
        item=dict(speed=v,poles=[[float(z.real),float(z.imag)] for z in eig],hurwitz=hurwitz,
                  continuous_feedback_flow_radius_10ms=float(max(abs(np.linalg.eigvals(expm(aug*.01))))))
        if hurwitz:
            matrix=solve_continuous_lyapunov(aug.T,-np.eye(5))
            item.update(lyapunov_min_eigenvalue=float(np.min(np.linalg.eigvalsh(matrix))),
                lyapunov_residual_norm=float(np.linalg.norm(aug.T@matrix+matrix@aug+np.eye(5))))
        result.append(item)
    report=dict(cases=result,scope='delay-free unsaturated nominal linearization with0.05s actuator lag and continuous state feedback',
        exclusions=['nonlinear Fiala dynamics','sample/hold and sensor estimation','input/rate saturation','time-varying delay and switching','global safety or zero convergence with nonzero residual'])
    args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
