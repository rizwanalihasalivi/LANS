import copy,tempfile,unittest
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
from bootstrap import RESEARCH
from policy10 import P,FrozenStudent,logits,PPOAdapter
from env10 import TrainingEnv
from train10 import create_model,STUDENTS
from credit10 import numeric_worker,single_request_cost,proposal_credit
from execution import matched_lqr
from core import GAINS,path_values
from plant import advance
from anchor10 import AnchoredPPO


class ZeroNoise:
    def normal(self,loc,scale):return np.zeros_like(scale)


def original_request_cost(env,proposal):
    clone=copy.deepcopy(env);clone.sensor.rng=ZeroNoise();cost=0.;applied=0;sequence=clone.execution.sequence+1
    for j in range(20):
        speed=max(5.,float(clone.obs[4])*25);base,gain=matched_lqr(clone.estimate,speed,clone.kappa)
        command,info=clone.execution.step((env.steps+j)*.01,proposal if j==0 else 0.,clone.service_ticks,base,clone.estimate,clone.state[5],speed,clone.kappa,gain)
        applied+=info['packet_sequence']==sequence and info['gate_weight']>0 and command!=base
        clone.state=advance(clone.state,command,clone.speed,clone.mu,clone.stiffness)
        y,h,_=path_values(clone.state[0],clone.path);ey=clone.state[1]-y;cost+=ey*ey
        if abs(ey)>2.5 or abs(clone.state[2]-h)>.6 or not np.isfinite(clone.state).all():return cost+(19-j)*6.25,applied
        clone.obs,clone.estimate,clone.kappa=clone.sensor.measure(clone.state,clone.speed,clone.path)
    return cost,applied


class PilotContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def test_exact_transfer_all_arms_fresh_critic_and_save_load(self):
        real=torch.from_numpy(np.load(RESEARCH.parent/'results/revision8-student/data/dev.npz')['x'][::6])
        for pair in range(3):
            student=FrozenStudent(STUDENTS/str(P['student_seeds'][pair]));models=[]
            for arm in P['arms']:
                model=create_model(TrainingEnv(pair,0,P['rl_seeds'][pair]),student,P['rl_seeds'][pair],arm);models.append(model)
                with torch.no_grad():np.testing.assert_array_equal(logits(model,real).numpy(),student(real).numpy())
                self.assertFalse(model.policy.optimizer.state)
                if model.anchor_coef:self.assertTrue(all(not p.requires_grad for p in model.anchor_ref.parameters()))
            for model in models[1:]:
                for name,value in models[0].policy.state_dict().items():self.assertTrue(torch.equal(value,model.policy.state_dict()[name]))
            with tempfile.TemporaryDirectory() as tmp:
                models[-1].save(Path(tmp)/'policy');loaded=AnchoredPPO.load(Path(tmp)/'policy',device='cpu')
                self.assertEqual(loaded.anchor_coef,1.);self.assertTrue(loaded.mask_busy)
                with torch.no_grad():np.testing.assert_array_equal(logits(loaded,real).numpy(),student(real).numpy())

    def test_counterfactual_matches_original_objects_without_mutation(self):
        found=set();checks=0
        for seed in range(2701,2731):
            env=TrainingEnv(0,0,seed,credit=True);env.reset()
            if (env.service_ticks,env.delay) in found:continue
            found.add((env.service_ticks,env.delay))
            for tick in range(45):
                worker=numeric_worker(env.execution);before=copy.deepcopy(env)
                if tick in (0,8,24,40) and (env.execution.pending is None or env.execution.pending[0]<=env.steps*.01+1e-9):
                    for proposal in (-.08,.08):
                        args=(env.state,env.estimate,env.sensor.cov,env.sensor.queue[-1],worker,env.steps,proposal,env.service_ticks,float(env.speed),env.path,env.mu,env.stiffness,env.delay,float(env.noise),max(5.,float(env.obs[4])*25),env.kappa,np.array([GAINS[v] for v in (15,20,25)]))
                        actual=single_request_cost(*args);expected=original_request_cost(env,proposal)
                        self.assertAlmostEqual(actual[0],expected[0],places=11);self.assertEqual(actual[1],expected[1]);checks+=1
                    np.testing.assert_array_equal(env.state,before.state);np.testing.assert_array_equal(worker,numeric_worker(env.execution))
                obs=env.observation();eligible=bool(obs[17]<.5 or obs[15]<=1e-8)
                _,reward,failed,_,info=env.step(1)
                self.assertEqual(eligible,info['decision_eligible']);self.assertEqual(eligible,info['submitted'])
                self.assertAlmostEqual(reward,info['credit_bonus']-10.*failed)
                if not eligible:self.assertEqual(info['credit_bonus'],0.)
                if env.service_ticks==10:self.assertEqual(reward,0.);self.assertEqual(info['command_rad'],info['baseline_rad'])
            if len(found)==4:break
        self.assertGreaterEqual(checks,16);self.assertTrue(any(x[0]==10 for x in found));self.assertTrue(any(x[1]==1 for x in found))

    def test_reward_changes_no_actual_trajectory_and_zero_proposal_no_credit(self):
        env=TrainingEnv(0,0,2701,credit=True);env.reset();original=copy.deepcopy(env);original.credit=False
        for tick in range(100):
            a=env.step(tick%5);b=original.step(tick%5)
            np.testing.assert_array_equal(a[0],b[0]);np.testing.assert_array_equal(env.state,original.state)
            if tick%5==2:self.assertEqual(a[4]['credit_bonus'],0.)

    def test_anchor_gradient_mask_and_zero_coefficient_stock_equivalence(self):
        student=FrozenStudent(STUDENTS/'701');seed=P['rl_seeds'][0]
        env=TrainingEnv(0,0,seed);env.reset();model=create_model(env,student,seed,'combined')
        x=torch.from_numpy(np.random.default_rng(99).normal(0,.05,(20,20)).astype(np.float32))
        x[:,17]=1;x[:,15]=.1;self.assertEqual(model.decision_mask(x).sum(),0)
        x[0,15]=0;self.assertEqual(model.decision_mask(x).sum(),1)
        before={k:v.clone() for k,v in model.anchor_ref.state_dict().items()}
        with torch.no_grad():model.policy.action_net.bias[0]+=.1
        loss=model.anchor_loss(x);self.assertGreater(loss.item(),0.);loss.backward()
        self.assertIsNotNone(model.policy.action_net.weight.grad)
        self.assertTrue(all(p.grad is None for p in model.anchor_ref.parameters()))
        for k,v in before.items():self.assertTrue(torch.equal(v,model.anchor_ref.state_dict()[k]))
        # Same data/order/initial parameters: the zero-anchor, unmasked learner
        # must reproduce stock SB3 PPO updates (not just inference).
        ours=create_model(TrainingEnv(0,0,seed),student,seed,'plain');ours.n_steps=20;ours.batch_size=20;ours.n_epochs=2
        from stable_baselines3.common.buffers import RolloutBuffer
        ours.rollout_buffer=RolloutBuffer(20,ours.observation_space,ours.action_space,device='cpu',gamma=.99,gae_lambda=.95,n_envs=1)
        stock=PPO('MlpPolicy',TrainingEnv(0,0,seed),seed=seed,n_steps=20,batch_size=20,n_epochs=2,learning_rate=.0001,clip_range=.1,target_kl=.01,policy_kwargs=ours.policy_kwargs,device='cpu')
        stock.policy.load_state_dict(ours.policy.state_dict())
        np.random.seed(seed);torch.manual_seed(seed);ours.learn(40)
        np.random.seed(seed);torch.manual_seed(seed);stock.learn(40)
        for k,v in ours.policy.state_dict().items():np.testing.assert_allclose(v.detach().numpy(),stock.policy.state_dict()[k].detach().numpy(),rtol=1e-5,atol=1e-6)


if __name__=='__main__':unittest.main()
