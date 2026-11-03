"""Joint SOC optimization of locally linearized steering sequences."""
import math
import numpy as np
from numba import njit
from scipy import sparse
import clarabel
from tools.unified_control_v4.kernels import step,lqr,geometry


@njit(cache=True)
def project_commands(commands,initial,accels,stiffness,gains,route):
    state=initial.copy();previous=0.;actions=np.zeros(len(commands))
    for i in range(len(commands)):
        base=lqr(state,gains,int(route[0]),route[1],route[2],route[3],1.)
        residual=min(.08,max(-.08,commands[i]-base));actions[i]=residual/.08
        u=min(.5,max(-.5,min(previous+.03,max(previous-.03,base+residual))))
        state=step(state,u,accels[i],.05,stiffness);previous=u
    return actions


def linearize(initial,states,commands,accels,stiff,gains,route,reference,trust):
    n=len(commands);free=initial.copy();sensitivity=np.zeros((6,n));pre=initial.copy()
    ef=[];em=[];hf=[];hm=[];position_free=[];position_matrix=[];residual=[];residual_offset=[]
    for i in range(n):
        before_free=free.copy();before_sensitivity=sensitivity.copy();u=commands[i];next_state=states[i]
        a=np.zeros((6,6));eps=1e-5
        for j in range(6):
            direction=np.zeros(6);direction[j]=eps
            a[:,j]=(step(pre+direction,u,accels[i],.05,stiff)-step(pre-direction,u,accels[i],.05,stiff))/(2*eps)
        b=(step(pre,u+eps,accels[i],.05,stiff)-step(pre,u-eps,accels[i],.05,stiff))/(2*eps)
        constant=next_state-a@pre-b*u
        free=a@free+constant;sensitivity=a@sensitivity;sensitivity[:,i]+=b
        np.testing.assert_allclose(free+sensitivity@commands,next_state,rtol=0,atol=1e-7)
        y,h,k=geometry(next_state[0],int(route[0]),route[1],route[2],route[3])
        dy=np.zeros(6);dy[0]=-math.tan(h);dy[1]=1.
        dh=np.zeros(6);dh[0]=-k/math.cos(h);dh[2]=1.
        ef.append(next_state[1]-y+dy@(free-next_state));em.append(dy@sensitivity)
        error=math.atan2(math.sin(next_state[2]-h),math.cos(next_state[2]-h))
        hf.append(error+dh@(free-next_state));hm.append(dh@sensitivity)
        position_free.append(free[:2].copy());position_matrix.append(sensitivity[:2].copy())
        base=lqr(pre,gains,int(route[0]),route[1],route[2],route[3],1.)
        if abs(u-base)<=.08+1e-8:
            gradient=np.zeros(6)
            for j in [0,1,2,4,5]:
                direction=np.zeros(6);direction[j]=eps
                gradient[j]=(lqr(pre+direction,gains,int(route[0]),route[1],route[2],route[3],1.)-
                             lqr(pre-direction,gains,int(route[0]),route[1],route[2],route[3],1.))/(2*eps)
            row=-gradient@before_sensitivity;row[i]+=1.
            residual.append(row);residual_offset.append(base+gradient@(before_free-pre))
        pre=next_state
    ef=np.array(ef);em=np.array(em);hf=np.array(hf);hm=np.array(hm)
    difference=np.eye(n);difference[np.arange(1,n),np.arange(n-1)]=-1.
    matrices=[np.eye(n),-np.eye(n),difference,-difference,np.eye(n),-np.eye(n),em,-em]
    bounds=[np.full(n,.5),np.full(n,.5),np.full(n,.03),np.full(n,.03),
            commands+trust,-commands+trust,np.full(n,1.75-1e-8)-ef,np.full(n,1.75-1e-8)+ef]
    if residual:
        residual=np.array(residual);offset=np.array(residual_offset)
        matrices.extend([residual,-residual]);bounds.extend([offset+.08,-offset+.08])
    matrices.append(-sensitivity[0:1]);bounds.append(np.array([free[0]-.99000001*reference[3]]))
    return dict(error_free=ef,error_matrix=em,heading_free=hf,heading_matrix=hm,difference=difference,
        linear_matrix=np.vstack(matrices),linear_bound=np.concatenate(bounds),
        position_free=np.array(position_free),position_matrix=np.array(position_matrix))


def solve_joint(problems,quality):
    count=len(problems);n=len(problems[0]['commands']);controls=count*n
    total=controls+count*(3 if quality else 1);linear=[];bounds=[];blocks=[]
    for p in problems:
        d=linearize(p['initial'],p['states'],p['commands'],p['accels'],p['stiff'],p['gains'],p['route'],p['reference'],p['trust'])
        rows=[];rhs=[]
        for i in range(n):
            for npc in p['npcs'][i]:
                vector=p['states'][i,:2]-npc[:2];normal=vector/max(1e-12,np.linalg.norm(vector))
                rows.append(-normal@d['position_matrix'][i])
                rhs.append(normal@(d['position_free'][i]-npc[:2])-4.600001)
        if rows:
            d['linear_matrix']=np.vstack([d['linear_matrix'],rows]);d['linear_bound']=np.r_[d['linear_bound'],rhs]
        blocks.append(d);linear.append(sparse.csc_matrix(d['linear_matrix']));bounds.append(d['linear_bound'])
    a_linear=sparse.hstack([sparse.block_diag(linear,format='csc'),sparse.csc_matrix((sum(x.shape[0] for x in linear),total-controls))],format='csc')
    b_linear=np.concatenate(bounds)
    if quality:
        rows=np.zeros((2,total));rows[0,controls+count:controls+2*count]=1.;rows[1,controls+2*count:]=1.
        caps=np.array([1.10*(1-1e-6)*sum(math.sqrt(p['reference'][1]) for p in problems),
                       1.10*(1-1e-6)*sum(math.sqrt(p['reference'][2]) for p in problems)])
        a_linear=sparse.vstack([a_linear,sparse.csc_matrix(rows)],format='csc');b_linear=np.r_[b_linear,caps]
    matrices=[a_linear];vectors=[b_linear];cones=[clarabel.NonnegativeConeT(len(b_linear))]
    for k,d in enumerate(blocks):
        entries=[(d['error_matrix'],d['error_free'],controls+k)]
        if quality:entries.extend([(d['heading_matrix'],d['heading_free'],controls+count+k),
                                  (d['difference']/.05,np.zeros(n),controls+2*count+k)])
        for matrix,offset,aux in entries:
            block=sparse.lil_matrix((n+1,total));block[0,aux]=-1.;block[1:,k*n:(k+1)*n]=-matrix
            matrices.append(block.tocsc());vectors.append(np.r_[0.,offset]);cones.append(clarabel.SecondOrderConeT(n+1))
    a=sparse.vstack(matrices,format='csc');b=np.concatenate(vectors);q=np.zeros(total);q[controls:controls+count]=1/(count*math.sqrt(n))
    settings=clarabel.DefaultSettings();settings.verbose=False;settings.max_iter=100
    settings.tol_gap_abs=1e-8;settings.tol_gap_rel=1e-8;settings.tol_feas=1e-8
    solver=clarabel.DefaultSolver(sparse.csc_matrix((total,total)),q,a,b,cones,settings)
    result=solver.solve();status=str(result.status)
    commands=np.asarray(result.x[:controls]).reshape(count,n) if result.x is not None else None
    info=dict(status=status,iterations=result.iterations,solve_time_s=result.solve_time,
              objective=result.obj_val,constraint_rows=a.shape[0],variables=total,nonzeros=a.nnz)
    return commands,info
