import unittest
import copy
import numpy as np
from bootstrap import RESEARCH
from core import Sensor,GAINS,path_values
from comparison import configure_lqr
from execution import Execution,matched_lqr
from gating import Gate
from plant import advance
from kernels import measure,lqr,execution_step,select,initial_executor,branch_cost,simulate


class OracleContracts(unittest.TestCase):
    def setUp(self):
        configure_lqr();self.gains=np.array([GAINS[v] for v in (15,20,25)])

    def test_observer_and_observed_speed_match_frozen_sensor(self):
        path=(0,2.5,120.,.3)
        for speed,noise_scale,delay in [(15.,1.,0),(25.,2.,1),(20.,1.,1)]:
            sensor=Sensor(123,noise_scale,delay)
            scales=np.array([.03,np.deg2rad(.17),.01,.1])*noise_scale
            noises=np.random.default_rng(123).normal(0,scales,size=(80,4))
            y,h,_=path_values(0,path);state=np.array([0.,y+.15,h+.01,0.,0.,0.])
            estimate=np.zeros(4);cov=np.eye(4)*.01;previous=np.zeros(4)
            for tick in range(80):
                obs,expected,kappa=sensor.measure(state,speed,path)
                estimate,cov,previous,v,k=measure(state,speed,path,noises[tick],delay,estimate,cov,previous,tick==0,noise_scale)
                np.testing.assert_allclose(estimate,expected,rtol=0,atol=1e-12)
                np.testing.assert_allclose(cov,sensor.cov,rtol=0,atol=1e-14)
                np.testing.assert_allclose(previous,sensor.queue[-1],rtol=0,atol=1e-14)
                self.assertEqual(v,float(obs[4])*25);self.assertAlmostEqual(k,kappa,places=14)
                a,ka=lqr(expected,v,k,self.gains);b,kb=matched_lqr(expected,v,k)
                self.assertAlmostEqual(a,b,places=13);np.testing.assert_allclose(ka,kb,rtol=0,atol=1e-14)
                state=advance(state,.01*np.sin(tick/10),speed,.9,1.)

    def test_worker_and_gate_match_original_on_release_persistence_and_stale(self):
        reasons=['missing','age','sequence','envelope','cost','persistence','earned','nonfinite','prediction_invalid']
        for service in (0,1,2,10):
            original=Execution();numeric=initial_executor()
            for tick in range(100):
                estimate=np.array([.2*np.sin(tick/10),0.,.01,0.]);v=20.;k=.001
                baseline,gain=matched_lqr(estimate,v,k);proposal=.08 if tick%20<10 else -.04
                expected,info=original.step(tick*.01,proposal,service,baseline,estimate,0.,v,k,gain)
                actual,w,reason,submitted=execution_step(numeric,tick*.01,proposal,service,baseline,estimate,0.,v,k,gain,False)
                self.assertAlmostEqual(actual,expected,places=13);self.assertEqual(w,info['gate_weight'])
                self.assertEqual(reasons[reason],info['gate_reason']);self.assertEqual(submitted,info['submitted'])
                self.assertEqual(numeric[0],original.gate.weight);self.assertEqual(numeric[1],original.gate.good)
                if original.packet:self.assertEqual(tuple(numeric[3:6]),original.packet)
                if original.pending:self.assertEqual(tuple(numeric[7:10]),original.pending[1])

    def test_branch_cost_matches_original_python_cloned_rollout(self):
        path=(0,2.5,120.,.3);speed=25.;noise_scale=2.;delay=1
        noises=np.random.default_rng(444).normal(0,np.array([.03,np.deg2rad(.17),.01,.1])*noise_scale,size=(50,4))
        sensor=Sensor(444,noise_scale,delay);y,h,_=path_values(0,path)
        state=np.array([0.,y+.15,h+.01,0.,0.,0.]);worker=Execution()
        obs,estimate,kappa=sensor.measure(state,speed,path)
        # Use a real warm gate/held packet, not only cold-start zero authority.
        worker.gate.weight=.1;worker.gate.good=4;worker.gate.last_sequence=3
        worker.sequence=3;worker.packet=(3,0.,-.04);worker.last_command=.01
        numeric=initial_executor();numeric[:3]=[.1,4,3];numeric[3:6]=worker.packet;numeric[10]=3;numeric[11]=.01
        before=[x.copy() for x in (state,estimate,sensor.cov,sensor.queue[-1],numeric,noises)]
        candidate=-.04
        cost=branch_cost(state,estimate,sensor.cov,sensor.queue[-1],numeric,0,candidate,2,speed,path,.6,.65,
            noises,delay,noise_scale,float(obs[4])*25,kappa,self.gains,False,20)
        z=state.copy();s=copy.deepcopy(sensor);w=copy.deepcopy(worker);value=0.;o=obs;est=estimate;k=kappa
        for tick in range(20):
            v=float(o[4])*25;base,gain=matched_lqr(est,v,k)
            command,_=w.step(tick*.01,candidate,2,base,est,z[5],v,k,gain)
            z=advance(z,command,speed,.6,.65);error=z[1]-path_values(z[0],path)[0];value+=error*error
            if tick<19:o,est,k=s.measure(z,speed,path)
        self.assertAlmostEqual(cost,value,places=11)
        for old,new in zip(before,(state,estimate,sensor.cov,sensor.queue[-1],numeric,noises)):np.testing.assert_array_equal(old,new)

    def test_five_action_selection_is_nonmutating_and_minimizes_its_window_only(self):
        path=(0,2.5,120.,.3);speed=20.;sensor=Sensor(1)
        y,h,_=path_values(0,path);state=np.array([0.,y+.15,h+.01,0.,0.,0.])
        obs,estimate,k=sensor.measure(state,speed,path);worker=initial_executor();noises=np.zeros((50,4))
        candidates=np.array([-.08,-.04,0.,.04,.08]);before=worker.copy()
        proposal,index,costs=select(state,estimate,sensor.cov,sensor.queue[-1],worker,0,0,speed,path,.9,1.,noises,0,1.,float(obs[4])*25,k,self.gains,False,20,candidates)
        self.assertEqual(proposal,candidates[index]);self.assertEqual(costs[index],min(costs));np.testing.assert_array_equal(worker,before)
        # Every100ms packet is stale; equal branch costs choose zero, never open gates.
        proposal,index,costs=select(state,estimate,sensor.cov,sensor.queue[-1],worker,0,10,speed,path,.9,1.,noises,0,1.,float(obs[4])*25,k,self.gains,False,20,candidates)
        self.assertEqual(proposal,0.);np.testing.assert_array_equal(costs,np.full(5,costs[0]))

    def test_actual_simulation_matches_recorded_development_baseline(self):
        import csv,json,math
        grid=json.loads((RESEARCH/'revision6/protocol.json').read_text())
        with (RESEARCH.parent/'results/revision6-correction/evaluation/episodes.csv').open() as f:
            reference_rows=list(csv.DictReader(f))
        for region in ('nominal','sensor_stress'):
            speed=25;path=tuple(float(x) for x in grid['paths']['sine120']);case=grid['scenarios'][region]
            seed=grid['development_noise_base']+2500+list(grid['scenarios']).index(region)
            scheduled=math.ceil((220/speed+2)/.01)
            noises=np.random.default_rng(seed).normal(0,np.array([.03,np.deg2rad(.17),.01,.1])*case['noise'],size=(scheduled+21,4))
            trace,failed,calls=simulate(0,float(speed),path,case['mu'],case['stiffness'],float(case['noise']),case['sensor_delay_steps'],
                case['service_ticks'],noises,self.gains,np.array([-.08,-.04,0.,.04,.08]),20,scheduled)
            expected=next(r for r in reference_rows if r['seed']=='301' and r['speed']=='25' and r['path']=='sine120' and r['scenario']==region and r['method']=='lqr')
            self.assertFalse(failed);self.assertEqual(calls,0)
            self.assertAlmostEqual(float(np.sqrt(np.mean(trace[:,6]**2))),float(expected['rmse']),places=10)

    def test_bypass_keeps_worker_age_and_physical_command_bounds(self):
        for service in (0,2,10):
            worker=initial_executor();estimate=np.zeros(4);baseline=.49;gain=self.gains[1]
            for tick in range(30):
                command,weight,reason,_=execution_step(worker,tick*.01,.08,service,baseline,estimate,0.,20.,0.,gain,True)
                self.assertLessEqual(abs(command),.5)
                if worker[3]<0 or tick*.01-worker[4]>=.05:
                    self.assertEqual(command,baseline);self.assertEqual(weight,0.)
                else:
                    self.assertEqual(command,.5);self.assertEqual(weight,1.)
                if service==10:self.assertEqual(command,baseline)


if __name__=='__main__':unittest.main()
