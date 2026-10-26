"""Geometry, observation, objective and inherited execution contracts."""
import math
import unittest
import numpy as np
from dynamics13 import path_values13, measure13, features13
from gate13 import cost13, execution_step13, objective_weights13
from gate12 import cost12, execution_step12
from kernels import path_values, measure, initial_executor, execution_step, lqr
from teacher import features
from plant import advance
from comparison import configure_lqr
from core import GAINS


def independent_cost_terms(estimate, actuator, command, speed, curvature, gain):
    """Scalar rollout returns lateral, heading and squared physical-rate costs."""
    ey, vy, ep, r = map(float, estimate); delta = float(actuator)
    vyref = (1.4*speed-1650*1.2*speed**3/(2.6*80000))*curvature
    ff = (2.6+1650/2.6*(1.4/80000-1.2/80000)*speed**2)*curvature
    lateral = heading = rates = first_rate_cost = 0.
    for i in range(20):
        errors = (ey, vy-vyref, ep+vyref/speed, r-speed*curvature)
        u = command if i < 5 else float(np.clip(ff-sum(g*x for g,x in zip(gain,errors)), -.5,.5))
        rate = float(np.clip((u-delta)/.05, -.35,.35))
        delta += .01*rate
        front = 80000*(delta-(vy+1.2*r)/speed)
        rear = 80000*(-(vy-1.4*r)/speed)
        ey, vy, ep, r = (ey+.01*(vy+speed*ep), vy+.01*((front+rear)/1650-speed*r),
                         ep+.01*(r-speed*curvature), r+.01*((1.2*front-1.4*rear)/4224))
        lateral += .01*(ey/.5)**2
        heading += .01*(ep/.1)**2
        rates += .01*(rate/.35)**2
        if i == 0:
            first_rate_cost = .01*(rate/.35)**2
    return lateral+.1*(ey/.5)**2, heading+.1*(ep/.1)**2, rates, first_rate_cost


class BalancedGateContracts(unittest.TestCase):
    def setUp(self):
        configure_lqr()
        self.gains = np.array([GAINS[v] for v in (15,20,25)])

    def test_original_geometry_and_scaled_reflection(self):
        for base in ((0.,2.5,120.,.3),(1.,0.,0.,0.)):
            for x in (0.,13.2,40.,70.,120.,210.):
                self.assertEqual(path_values13(x,base+(1.,1.)),path_values(x,base))
                for scale in (1.,1.2):
                    a = path_values13(x,base+(scale,1.))
                    b = path_values13(x,base+(scale,-1.))
                    np.testing.assert_allclose(b,-np.array(a),rtol=0,atol=1e-15)
                    step = 1e-3
                    yp = path_values13(x+step,base+(scale,1.))[0]
                    ym = path_values13(x-step,base+(scale,1.))[0]
                    self.assertAlmostEqual(math.tan(a[1]),(yp-ym)/(2*step),places=7)
                    second = (yp-2*a[0]+ym)/step**2
                    self.assertAlmostEqual(a[2],second/(1+math.tan(a[1])**2)**1.5,places=6)
        for scale,sign in ((0.,1.),(-1.,1.),(math.nan,1.),(1.,0.)):
            with self.assertRaises(ValueError):
                path_values13(1.,(0.,2.5,120.,.3,scale,sign))

    def test_original_sensor_and_feature_parity(self):
        rng = np.random.default_rng(713)
        for base in ((0.,2.5,120.,.3),(1.,0.,0.,0.)):
            for delay in (0,1):
                y,h,_ = path_values(0.,base)
                state = np.array([0.,y+.15,h+.01,0.,0.,0.])
                estimate = np.zeros(4); cov = np.eye(4)*.01; previous = np.zeros(4)
                worker = initial_executor()
                for tick in range(40):
                    noise = rng.normal(0,[.03,.003,.01,.1])
                    args = (state,20.,base,noise,delay,estimate,cov,previous,tick==0,1.)
                    a = measure(*args)
                    b = measure13(state,20.,base+(1.,1.),noise,delay,estimate,cov,previous,tick==0,1.)
                    for original,new in zip(a,b):
                        np.testing.assert_array_equal(original,new)
                    raw_speed = max(5.,previous[3]) if delay and tick else max(5.,20.+noise[3])
                    estimate,cov,previous,v,k = a
                    observed = features(state,estimate,raw_speed,base,worker,tick,2)
                    new = features13(state,estimate,raw_speed,base+(1.,1.),worker,tick,2)
                    np.testing.assert_array_equal(observed,new)
                    baseline,gain = lqr(estimate,v,k,self.gains)
                    command,*_ = execution_step(worker,tick*.01,.04,2,baseline,estimate,state[5],v,k,gain,False)
                    state = advance(state,command,20.,.9,.65)

    def test_mirror_estimator_plant_and_features(self):
        path = (1.,0.,0.,0.,1.2,1.)
        mirrored_path = path[:-1]+(-1.,)
        y,h,_ = path_values13(0.,path)
        state = np.array([0.,y+.15,h+.01,0.,0.,0.])
        mirrored = state*np.array([1.,-1.,-1.,-1.,-1.,-1.])
        estimate = np.zeros(4); other_estimate = estimate.copy()
        cov = np.eye(4)*.01; other_cov = cov.copy()
        raw = np.zeros(4); other_raw = raw.copy()
        worker = initial_executor(); other_worker = initial_executor()
        rng = np.random.default_rng(914)
        feature_sign = np.array([-1,-1,-1,-1,1,-1,-1,-1,-1,1,1,-1,1,1,-1,1,1,1,-1,1])
        for tick in range(80):
            noise = rng.normal(0,[.03,.003,.01,.1]); other_noise = noise*np.array([-1,-1,-1,1])
            vraw = max(5.,raw[3]) if tick else max(5.,25.+noise[3])
            estimate,cov,raw,v,k = measure13(state,25.,path,noise,1,estimate,cov,raw,tick==0,1.)
            other_estimate,other_cov,other_raw,ov,ok = measure13(mirrored,25.,mirrored_path,other_noise,1,other_estimate,other_cov,other_raw,tick==0,1.)
            np.testing.assert_allclose(other_estimate,-estimate,rtol=0,atol=1e-13)
            np.testing.assert_array_equal(cov,other_cov)
            np.testing.assert_allclose(other_raw,raw*np.array([-1,-1,-1,1]),rtol=0,atol=1e-13)
            self.assertEqual(v,ov);self.assertAlmostEqual(k,-ok,places=15)
            f = features13(state,estimate,vraw,path,worker,tick,2)
            of = features13(mirrored,other_estimate,vraw,mirrored_path,other_worker,tick,2)
            np.testing.assert_allclose(of,f*feature_sign,rtol=0,atol=1e-7)
            baseline,gain = lqr(estimate,v,k,self.gains)
            other_baseline,other_gain = lqr(other_estimate,ov,ok,self.gains)
            self.assertAlmostEqual(other_baseline,-baseline,places=13)
            a = execution_step13(worker,tick*.01,.04,2,baseline,estimate,state[5],v,k,gain,3)
            b = execution_step13(other_worker,tick*.01,-.04,2,other_baseline,other_estimate,mirrored[5],ov,ok,other_gain,3)
            self.assertAlmostEqual(a[0],-b[0],places=13)
            self.assertEqual(a[1:],b[1:])
            state = advance(state,a[0],25.,.6,.65)
            mirrored = advance(mirrored,b[0],25.,.6,.65)
            np.testing.assert_allclose(mirrored,state*np.array([1.,-1.,-1.,-1.,-1.,-1.]),rtol=0,atol=1e-12)

    def test_balanced_cost_matches_independent_components_including_initial_rate(self):
        for speed in (15.,20.,25.):
            estimate = np.array([.12,-.04,.015,.03]); k = .003; gain = GAINS[int(speed)]
            lateral,heading,rate,first_rate = independent_cost_terms(estimate,.02,-.06,speed,k,gain)
            self.assertAlmostEqual(cost13(estimate,.02,-.06,speed,k,gain,1),lateral,places=12)
            for variant,weights in ((2,(.05,.01)),(3,(.10,.03)),(4,(.20,.10))):
                self.assertEqual(objective_weights13(variant),weights)
                h,r = weights
                expected = lateral+h*heading+r*rate
                self.assertAlmostEqual(cost13(estimate,.02,-.06,speed,k,gain,variant),expected,places=12)
                self.assertGreater(expected-(lateral+h*heading+r*(rate-first_rate)),0.)
                self.assertAlmostEqual(cost13(-estimate,-.02,.06,speed,-k,gain,variant),expected,places=12)

    def test_legacy_and_lateral_execution_delegate_exactly(self):
        estimate = np.array([.03,0.,.005,0.]);k=.001
        baseline,gain = lqr(estimate,25.,k,self.gains)
        for variant in (0,1):
            for service in (0,1,2,10):
                for sparse in (False,True):
                    old=initial_executor();new=initial_executor()
                    for tick in range(35):
                        args=(tick*.01,.08*np.sin(tick/7),service,baseline,estimate,0.,25.,k,gain)
                        submit=not sparse or tick%5==0
                        a=execution_step(old,*args,False,submit) if variant==0 else execution_step12(old,*args,np.zeros(3),2,submit)
                        b=execution_step13(new,*args,variant,submit)
                        self.assertEqual(a,b);np.testing.assert_array_equal(old,new)

    def test_balanced_gate_age_envelope_and_motion_bounds(self):
        estimate=np.array([.03,0.,.005,0.]);k=.001
        baseline,gain=lqr(estimate,25.,k,self.gains)
        for variant in (2,3,4):
            worker=initial_executor()
            a=execution_step13(worker,0.,.08,0,baseline,estimate,0.,25.,k,gain,variant,False)
            self.assertEqual(a[:3],(baseline,0.,0))
            for tick in range(30):
                a=execution_step13(worker,tick*.01,.08,10,baseline,estimate,0.,25.,k,gain,variant)
                self.assertEqual(a[0],baseline);self.assertEqual(a[1],0.)
            outside=estimate.copy();outside[0]=1.51;worker=initial_executor()
            a=execution_step13(worker,0.,.08,0,baseline,outside,0.,25.,k,gain,variant)
            self.assertEqual(a[:3],(baseline,0.,3))
            # Exercise both proposal signs and actuator offsets, including
            # actual earned decisions rather than only vacuous bound checks.
            earned=0
            for actuator in (-.03,0.,.03):
                for proposal in (-1.,1.):
                    worker=initial_executor();prior=0.
                    for tick in range(20):
                        a=execution_step13(worker,tick*.01,proposal,0,baseline,estimate,actuator,25.,k,gain,variant)
                        command,weight,reason,_=a
                        self.assertLessEqual(abs(command),.5)
                        self.assertLessEqual(weight,min(.5,prior+.05)+1e-12)
                        self.assertLessEqual(abs(command-baseline),.0400000001)
                        if reason==6:
                            earned+=1;self.assertGreaterEqual(worker[1],3)
                            j0=cost13(estimate,actuator,baseline,25.,k,gain,variant)
                            j1=cost13(estimate,actuator,command,25.,k,gain,variant)
                            self.assertGreaterEqual(j0-j1,max(1e-7,.01*j0))
                        prior=weight
            # A small deliberately suboptimal baseline command on a zero-error
            # straight-road fixture gives a known useful negative correction.
            # This isolates persistence/ramp behavior without assuming every
            # realistic LQR state must offer a qualifying correction.
            worker=initial_executor();zero=np.zeros(4)
            for tick in range(3):
                a=execution_step13(worker,tick*.01,-.08,0,.01,zero,0.,25.,0.,gain,variant)
                self.assertEqual(a[2],5 if tick<2 else 6)
            self.assertAlmostEqual(a[0],.006,places=14)
            self.assertEqual(a[1],.05)
            a=execution_step13(worker,.12,-.08,0,.01,zero,0.,25.,0.,gain,variant,False)
            self.assertEqual(a[:3],(.01,0.,1));self.assertEqual(worker[1],0.)
            for tick in range(3):
                a=execution_step13(worker,.13+tick*.01,-.08,0,.01,zero,0.,25.,0.,gain,variant)
                self.assertEqual(a[2],5 if tick<2 else 6)


if __name__=='__main__':
    unittest.main()
