import unittest
import numpy as np
from gymnasium import spaces
from evaluate_execution import episode, predict
from execution_env import ExecutionEnv


class Constant:
    observation_space=spaces.Box(-np.inf,np.inf,(20,),dtype=np.float32)
    action_space=spaces.Box(-1.,1.,(1,),dtype=np.float32)
    def predict(self, observation, deterministic=True):
        return np.array([-.5],dtype=np.float32),None


class EvaluationContracts(unittest.TestCase):
    def test_training_and_evaluation_transitions_match_at_all_delays(self):
        policy=Constant()
        for ticks in (0,1,2,10):
            row,trace=episode(policy,101,ticks,trace=True)
            env=ExecutionEnv(seed=101,service_ticks=ticks)
            obs,_=env.reset(seed=101)
            errors=[]
            for actual in trace:
                obs,reward,failed,truncated,expected=env.step([-.5])
                errors.append(expected['error'])
                for key in ('command_rad','error','gate_weight','packet_sequence',
                            'observation_timestamp_s','executed_packet_residual','reward_relative'):
                    self.assertTrue(np.isclose(actual[key],expected[key],rtol=0,atol=0,equal_nan=True),key)
                self.assertEqual(actual['reward'],reward)
                if ticks==10:
                    self.assertEqual(actual['command_rad'],actual['baseline_rad'])
            self.assertEqual(row['steps'],len(trace))
            self.assertEqual(row['survived'],not failed)
            self.assertAlmostEqual(row['rmse'],np.sqrt(np.mean(np.square(errors))))
            env.close()

    def test_legacy_observation_and_nonfinite_actions_rejected(self):
        policy=Constant()
        with self.assertRaises(ValueError):predict(policy,np.zeros(9))
        policy.observation_space=spaces.Box(-np.inf,np.inf,(9,),dtype=np.float32)
        with self.assertRaises(ValueError):predict(policy,np.zeros(20))
        class Invalid(Constant):
            def predict(self,*args,**kwargs):return [np.nan],None
        with self.assertRaises(ValueError):predict(Invalid(),np.zeros(20))


if __name__=='__main__':unittest.main()
