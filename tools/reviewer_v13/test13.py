import boot13
import math
import unittest
import numpy as np
from scipy.integrate import solve_ivp
from control13 import actuator_next,project,SmoothController
from env13 import Env
from experiment import FollowupEnv
from models13 import original,export,logits
import torch


class Contracts(unittest.TestCase):
    def test_actuator_matches_independent_integrator(self):
        rng=np.random.default_rng(13031)
        for delta,difference in zip(rng.uniform(-.4,.4,60),rng.uniform(-.04,.04,60)):
            command=delta+difference
            sol=solve_ivp(lambda t,z:[np.clip((command-z[0])/.05,-.35,.35)],(0,.01),[delta],method='DOP853',rtol=1e-12,atol=1e-13,max_step=.0001)
            self.assertAlmostEqual(actuator_next(delta,command),sol.y[0,-1],9)

    def test_projection_local_budget_and_segment(self):
        rng=np.random.default_rng(13032)
        for _ in range(1000):
            delta,base,desired=rng.uniform(-.5,.5,3)
            command,scale,b,c=project(delta,base,desired)
            self.assertTrue(0<=scale<=1)
            self.assertAlmostEqual(command,base+scale*(desired-base),12)
            self.assertLessEqual(c,min(.35,1.02*b)+1e-10)

    def test_project_is_mirror_symmetric(self):
        a=project(.01,.015,-.01);b=project(-.01,-.015,.01)
        self.assertAlmostEqual(a[0],-b[0],13)
        np.testing.assert_allclose(a[1:],b[1:],rtol=0,atol=1e-12)

    def test_stale_invalid_and_future_revoke_immediately(self):
        for packet,t in [((1,0.,.08),.05),((1,.02,.08),.01),((True,0.,.04),.01),((1,0.,.09),.01),((1,0.,float('nan')),.01),((1,'bad',.04),.01),((1,0.,True),.01)]:
            c=SmoothController();c.packet=packet;c.filtered=.05;c.weight=.5
            command,_=c.choose(t,.01,np.zeros(4),0.,20.,0.,np.zeros(4))
            self.assertEqual(command,.01);self.assertEqual(c.weight,0.);self.assertEqual(c.filtered,0.)

    def test_identity_mutation_rejected(self):
        c=SmoothController();c.packet=(1,0.,.04)
        c.choose(.01,0.,np.zeros(4),0.,20.,0.,np.zeros(4))
        c.packet=(1,0.,-.04)
        self.assertEqual(c.choose(.02,.02,np.zeros(4),0.,20.,0.,np.zeros(4)),(.02,'identity'))

    def test_rejected_future_id_does_not_poison_recovery(self):
        c=SmoothController();c.packet=(900,100.,.04)
        self.assertEqual(c.choose(.01,0.,np.zeros(4),0.,20.,0.,np.zeros(4)),(0.,'age'))
        c.packet=(1,.01,.04)
        _,reason=c.choose(.01,0.,np.zeros(4),0.,20.,0.,np.zeros(4))
        self.assertIn(reason,('rate_projected','smoothed'))

    def test_queue_original_time_and_one_inflight(self):
        c=SmoothController();self.assertTrue(c.submit(0.,.04,.02));self.assertFalse(c.submit(.01,-.04,0.))
        c.deliver(.019);self.assertIsNone(c.packet)
        c.deliver(.02);self.assertEqual(c.packet,(1,0.,.04))

    def test_historical_baseline_and_original_plant_unchanged(self):
        for oldprofile,newprofile in [('lqr','lqr'),('age_original','original'),('age_filtered','oldfiltered')]:
            case=(20,'dlc220',1,'nominal',1926000999)
            a=FollowupEnv(oldprofile,case);b=Env(profile=newprofile,case=case)
            a.reset();b.reset()
            for res in [.04,-.08,.08,0.]*25:
                aa,_,_,_,x=a.step_residual(res);bb,_,_,_,y=b.step_residual(res)
                self.assertEqual(x['command'],y['command']);np.testing.assert_array_equal(a.state,b.state)
                bb=bb.copy();bb[14]=0.;np.testing.assert_array_equal(aa,bb)

    def test_reward_uses_actual_actuator_rate_and_terminal_next_obs(self):
        e=Env(case=(20,'dlc220',1,'nominal',1926000999));x,_=e.reset();e.horizon=1
        y,r,failed,done,row=e.step_residual(.08)
        wanted=-(row['lateral_error']/.5)**2-.2*(row['heading_error']/.1)**2-.2*(row['steering_rate']/.35)**2-.005*(row['command']/.5)**2-10*failed
        self.assertEqual(r,wanted);self.assertTrue(done);self.assertFalse(np.array_equal(x,y))

    def test_bridged_actors_ignore_new_history_and_preserve_old_logits(self):
        x=np.random.default_rng(13033).normal(size=(100,20)).astype(np.float32);x[:,[14,15,16,17,19]]=0
        for source in ('ppo','student'):
            m=original(0,source);a=export(m,student=source=='student',bridge=False);b=export(m,student=source=='student')
            old=logits(a,x);x[:,14]=.3
            np.testing.assert_allclose(old,logits(b,x),rtol=0,atol=1e-6);x[:,14]=0

    def test_new_history_contains_only_available_filter(self):
        e=Env(case=(20,'dlc220',1,'nominal',1926000999));e.reset()
        x,_,_,_,_=e.step_residual(.08)
        self.assertAlmostEqual(x[14],e.ctrl.filtered/.08,7)
        self.assertTrue(np.all(x[[15,16,17,19]]==0))

    def test_train_bridge_preserves_actor_and_critic(self):
        from train13 import bridge
        x=np.random.default_rng(13034).normal(size=(100,20)).astype(np.float32);x[:,[14,15,16,17,19]]=0
        m=original(0,'ppo')
        with torch.no_grad():
            old=m.policy.get_distribution(torch.from_numpy(x)).distribution.logits.clone()
            value=m.policy.predict_values(torch.from_numpy(x)).clone()
            bridge(m);x[:,14]=.7
            np.testing.assert_allclose(old,m.policy.get_distribution(torch.from_numpy(x)).distribution.logits,rtol=0,atol=1e-6)
            np.testing.assert_allclose(value,m.policy.predict_values(torch.from_numpy(x)),rtol=0,atol=1e-6)

    def test_exact_training_resume_on_new_environment(self):
        import tempfile
        from pathlib import Path
        from train13 import initialize
        from train12 import Credit
        from checkpoint12 import save,load
        from stable_baselines3.common.logger import configure
        m,e=initialize(0,'physical');m.set_logger(configure(None,[]));c=Credit()
        m._setup_learn(2000,c,reset_num_timesteps=True)
        def advance(m,e,c):
            self.assertTrue(m.collect_rollouts(e,c,m.rollout_buffer,m.n_steps))
            m._update_current_progress_remaining(m.num_timesteps,2000);m.train()
        advance(m,e,c)
        with tempfile.TemporaryDirectory() as d:
            save(m,Path(d),'v13-smoke');advance(m,e,c)
            expected={k:v.detach().clone() for k,v in m.policy.state_dict().items()};obs=m._last_obs.copy();returns=e.returns.copy()
            resumed,ev,_=load(Path(d),'v13-smoke');resumed.set_logger(configure(None,[]));c2=Credit()
            resumed._setup_learn(1000,c2,reset_num_timesteps=False);advance(resumed,ev,c2)
            for k,v in resumed.policy.state_dict().items():self.assertTrue(torch.equal(v,expected[k]),k)
            np.testing.assert_array_equal(obs,resumed._last_obs);np.testing.assert_array_equal(returns,ev.returns)
            self.assertEqual(m.audit_counts,resumed.audit_counts)
            for key,slots in m.policy.optimizer.state_dict()['state'].items():
                for name,value in slots.items():
                    other=resumed.policy.optimizer.state_dict()['state'][key][name]
                    if isinstance(value,torch.Tensor):self.assertTrue(torch.equal(value,other))
                    else:self.assertEqual(value,other)
        e.close();ev.close()

    def test_small_complete_evidence_pipeline_and_corruption_rejection(self):
        import tempfile
        import contextlib
        import io
        from pathlib import Path
        from unittest.mock import patch
        import study13,verify13
        from train13 import bridge
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp);(out/'actors').mkdir()
            models={}
            for pair in range(3):
                for source in ('ppo','student','legacy','physical'):
                    m=original(pair,'student' if source=='student' else 'ppo')
                    if source in ('legacy','physical'):bridge(m)
                    models[pair,source]=m
                    np.savez_compressed(out/f'actors/{source}-{pair}.npz',**export(m,student=source=='student',bridge=source in ('ppo','student')))
            def cases(pair):
                for scenario in ('nominal','delay100'):
                    yield (20,'sine120',1,scenario,1990000000+pair),scenario
            make=study13.make_env
            def short(*args):
                e=make(*args);reset=e.reset
                def shorter(**kwargs):
                    result=reset(**kwargs);e.horizon=4;return result
                e.reset=shorter;return e
            with patch.object(study13,'cases',cases),patch.object(verify13,'cases',cases),patch.object(study13,'make_env',short),patch.object(verify13,'make_env',short),patch.object(verify13,'torch_model',lambda out,pair,source:models[pair,source]),patch.dict(study13.P['development'],episodes=72),contextlib.redirect_stdout(io.StringIO()):
                for pair in range(3):study13.main(out,pair)
                verify13.main(out)
                trace=next((out/'pair-0/traces').glob('*.npz'));trace.write_bytes(b'corrupted')
                with self.assertRaises(AssertionError):verify13.main(out)


if __name__=='__main__':torch.set_num_threads(1);unittest.main()
