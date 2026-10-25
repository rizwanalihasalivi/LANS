import unittest
import numpy as np
from bootstrap import RESEARCH
from environment import PilotEnv
from execution_env import ExecutionEnv


class TrainingContracts(unittest.TestCase):
    def test_execution_arm_is_original_training_environment(self):
        a=PilotEnv('execution',301);b=ExecutionEnv(seed=301,randomize=False,service_ticks=0)
        x,_=a.reset(seed=301);y,_=b.reset(seed=301);np.testing.assert_array_equal(x,y)
        for u in [.1,-.5,1.,0.]*10:
            x,r,d,t,i=a.step([u]);y,s,e,v,j=b.step([u])
            np.testing.assert_array_equal(x,y);self.assertEqual((r,d,t),(s,e,v))
            self.assertEqual(i['command_rad'],j['command_rad'])

    def test_direct_training_has_same_reset_units_and_reward_accounting(self):
        a=PilotEnv('direct',402);b=PilotEnv('execution',402)
        x,_=a.reset(seed=402);y,_=b.reset(seed=402);np.testing.assert_array_equal(x,y)
        for u in [-1.,0.,1.,.2]:
            obs,r,_,_,info=a.step([u])
            self.assertEqual(obs.shape,(20,));self.assertEqual(info['service_ticks'],0)
            self.assertAlmostEqual(info['command_rad'],np.clip(info['baseline_rad']+.08*u,-.5,.5))
            self.assertAlmostEqual(r,sum(info[k] for k in ['reward_tracking','reward_effort','reward_change','reward_survival','reward_relative']))


if __name__=='__main__':unittest.main()
