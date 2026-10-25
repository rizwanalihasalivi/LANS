"""Regression probes for active root contracts and evidence-pairing gaps."""
import csv
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import numpy as np
from gymnasium import spaces
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from controllers.policy_bundle import save_bundle, validate_spaces, PolicyBundle
from controllers.observation_builder import ObservationBuilder
from envs.path_tracking_env import PathTrackingEnv
from tools.controller_review.compare import run
from tools.controller_review.report import summarize


class RootAuditContracts(unittest.TestCase):
    def write(self, folder, rows):
        path=Path(folder)/'episodes.csv'
        with path.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
        return path

    def test_different_noise_ids_are_not_paired(self):
        rows=[dict(seed=701,noise_id=520001500+i,method=m,survived=True,penalized_rmse=.1)
              for i,m in enumerate(['lqr','student'])]
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'paired condition'):
                summarize(self.write(folder,rows))

    def test_horizon_without_raw_score_is_explicit_error(self):
        row=dict(seed=1,method='lqr',survived=True,steps=10,scheduled_steps=10,penalized_rmse=.1)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'raw RMSE'):
                summarize(self.write(folder,[row]))

    def test_full_command_model_cannot_be_packaged_as_residual(self):
        from stable_baselines3.common.vec_env import DummyVecEnv,VecNormalize
        env=VecNormalize(DummyVecEnv([PathTrackingEnv]))
        try:
            with tempfile.TemporaryDirectory() as folder:
                output=Path(folder)/'invalid'
                with self.assertRaisesRegex(ValueError,'residual environments'):
                    save_bundle(output,None,env)
                self.assertFalse(output.exists())
            with self.assertRaisesRegex(ValueError,'normalized action'):
                validate_spaces(SimpleNamespace(observation_space=env.observation_space,action_space=env.action_space))
        finally:env.close()

    def test_existing_valid_bundle_still_loads(self):
        folder=Path(__file__).resolve().parents[1]/'integrations/webots/results/controller-remediation/root-smoke'
        policy=PolicyBundle(folder)
        try:
            obs,_=PathTrackingEnv().reset(seed=101)
            action,_=policy.predict(obs)
            self.assertEqual(action.shape,(1,));self.assertTrue(np.isfinite(action).all())
        finally:policy.normalizer.close()

    def test_comparison_requires_policy_and_exposes_penalty_inputs(self):
        with self.assertRaisesRegex(ValueError,'actual policy'):run('residual',1,25,0)
        with self.assertRaisesRegex(ValueError,'method'):run('ppo',1,25,0)
        row,_=run('lqr',1,25,0)
        self.assertEqual(row['scheduled_steps'],1000)
        self.assertIn('rmse',row)
        with tempfile.TemporaryDirectory() as folder:
            table,_=summarize(self.write(folder,[row]))
        self.assertAlmostEqual(table[0]['mean_episode_rmse_m'],row['penalized_rmse'])

    def test_speed_change_refreshes_observed_error_rates(self):
        env=PathTrackingEnv('eval');env.reset(options={'heading_error':.1})
        env.target_speed=15.
        self.assertAlmostEqual(env._get_observation()[1],1.5)
        self.assertAlmostEqual(env._get_observation()[4],15.)

    def test_preview_dimension_rejected_at_construction(self):
        with self.assertRaisesRegex(ValueError,'four previews'):ObservationBuilder(lookahead_steps=5)

if __name__=='__main__':unittest.main()
