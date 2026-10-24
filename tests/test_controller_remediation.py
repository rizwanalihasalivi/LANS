import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
import numpy as np
from envs.path_tracking_env import PathTrackingEnv
from envs.residual_path_env import ResidualPathEnv
from models.bicycle_model import discretize_error_state_model
from controllers.lqr_controller import get_lqr_controller
from controllers.lans_controller import LANSController
from tools.controller_review.train import set_learning_rate


class Contracts(unittest.TestCase):
    def test_curved_reference_does_not_move_zero_steering_vehicle(self):
        env=PathTrackingEnv('eval');env.reset(seed=1)
        for _ in range(700):
            _,_,done,trunc,info=env.step([0.])
            self.assertAlmostEqual(info['y_phys'],0.)
            self.assertAlmostEqual(info['error'],-info['y_ref'])
            if done or trunc:break
        self.assertTrue(done)
        self.assertGreater(info['y_ref'],2.5)
        with self.assertRaises(RuntimeError):env.step([0.])

    def test_residual_fused_exactly_once(self):
        a=ResidualPathEnv('eval');b=PathTrackingEnv('eval')
        options={'lateral_error':.2,'heading_error':.01}
        a.reset(seed=2,options=options);b.reset(seed=2,options=options)
        for residual in (0.,.2,-.3):
            u=np.clip(a.lqr_control(a.state,a.curvature())+.08*residual,-.5,.5)
            _,_,_,_,info=a.step([residual]);b.step([u])
            np.testing.assert_allclose(a.physical,b.physical)
            self.assertEqual(info['total_steer'],u)

    def test_speed_seed_and_preview(self):
        a=ResidualPathEnv();b=ResidualPathEnv();a.target_speed=b.target_speed=15.
        x,_=a.reset(seed=5);y,_=b.reset(seed=5)
        np.testing.assert_array_equal(x,y);np.testing.assert_array_equal(a.y_ref,b.y_ref)
        self.assertEqual(x[4],15.);a.step([0.]);self.assertAlmostEqual(a.car_x,a.x_position)
        self.assertNotEqual(tuple(get_lqr_controller(15)[0]),tuple(get_lqr_controller(25)[0]))
        env=PathTrackingEnv('eval',15.);obs,_=env.reset(seed=1)
        c=LANSController(15.);_,info=c.step(env.y_actual,env._get_reference_y(0),env.physical[2],env._get_reference_heading(0),0,0,env.curvature(),preview_y=[env._get_reference_y(i*.15) for i in range(1,5)])
        np.testing.assert_allclose(info['observation'],obs)

    def test_zoh_integrator(self):
        a,b=discretize_error_state_model(np.zeros((2,2)),np.array([[1.],[2.]]),.1)
        np.testing.assert_allclose(a,np.eye(2));np.testing.assert_allclose(b,[[.1],[.2]])

    def test_missing_policy_fails(self):
        with self.assertRaises(ValueError):LANSController(load_ppo_model=True)

    def test_effective_learning_rate(self):
        from stable_baselines3 import PPO
        model=PPO('MlpPolicy',ResidualPathEnv(),n_steps=10,batch_size=10)
        set_learning_rate(model,1e-5)
        self.assertEqual(model.lr_schedule(.4),1e-5)
        self.assertEqual(model.policy.optimizer.param_groups[0]['lr'],1e-5)

if __name__=='__main__':unittest.main()
