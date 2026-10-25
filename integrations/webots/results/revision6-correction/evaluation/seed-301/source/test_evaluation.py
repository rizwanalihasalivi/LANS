import unittest
import numpy as np
from bootstrap import RESEARCH
from comparison import configure_lqr
from execution import matched_lqr
from mpc import MPC
from evaluate import episode,P
from core import Sensor,path_values
from execution_env import ExecutionEnv
from execution import Execution


class EvaluationContracts(unittest.TestCase):
    def setUp(self):configure_lqr()
    def test_mpc_equilibrium_bounds_and_direction(self):
        for v in (15.,20.,25.):
            m=MPC();z=np.zeros(4)
            u=m.command(z,0.,v,[0.,0.,0.],0.)
            self.assertLess(abs(u),1e-8);self.assertEqual(m.fallbacks,0)
            z[0]=.2;base,_=matched_lqr(z,v,0.)
            u=m.command(z,0.,v,[0.,0.,0.],base)
            self.assertLess(u,0.);self.assertLessEqual(abs(u),.0176);self.assertEqual(m.fallbacks,0)
            k=.001;vy=(1.4*v-1650*1.2*v**3/(2.6*80000))*k
            z=np.array([0.,vy,-vy/v,v*k]);ff=(2.6+1650/2.6*(1.4/80000-1.2/80000)*v*v)*k
            u=MPC().command(z,ff,v,[k,k,k],ff)
            self.assertAlmostEqual(u,ff,places=4)

    def test_fresh_noise_ids_and_method_coverage(self):
        ids=[P['development_noise_base']+i*10000+v*100+j*10+k for i in range(3) for v in P['speeds'] for j in range(2) for k in range(6)]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(len(ids)*len(P['methods']),P['episodes'])

    def test_deployment_trace_matches_training_execution(self):
        # Recreate the same explicit development initial condition in the training
        # environment; compare the independent efficient evaluator's first80 ticks.
        import tempfile,gzip,csv
        seed=301;speed=25;path=tuple(P['paths']['dlc220']);region='latency20';case=P['scenarios'][region]
        noise=P['development_noise_base']+speed*100+10+4
        class Constant:
            def predict(self,*args,**kwargs):return np.array([1.]),None
        with tempfile.TemporaryDirectory() as folder:
            from pathlib import Path
            file=Path(folder)/'trace.csv.gz'
            episode(Constant(),'execution',seed,speed,'dlc220',region,file)
            with gzip.open(file,'rt') as f:rows=list(csv.DictReader(f))
        env=ExecutionEnv(seed=seed,service_ticks=2);env.reset(seed=seed)
        env.speed=speed;env.path=path;env.mu=case['mu'];env.stiffness=case['stiffness']
        y,h,_=path_values(0,path);env.state=np.array([0.,y+.15,h+.01,0.,0.,0.])
        env.sensor=Sensor(noise,case['noise'],case['sensor_delay_steps']);env.execution=Execution()
        env.obs,env.estimate,env.kappa=env.sensor.measure(env.state,speed,path)
        for row in rows[:80]:
            _,_,_,_,info=env.step([1.])
            self.assertAlmostEqual(float(row['command']),info['command_rad'],places=12)
            self.assertAlmostEqual(float(row['error']),info['error'],places=12)
        env.close()


if __name__=='__main__':unittest.main()
