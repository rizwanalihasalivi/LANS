import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
from bootstrap import RESEARCH
from policy9 import FrozenStudent,logits,PPOAdapter,P
from train9 import create_model,STUDENTS
from env9 import TrainingEnv
from execution_env import ExecutionEnv


class TransferContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def test_exact_transfer_fresh_critic_optimizer_and_serialization(self):
        for pair in range(3):
            student=FrozenStudent(STUDENTS/str(P['student_seeds'][pair]));seed=P['rl_seeds'][pair]
            warm=create_model(TrainingEnv(pair,0,seed),student,seed,'finetune')
            scratch=create_model(TrainingEnv(pair,0,seed),student,seed,'scratch')
            x=torch.from_numpy(np.random.default_rng(seed).normal(0,.2,(4096,20)).astype(np.float32))
            with torch.no_grad():
                np.testing.assert_allclose(logits(warm,x).numpy(),student(x).numpy(),atol=0,rtol=0)
                self.assertFalse(torch.equal(logits(scratch,x),student(x)))
            for a,b in zip(warm.policy.mlp_extractor.value_net.parameters(),scratch.policy.mlp_extractor.value_net.parameters()):self.assertTrue(torch.equal(a,b))
            self.assertTrue(torch.equal(warm.policy.value_net.weight,scratch.policy.value_net.weight))
            self.assertEqual(len(warm.policy.optimizer.state),0);self.assertEqual(len(scratch.policy.optimizer.state),0)
            with tempfile.TemporaryDirectory() as tmp:
                warm.save(Path(tmp)/'policy');loaded=PPO.load(Path(tmp)/'policy',device='cpu')
                with torch.no_grad():self.assertTrue(torch.equal(logits(warm,x),logits(loaded,x)))
                adapter=PPOAdapter(loaded)
                for obs in x.numpy()[::101]:np.testing.assert_array_equal(adapter.predict(obs)[0],student.predict(obs)[0])

    def test_action_map_reward_and_full_horizon_match_original(self):
        env=TrainingEnv(0,0,1701);env.reset();original=copy.deepcopy(env)
        for step in range(100):
            action=step%5
            a=env.step(action);b=ExecutionEnv.step(original,np.array([P['candidates_rad'][action]/.08],np.float32))
            np.testing.assert_array_equal(a[0],b[0]);np.testing.assert_array_equal(env.state,original.state)
            self.assertEqual(a[1],b[1]);self.assertEqual(a[2],b[2])
            info=a[4];self.assertAlmostEqual(a[1],sum(info[k] for k in ('reward_tracking','reward_effort','reward_change','reward_survival','reward_relative')),places=12)
            if env.service_ticks==10:self.assertEqual(info['baseline_rad'],info['command_rad'])
        for bad in (-1,5,1.5,np.nan,[1,2]):
            with self.assertRaises(ValueError):env.step(bad)
        env.steps=799;self.assertFalse(env.step(2)[3])
        env.steps=env.horizon-1;self.assertTrue(env.step(2)[3])

    def test_split_noise_disjoint_and_paired_resets(self):
        sets=[]
        for base in (320000000,420000000,520000000,*P['splits'].values()):
            ids={base+i*10000+v*100+j*10+k for i in range(3) for v in (15,20,25) for j in range(2) for k in range(6)}
            for old in sets:self.assertFalse(ids&old)
            sets.append(ids)
        a,b=TrainingEnv(0,0,1701),TrainingEnv(0,0,1701)
        for episode in range(30):
            x,ia=a.reset();y,ib=b.reset();np.testing.assert_array_equal(x,y);self.assertEqual(ia,ib)
            self.assertFalse(any(a.noise_id in old for old in sets))


if __name__=='__main__':unittest.main()
