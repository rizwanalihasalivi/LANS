import boot4
import copy
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
from aligned import AlignedController,AlignedEnv,trajectory_cost
from interface4 import ScalarAligned,FreshController,AsyncEnv,planner
from scalar_cost import scalar_cost


class Contracts(unittest.TestCase):
    def test_scalar_matches_frozen_cost(self):
        rng=np.random.default_rng(4731)
        for _ in range(2000):
            z=rng.normal(size=4)*np.array([.3,.1,.03,.1]);a=float(rng.uniform(-.1,.1));v=float(rng.uniform(15,25))
            ks=rng.normal(size=3)*.002;gain=np.array([.2,.1,.3,.1]);f,r=rng.uniform(-.08,.08,2);w=float(rng.uniform(0,.25))
            ref=trajectory_cost(z,a,v,ks,gain,f,r,w);got=scalar_cost(z,a,v,ks,gain,f,r,w)
            self.assertAlmostEqual(got,ref,delta=1e-11*max(1.,abs(ref)))
    def test_optimized_closed_loop_command_parity(self):
        rng=np.random.default_rng(4732)
        for scenario in ('nominal','tire','delay20','delay100'):
            case=(20,'dlc220',1,scenario,1376000901)
            a=AlignedEnv(case=case);b=AlignedEnv(case=case);a.reset();b.reset()
            b.ctrl=ScalarAligned();b.ctrl.previews=a.ctrl.previews.copy()
            for _ in range(250):
                action=int(rng.integers(5));ra=a.step(action)[4];rb=b.step(action)[4]
                self.assertEqual(ra['reason'],rb['reason']);self.assertAlmostEqual(ra['command'],rb['command'],places=11)
                np.testing.assert_allclose(a.state,b.state,rtol=0,atol=1e-11)
    def test_freshness_does_not_exponentially_suppress_valid_authority(self):
        c=FreshController();c.packet=(1,0.,.08)
        with patch('interface4.scalar_cost',side_effect=[1.,.9]*3):
            for t in (.01,.02,.04):command,reason=c.choose(t,.01,np.zeros(4),0.,20.,0.,np.ones(4))
        self.assertEqual(reason,'accepted');self.assertAlmostEqual(c.weight,.05)
        self.assertEqual(c.choose(.05,.03,np.zeros(4),0.,20.,0.,np.ones(4)),(.03,'age'))
        self.assertEqual((c.filtered,c.weight,c.good),(0.,0.,0))
    def test_zero_service_is_next_tick_and_policy_oracles_remain_zero(self):
        e=AsyncEnv((20,'dlc220',1,'nominal',1376000902),'ppo');e.reset()
        self.assertEqual(e.service,.01)
        first=e.step(4)[4];second=e.step(4)[4]
        self.assertEqual(first['packet_seq'],-1);self.assertEqual(first['command'],first['baseline'])
        self.assertEqual(second['packet_age_s'],.01);self.assertTrue(np.all(e.obs[[14,15,16,17,19]]==0))
    def test_one_second_worker_stall_exact_local_lqr(self):
        case=(20,'dlc220',1,'stall1000',1376000903)
        a=AsyncEnv(case,'ppo');b=AsyncEnv(case,'lqr');a.reset();b.reset()
        for _ in range(120):
            ra=a.step(4)[4];rb=b.step(2)[4]
            self.assertEqual(ra['command'],rb['command']);np.testing.assert_array_equal(a.state,b.state)
    def test_planner_only_observable_state_and_history(self):
        e=AsyncEnv((20,'dlc220',1,'nominal',1376000904),'planner');e.reset()
        class ActuatorOnly:
            def __getitem__(self,index):
                if index!=5:raise AssertionError('privileged physical state requested')
                return 0.
        view=SimpleNamespace(ctrl=e.ctrl,tick=e.tick,baseline=e.baseline,estimate=e.estimate,
            state=ActuatorOnly(),measured_speed=e.measured_speed,curvature=e.curvature,gain=e.gain)
        self.assertIn(planner(view),(-.08,-.04,0.,.04,.08))


if __name__=='__main__':unittest.main()
