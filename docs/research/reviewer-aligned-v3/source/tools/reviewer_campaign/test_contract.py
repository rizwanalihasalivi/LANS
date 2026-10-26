import unittest
from unittest.mock import patch
import common
import numpy as np
from supervisor import Controller, observation
from environment import CausalEnv


class Contracts(unittest.TestCase):
    def test_pending_result_and_forecast_never_enter_observation(self):
        a, b = Controller(), Controller()
        a.submit(0., -.08, .02)
        b.submit(0., .08, 1.)
        args = (np.zeros(6), np.zeros(4), 20., [0., 0., 0.])
        np.testing.assert_array_equal(observation(*args, a, 0.), observation(*args, b, 0.))
        self.assertIsNone(a.packet)
        self.assertFalse(a.submit(.01, 0., 0.))
        a.deliver(.02)
        self.assertEqual(a.packet, (1, 0., -.08))

    def test_boundary_rejects_and_resets(self):
        ctrl = Controller('fixed')
        ctrl.submit(0., .08, 0.)
        ctrl.weight = .5
        command, why = ctrl.choose(.05, .03, np.zeros(4), 0., 20., 0., np.ones(4))
        self.assertEqual((command, why, ctrl.weight), (.03, 'age', 0.))

    def test_out_of_order_and_invalid(self):
        ctrl = Controller()
        ctrl.last_sequence = 5
        ctrl.packet = (4, 0., .04)
        self.assertEqual(ctrl.choose(0., 0., np.zeros(4), 0., 20., 0., np.ones(4))[1], 'sequence')
        ctrl.packet = (6, 0., float('nan'))
        self.assertEqual(ctrl.choose(0., 0., np.zeros(4), 0., 20., 0., np.ones(4))[1], 'nonfinite')

    def test_mirrored_plant_and_noise(self):
        a = CausalEnv(case=(20, 'dlc220', 1, 'nominal', 1234), mode='lqr')
        b = CausalEnv(case=(20, 'dlc220', -1, 'nominal', 1234), mode='lqr')
        a.reset(); b.reset()
        for _ in range(50):
            _, _, _, _, x = a.step(2)
            _, _, _, _, y = b.step(2)
            self.assertAlmostEqual(x['command'], -y['command'], places=12)
            self.assertAlmostEqual(x['lateral_error'], -y['lateral_error'], places=12)

    def test_one_second_queue_keeps_local_control_active(self):
        env = CausalEnv(case=(20, 'dlc220', 1, 'stall1000', 1234))
        env.reset()
        for _ in range(110):
            obs, _, failed, _, info = env.step(4)
            self.assertFalse(failed)
            self.assertEqual(info['command'], info['baseline'])
            self.assertEqual(info['weight'], 0.)
            self.assertTrue(np.all(obs[[14,15,16,17,19]] == 0))
        self.assertGreater(env.state[0], 20.)

    def test_predictive_recovery_and_immediate_age_revocation(self):
        ctrl = Controller()
        ctrl.submit(0., -.08, 0.)
        with patch('supervisor.predicted_cost', side_effect=lambda z,d,u,old,v,k,g: (u+.1)**2):
            for t in (0., .01):
                command, reason = ctrl.choose(t, 0., np.zeros(4), 0.,20.,0.,np.ones(4))
                self.assertEqual(reason, 'recovery')
                self.assertEqual(command, 0.)
            command, reason = ctrl.choose(.02, 0., np.zeros(4),0.,20.,0.,np.ones(4))
            self.assertEqual(reason, 'accepted')
            self.assertLess(command, 0.)
            self.assertLessEqual(ctrl.weight, .05)
            self.assertAlmostEqual(command, ctrl.weight*ctrl.packet[2])
            self.assertEqual(ctrl.choose(.05, 0., np.zeros(4),0.,20.,0.,np.ones(4)), (0., 'age'))

    def test_predictor_left_right_symmetry(self):
        from supervisor import predicted_cost
        z=np.array([.15,.02,.01,.03]);gain=np.array([.2,.1,.3,.1])
        a=predicted_cost(z,.02,-.03,.01,20.,.001,gain)
        b=predicted_cost(-z,-.02,.03,-.01,20.,-.001,gain)
        self.assertAlmostEqual(a,b,places=12)


if __name__ == '__main__':
    unittest.main()
