import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from realtime_kernels import np,solve_spd3,measure_fast
from kernels import measure,path_values
from data import G

class AlgebraParity(unittest.TestCase):
    def test_spd_solve_and_invalid_covariance(self):
        rng=np.random.default_rng(910)
        for _ in range(200):
            m=rng.normal(size=(3,3));a=m@m.T+np.eye(3)*.01;b=rng.normal(size=(3,4))
            np.testing.assert_allclose(solve_spd3(a,b),np.linalg.solve(a,b),atol=2e-10,rtol=1e-10)
        with self.assertRaises(ValueError):solve_spd3(-np.eye(3),np.ones((3,4)))
    def test_observer_trajectory_parity(self):
        rng=np.random.default_rng(911)
        for speed in (15.,20.,25.):
            for delay in (0,1):
                for path in G['paths'].values():
                    path=tuple(float(v) for v in path)
                    old=(np.zeros(4),np.eye(4)*.01,np.zeros(4));new=tuple(x.copy() for x in old)
                    for tick in range(100):
                        x=speed*.01*tick;y,h,_=path_values(x,path)
                        state=np.array([x,y+.1,h+.01,.01,.01,.02]);noise=rng.normal(size=4)*np.array([.03,.003,.01,.1])
                        original=measure(state,speed,path,noise,delay,*old,tick==0,1.)
                        optimized=measure_fast(state,speed,path,noise,delay,*new,tick==0,1.)
                        for a,b in zip(original,optimized):np.testing.assert_allclose(a,b,atol=1e-11,rtol=1e-10)
                        old=original[:3];new=optimized[:3]

if __name__=='__main__':unittest.main()
