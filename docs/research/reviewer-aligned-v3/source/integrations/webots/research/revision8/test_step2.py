import unittest
import numpy as np
from bootstrap import RESEARCH
from core import Sensor,GAINS,path_values
from comparison import configure_lqr
from execution import Execution,matched_lqr
from kernels import measure,execution_step,branch_cost,initial_executor
from teacher import choose,expected_cost,features
from data import noise_inputs,P,G


class TeacherContracts(unittest.TestCase):
    def setUp(self):configure_lqr();self.gains=np.array([GAINS[v] for v in (15,20,25)])

    def test_expected_cost_matches_independent_forecasts_not_actual_future(self):
        path=(0.,2.5,120.,.3);speed=20.;sensor=Sensor(1);y,h,_=path_values(0,path)
        state=np.array([0.,y+.15,h+.01,0.,0.,0.]);obs,estimate,k=sensor.measure(state,speed,path)
        worker=initial_executor();forecast=np.random.default_rng(99).normal(0,.01,size=(21,4));tick=7
        before=[a.copy() for a in (state,estimate,sensor.cov,sensor.queue[-1],worker,forecast)]
        result=expected_cost(state,estimate,sensor.cov,sensor.queue[-1],worker,tick,-.04,0,speed,path,.9,1.,forecast,0,1.,float(obs[4])*25,k,self.gains)
        values=[]
        for sign in (0.,1.,-1.):
            future=np.zeros((50,4));future[tick+1:tick+20]=sign*forecast[1:20]
            values.append(branch_cost(state,estimate,sensor.cov,sensor.queue[-1],worker,tick,-.04,0,speed,path,.9,1.,future,0,1.,float(obs[4])*25,k,self.gains,False,20))
        self.assertAlmostEqual(result,float(np.mean(values)),places=12)
        for old,new in zip(before,(state,estimate,sensor.cov,sensor.queue[-1],worker,forecast)):np.testing.assert_array_equal(old,new)
        actual_a=np.zeros((50,4));actual_b=np.ones((50,4))*999
        # Neither buffer is an argument to choose; replacing the future cannot change labels.
        def label(actual):return choose(state,estimate,sensor.cov,sensor.queue[-1],worker,tick,0,speed,path,.9,1.,forecast,0,1.,float(obs[4])*25,k,self.gains)
        a,cost_a=label(actual_a);b,cost_b=label(actual_b);self.assertEqual(a,b);np.testing.assert_array_equal(cost_a,cost_b)

    def test_features_match_original_actor_history_without_true_hidden_inputs(self):
        from plant import advance
        path=(0.,2.5,120.,.3);speed=25.;case=G['scenarios']['sensor_stress'];delay=1;service=2
        _,actual,_,_=noise_inputs(320000000,0,25,0,3,case,80)
        sensor=Sensor(320002503,2.,1);worker=Execution();numeric=initial_executor()
        y,h,_=path_values(0,path);state=np.array([0.,y+.15,h+.01,0.,0.,0.]);est=np.zeros(4);cov=np.eye(4)*.01;previous=np.zeros(4)
        for tick in range(80):
            raw_speed=max(5.,previous[3]) if tick else max(5.,speed+actual[tick,3])
            obs,expected,k=sensor.measure(state,speed,path)
            est,cov,previous,v,k=measure(state,speed,path,actual[tick],delay,est,cov,previous,tick==0,2.)
            a=features(state,est,raw_speed,path,numeric,tick,service)
            b=np.r_[obs,worker.context(tick*.01),service/10].astype(np.float32)
            np.testing.assert_array_equal(a,b)
            hidden=state.copy();hidden[1:5]+=100.
            np.testing.assert_array_equal(a,features(hidden,est,raw_speed,path,numeric,tick,service))
            base,gain=matched_lqr(expected,float(obs[4])*25,k)
            u,_=worker.step(tick*.01,-.04,service,base,expected,state[5],float(obs[4])*25,k,gain)
            z,_,_,_=execution_step(numeric,tick*.01,-.04,service,base,est,state[5],v,k,gain,False)
            self.assertAlmostEqual(u,z,places=12);state=advance(state,u,speed,.9,1.)

    def test_splits_and_teacher_forecast_streams_are_separate(self):
        sets=[]
        for split in P['splits'].values():
            ids={split['noise_base']+i*10000+v*100+j*10+k for i in range(split['noise_repetitions']) for v in G['speeds'] for j in range(2) for k in range(6)}
            for old in sets:self.assertFalse(ids&old)
            sets.append(ids)
        case=G['scenarios']['nominal']
        _,a,f,_=noise_inputs(320000000,0,15,0,0,case,30,0)
        _,b,g,_=noise_inputs(320000000,0,15,0,0,case,30,1)
        np.testing.assert_array_equal(a,b);self.assertFalse(np.array_equal(f,g));self.assertFalse(np.array_equal(a[1:21],f[0,1:21]))

    def test_student_accepts_observed_vector_only(self):
        from student import Student
        model=Student(np.zeros(20),np.ones(20))
        a,_=model.predict(np.zeros(20));self.assertIn(float(a[0]),[-1.,-.5,0.,.5,1.])
        with self.assertRaises(ValueError):model.predict(np.zeros(21))
        with self.assertRaises(ValueError):model.predict(np.full(20,np.nan))


if __name__=='__main__':unittest.main()
