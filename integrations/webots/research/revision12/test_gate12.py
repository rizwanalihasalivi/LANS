"""Reference preservation, information boundary, objective and gate contracts."""
import unittest
import numpy as np
from gate12 import cost12,execution_step12,_curvature_at
from gating import predict_cost
from kernels import execution_step,initial_executor,lqr
from comparison import configure_lqr
from core import GAINS,Sensor,path_values
from plant import advance


def reference_rollout(estimate, actuator, command, speed, curvature, gain):
    """Independent scalar Python integration of the original constant-road model."""
    ey,vy,ep,r=map(float,estimate);delta=float(actuator);combined=0.;lateral=0.;trace=[]
    vy_ref=(1.4*speed-1650*1.2*speed**3/(2.6*80000))*curvature
    ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*speed**2)*curvature
    for step in range(20):
        errors=(ey,vy-vy_ref,ep+vy_ref/speed,r-speed*curvature)
        u=float(command) if step<5 else float(np.clip(ff-sum(g*x for g,x in zip(gain,errors)),-.5,.5))
        delta+=.01*float(np.clip((u-delta)/.05,-.35,.35))
        front=80000*(delta-(vy+1.2*r)/speed);rear=80000*(-(vy-1.4*r)/speed)
        ey,vy,ep,r=(ey+.01*(vy+speed*ep),vy+.01*((front+rear)/1650-speed*r),
                    ep+.01*(r-speed*curvature),r+.01*((1.2*front-1.4*rear)/4224))
        lateral+=.01*(ey/.5)**2
        combined+=.01*((ey/.5)**2+.2*(ep/.1)**2+.01*((r-speed*curvature)/.2)**2+.001*(u/.5)**2)
        trace.append((ey,vy,ep,r,delta,u))
    lateral+=.1*(ey/.5)**2
    combined+=.1*((ey/.5)**2+.2*(ep/.1)**2)
    return combined,lateral,np.array(trace)


class GateAblationContracts(unittest.TestCase):
    def setUp(self):
        configure_lqr()
        self.gains=np.array([GAINS[v] for v in (15,20,25)])

    def test_reference_execution_and_plant_trajectory_parity(self):
        path=(0.,1.5,120.,.2)
        for service in [0,1,2,10]:
            for sparse in [False,True]:
                original=initial_executor();new=initial_executor()
                y,h,_=path_values(0.,path)
                state=np.array([0.,y+.15,h+.01,0.,0.,0.]);other=state.copy()
                sensor=Sensor(410+service)
                for tick in range(120):
                    obs,estimate,k=sensor.measure(state,25.,path)
                    speed=max(5.,float(obs[4])*25);baseline,gain=lqr(estimate,speed,k,self.gains)
                    previews=obs[6:9].astype(np.float64)*.02
                    proposal=.08*np.sin(tick/7);submit=not sparse or tick%5==0
                    before=previews.copy()
                    a=execution_step(original,tick*.01,proposal,service,baseline,estimate,state[5],speed,k,gain,False,submit)
                    b=execution_step12(new,tick*.01,proposal,service,baseline,estimate,other[5],speed,k,gain,previews,0,submit)
                    self.assertEqual(a,b);np.testing.assert_array_equal(original,new)
                    np.testing.assert_array_equal(previews,before)
                    state=advance(state,a[0],25.,.9,.65);other=advance(other,b[0],25.,.9,.65)
                    np.testing.assert_array_equal(state,other)

    def test_flat_previews_recover_original_combined_cost(self):
        rng=np.random.default_rng(201)
        for speed in [15.,20.,25.]:
            gain=GAINS[int(speed)]
            for k in [-.006,0.,.004]:
                state=rng.normal(0,[.15,.03,.02,.02]);before=state.copy()
                actuator=.03;command=-.04;previews=np.full(3,k)
                old=predict_cost(state,actuator,command,speed,k,gain,20)
                self.assertEqual(cost12(state,actuator,command,speed,k,gain,previews,0),old)
                self.assertAlmostEqual(cost12(state,actuator,command,speed,k,gain,previews,1),old,places=13)
                np.testing.assert_array_equal(state,before)

    def test_lateral_objective_matches_independent_same_dynamics_rollout(self):
        for speed in [15.,25.]:
            state=np.array([.12,-.04,.015,.03]);k=.003;gain=GAINS[int(speed)]
            combined,lateral,trace=reference_rollout(state,.02,-.06,speed,k,gain)
            # Deliberately nonflat previews must not change lateral-only geometry.
            previews=np.array([-.01,.02,-.03])
            self.assertAlmostEqual(cost12(state,.02,-.06,speed,k,gain,previews,0),combined,places=12)
            self.assertAlmostEqual(cost12(state,.02,-.06,speed,k,gain,previews,2),lateral,places=12)
            self.assertGreater(combined,lateral)
            self.assertTrue(np.isfinite(trace).all())
            self.assertLessEqual(np.max(np.abs(np.diff(np.r_[.02,trace[:,4]]))),.00350000001)

    def test_preview_uses_only_declared_points_and_local_anchor(self):
        previews=np.array([.99,.004,-.002]);k=.001
        self.assertEqual(_curvature_at(0.,k,previews),k)
        self.assertEqual(_curvature_at(10.,k,previews),previews[1])
        self.assertEqual(_curvature_at(20.,k,previews),previews[2])
        self.assertEqual(_curvature_at(35.,k,previews),previews[2])
        self.assertAlmostEqual(_curvature_at(5.,k,previews),.0025)
        estimate=np.array([.1,0.,.01,0.]);gain=GAINS[25]
        a=cost12(estimate,0.,.01,25.,k,gain,previews,1)
        previews[0]=-123.
        self.assertEqual(a,cost12(estimate,0.,.01,25.,k,gain,previews,1))
        self.assertNotEqual(a,cost12(estimate,0.,.01,25.,k,gain,np.full(3,k),1))

    def test_stale_missing_envelope_and_recovery_bounds(self):
        estimate=np.array([.03,0.,.005,0.]);k=.001;gain=GAINS[25]
        baseline,_=lqr(estimate,25.,k,self.gains);previews=np.full(3,k)
        for variant in [1,2]:
            ex=initial_executor()
            out=execution_step12(ex,0.,.08,0,baseline,estimate,0.,25.,k,gain,previews,variant,False)
            self.assertEqual(out[:3],(baseline,0.,0))
            ex=initial_executor()
            for tick in range(30):
                command,weight,reason,_=execution_step12(ex,tick*.01,.08,10,baseline,estimate,0.,25.,k,gain,previews,variant)
                self.assertEqual(command,baseline);self.assertEqual(weight,0.)
                self.assertIn(reason,[0,1])
            ex=initial_executor();outside=estimate.copy();outside[0]=1.51
            out=execution_step12(ex,0.,.08,0,baseline,outside,0.,25.,k,gain,previews,variant)
            self.assertEqual(out[:3],(baseline,0.,3))
            earned=0
            for sign in [-1,1]:
                ex=initial_executor();prior=0.;good=0
                for tick in range(25):
                    command,weight,reason,_=execution_step12(ex,tick*.01,sign*1.,0,baseline,estimate,0.,25.,k,gain,previews,variant)
                    self.assertLessEqual(abs(command),.5)
                    self.assertLessEqual(weight,.5)
                    self.assertLessEqual(weight,prior+.0500000001)
                    self.assertLessEqual(abs(command-baseline),.0400000001)
                    if reason==5:
                        good+=1;self.assertLess(good,3);self.assertEqual(command,baseline)
                    elif reason==6:
                        earned+=1;self.assertGreaterEqual(ex[1],3)
                        j0=cost12(estimate,0.,baseline,25.,k,gain,previews,variant)
                        j1=cost12(estimate,0.,command,25.,k,gain,previews,variant)
                        self.assertGreaterEqual(j0-j1,max(1e-7,.01*j0))
                        if earned==1:
                            recovery=ex.copy()
                            stale=execution_step12(recovery,tick*.01+.1,sign*.08,0,baseline,estimate,0.,25.,k,gain,previews,variant,False)
                            self.assertEqual(stale[:3],(baseline,0.,1));self.assertEqual(recovery[1],0.)
                            for offset in [1,2,3]:
                                recovered=execution_step12(recovery,tick*.01+.1+offset*.01,sign*.08,0,baseline,estimate,0.,25.,k,gain,previews,variant)
                                self.assertEqual(recovered[2],5 if offset<3 else 6)
                    else:good=0
                    prior=weight
            self.assertGreater(earned,0,'exercise real earned decisions as well as fallback')

if __name__=='__main__':unittest.main()
