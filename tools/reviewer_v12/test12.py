import boot12
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import torch
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.logger import configure
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from credit6 import CreditPPO, CreditBuffer
from env11 import Env as OldEnv
from env12 import Env
from forecast12 import forecast_state, Controller
from checkpoint12 import save, load, digest


class Credit(BaseCallback):
    def _on_step(self):
        self.model.rollout_buffer.next_credit = np.array([i['submitted'] for i in self.locals['infos']], np.float32)
        return True


def model_for_test():
    env = VecNormalize(DummyVecEnv([lambda: Env(seed=123, source='ppo')]), norm_obs=False)
    m = CreditPPO('MlpPolicy', env, seed=555, n_steps=8, batch_size=8, n_epochs=2,
                  policy_kwargs=dict(net_arch=dict(pi=[8], vf=[8])), device='cpu')
    m.rollout_buffer = CreditBuffer(8, m.observation_space, m.action_space,
                                    device='cpu', gamma=m.gamma, gae_lambda=m.gae_lambda, n_envs=1)
    m.set_logger(configure(None, []))
    m._setup_learn(24, Credit(), reset_num_timesteps=True)
    # Cross an automatic time-limit reset after the first checkpoint.
    m.env.venv.envs[0].horizon = 10
    return m


def update(m):
    cb = Credit(); cb.init_callback(m)
    assert m.collect_rollouts(m.env, cb, m.rollout_buffer, m.n_steps)
    m._update_current_progress_remaining(m.num_timesteps, 24)
    m.train()


class Contracts(unittest.TestCase):
    def test_resume_same_as_uninterrupted_including_optimizer_and_environment(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            first = model_for_test(); update(first)
            save(first, root, 'test-signature')
            for _ in range(2): update(first)
            state = {n: p.detach().clone() for n, p in first.policy.state_dict().items()}
            optimizer = first.policy.optimizer.state_dict()
            second, env, meta = load(root, 'test-signature')
            second.set_logger(configure(None, []))
            second._setup_learn(24-second.num_timesteps, Credit(), reset_num_timesteps=False)
            self.assertEqual(meta['steps'], 8)
            for _ in range(2): update(second)
            for name, value in second.policy.state_dict().items():
                torch.testing.assert_close(value, state[name], rtol=0, atol=0)
            for key, slots in optimizer['state'].items():
                for name, value in slots.items():
                    actual = second.policy.optimizer.state_dict()['state'][key][name]
                    if isinstance(value, torch.Tensor): torch.testing.assert_close(value, actual, rtol=0, atol=0)
                    else: self.assertEqual(value, actual)
            np.testing.assert_array_equal(first._last_obs, second._last_obs)
            np.testing.assert_array_equal(first.env.returns, env.returns)
            np.testing.assert_array_equal(first.env.ret_rms.var, env.ret_rms.var)
            self.assertEqual(first.env.venv._seeds, env.venv._seeds)
            a = first.env.venv.envs[0]; b = env.venv.envs[0]
            np.testing.assert_array_equal(a.state, b.state)
            self.assertEqual(a.ctrl.pending, b.ctrl.pending)
            self.assertEqual(a.ctrl.packet, b.ctrl.packet)
            self.assertEqual(first._n_updates, second._n_updates)

    def test_partial_save_does_not_replace_latest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); model = model_for_test(); update(model)
            save(model, root, 'test')
            (root/'step-000000016.partial-interrupted').mkdir()
            m, _, _ = load(root, 'test')
            self.assertEqual(m.num_timesteps, 8)

    def test_corruption_and_different_source_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); model = model_for_test(); update(model)
            path = save(model, root, 'test')
            with self.assertRaisesRegex(ValueError, 'signature'): load(root, 'different')
            with (path/'state.pkl').open('ab') as f: f.write(b'changed')
            with self.assertRaisesRegex(ValueError, 'checksum'): load(root, 'test')

    def test_new_forecast_preserves_zero_horizon_and_input_arrays(self):
        z = np.array([.1, .02, .01, .03]); ks = np.array([.001, .002, -.002]); g = np.array([1., 2., 3., 4.])
        old = z.copy()
        state, actuator, preview = forecast_state(z, .01, 20., ks, g, 0.)
        np.testing.assert_array_equal(state, z); np.testing.assert_array_equal(z, old)
        np.testing.assert_array_equal(preview, ks); self.assertEqual(actuator, .01)

    def test_lqr_baseline_physically_identical_after_forecast_fix(self):
        case = (20, 'dlc220', 1, 'nominal', 1826000999)
        old = OldEnv(source='lqr', case=case, scenario='nominal')
        new = Env(source='lqr', case=case, scenario='nominal')
        old.reset(); new.reset()
        for _ in range(100):
            _, r, _, _, a = old.step_residual(.04)
            _, s, _, _, b = new.step_residual(.04)
            self.assertEqual(a['command'], b['command']); self.assertEqual(r, s)
            np.testing.assert_array_equal(old.state, new.state)

    def test_timestamp_not_refreshed_and_stale_packet_no_authority(self):
        c = Controller(); c.previews = np.zeros(3); c.packet = (1, 0., .04)
        raw = np.zeros(20, np.float32)
        c.prepare_query(raw, np.zeros(4), 0., 20., c.previews, np.zeros(4))
        self.assertEqual(c.packet, (1, 0., .04))
        command, why = c.choose(.05, .01, np.zeros(4), 0., 20., 0., np.zeros(4))
        self.assertEqual(command, .01); self.assertEqual(c.weight, 0.); self.assertEqual(why, 'age')

    def test_forecast_uses_only_declared_causal_inputs(self):
        case = (20, 'dlc220', 1, 'nominal', 1826000999)
        e = Env(source='ppo', case=case, scenario='nominal'); e.reset()
        args = (e.raw.copy(), e.estimate.copy(), e.state[5], e.measured_speed, e.ctrl.previews.copy(), e.gain.copy())
        before, _ = e.ctrl.prepare_query(*args)
        e.service = 1.; e.mu = .1; e.stiffness = .2; e.noise[:] = 500.
        after, _ = e.ctrl.prepare_query(*args)
        np.testing.assert_array_equal(before, after)

    def test_exploration_initialization_preserves_critic_and_argmax(self):
        from train12 import initialize
        first, a = initialize(0, 'continued'); second, b = initialize(0, 'explore')
        for name, value in first.policy.state_dict().items():
            expected = value*.25 if name.startswith('action_net.') else value
            torch.testing.assert_close(second.policy.state_dict()[name], expected, rtol=0, atol=0)
        x = torch.randn(200, 20); x[:, [16, 17]] = 0
        with torch.no_grad():
            p = first.policy.get_distribution(x); q = second.policy.get_distribution(x)
            torch.testing.assert_close(p.distribution.logits.argmax(1), q.distribution.logits.argmax(1), rtol=0, atol=0)
            self.assertGreater(q.entropy().mean(), p.entropy().mean())
        self.assertTrue(all(param not in second.policy.optimizer.state for param in second.policy.action_net.parameters()))
        self.assertEqual(a.ret_rms.var, b.ret_rms.var)
        a.close(); b.close()

    def test_all_fixed_candidate_outputs_still_bounded(self):
        e = Env(source='ppo', case=(20, 'dlc220', 1, 'nominal', 1826000999), scenario='nominal')
        e.reset()
        for res in [-.08, -.04, 0., .04, .08]*20:
            _, _, _, _, row = e.step_residual(res)
            self.assertLessEqual(abs(row['command']), .5)
            self.assertLessEqual(abs(row['steering_rate']), .3500001)
            if row['weight']:
                self.assertLess(row['packet_age_s'], .05)


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main()
