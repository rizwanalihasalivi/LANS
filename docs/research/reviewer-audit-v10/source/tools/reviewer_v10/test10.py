import boot10
import unittest
from unittest.mock import patch
import numpy as np
from controller10 import AuditedController
from features9 import QueryController
from env9 import Env as OldEnv
from env10 import Env

class AuditContracts(unittest.TestCase):
    def setup_controller(self,kind=AuditedController):
        c=kind();c.previews=np.zeros(3);c.good=3;c.filtered=.01;c.last_qualified_time=.009;c.last_qualified_sequence=1;c.last_sequence=1;c.packet=(2,0.,.04)
        return c
    def choose(self,c,**kw):
        args=dict(t=.01,baseline=0.,estimate=np.zeros(4),actuator=0.,speed=20.,curvature=0.,gain=np.zeros(4));args.update(kw)
        with patch('recovery8.expiry_cost',side_effect=lambda *a:1. if a[-2]==0 else .9):return c.choose(*args.values())
    def test_old_nonfinite_identifier_can_retain_authority(self):
        c=self.setup_controller(QueryController);c.packet=(float('nan'),0.,.04);self.choose(c);self.assertGreater(c.weight,0.)
    def test_bad_identifiers_rejected(self):
        for seq in (float('nan'),float('inf'),2.,True,0,-1,'2'):
            c=self.setup_controller();c.packet=(seq,0.,.04);_,reason=self.choose(c);self.assertEqual(reason,'packet_identifier');self.assertEqual(c.weight,0.)
    def test_duplicate_identity_mutation_rejected(self):
        for stamp,res in ((.001,.04),(0.,-.04)):
            c=self.setup_controller();self.choose(c);c.packet=(2,stamp,res);_,reason=self.choose(c);self.assertEqual(reason,'packet_identity');self.assertEqual(c.weight,0.)
    def test_unchanged_packet_may_be_held(self):
        c=self.setup_controller();self.choose(c);_,reason=self.choose(c,t=.02);self.assertEqual(reason,'accepted')
    def test_invalid_service_and_timestamp(self):
        for t,service in ((0.,float('nan')),(0.,float('inf')),(0.,-.01),(-.01,.01),(float('nan'),.01)):
            with self.assertRaises(ValueError):AuditedController().submit(t,0.,service)
    def test_old_nan_service_creates_undeliverable_pending(self):
        c=QueryController();self.assertTrue(c.submit(0.,.04,float('nan')));c.deliver(1.);self.assertIsNotNone(c.pending)
    def test_out_of_bound_request_not_silently_clipped(self):
        with self.assertRaises(ValueError):AuditedController().submit(0.,.081,.01)
    def test_invalid_baseline_is_explicit_control_fault(self):
        for x in (float('nan'),float('inf'),.51):
            with self.assertRaises(ValueError):self.choose(self.setup_controller(),baseline=x)
    def test_numerical_domains_fail_closed(self):
        for kw in (dict(speed=0.),dict(speed=4.9),dict(actuator=.6)):
            c=self.setup_controller();command,_=self.choose(c,**kw);self.assertEqual(command,0.);self.assertEqual(c.weight,0.)
    def test_malformed_packet_fail_closed(self):
        for packet in ((1,0.),None,(1,'x',.04),(1,-.1,.04)):
            c=self.setup_controller();c.packet=packet;command,_=self.choose(c);self.assertEqual(command,0.);self.assertEqual(c.weight,0.)
    def test_freshness_cutoff_unchanged(self):
        c=self.setup_controller();self.choose(c,t=.05);self.assertEqual(c.weight,0.)
    def test_future_packets_never_assist(self):
        c=self.setup_controller();c.packet=(2,.02,.04);self.choose(c);self.assertEqual(c.weight,0.)
    def test_time_limit_returns_next_observation(self):
        case=(20,'dlc220',1,'nominal',1606000999)
        old=OldEnv(case=case,scenario='nominal',source='causal_history');new=Env(case=case,scenario='nominal',source='ppo_euler');a,_=old.reset();b,_=new.reset();np.testing.assert_array_equal(a,b)
        old.horizon=new.horizon=1
        aa,_,_,done,_=old.step_residual(0.);bb,_,_,end,_=new.step_residual(0.)
        self.assertTrue(done and end);np.testing.assert_array_equal(aa,a);self.assertFalse(np.array_equal(bb,b));self.assertEqual(bb[13],1.)
    def test_valid_nonterminal_behavior_matches_previous(self):
        case=(20,'dlc220',1,'nominal',1606000999);old=OldEnv(case=case,scenario='nominal',source='causal_history');new=Env(case=case,scenario='nominal',source='ppo_euler');old.reset();new.reset()
        for res in ([.04,-.04,0.,.08,-.08]*10):
            a,r,f,d,info=old.step_residual(res);b,s,g,e,check=new.step_residual(res)
            np.testing.assert_array_equal(a,b);self.assertEqual(r,s);np.testing.assert_array_equal(old.state,new.state);self.assertEqual(info['reason'],check['reason'])
    def test_planner_has_no_true_state_or_future_noise_input(self):
        from planner10 import propose
        e=Env(case=(20,'dlc220',1,'nominal',1606000999),scenario='nominal',source='planner');e.reset()
        args=(e.ctrl,e.estimate,e.state[5],e.measured_speed,e.ctrl.previews,e.gain,e.gains,0.)
        a=propose(*args);e.mu=.2;e.stiffness=.2;e.service=1.;e.noise[:]=100.
        self.assertEqual(a,propose(*args));self.assertIsNone(e.ctrl.packet);self.assertEqual(e.ctrl.sequence,0)
    def test_rk_actuator_matches_closed_form(self):
        import math
        from rollout10 import micro_step
        z=(0.,0.,0.,0.,0.);ks=np.zeros(3)
        for j in range(10):z=micro_step(z,.005,20.,ks,j*.001,.001)
        exact=.005*(1-math.exp(-.01/.05));self.assertAlmostEqual(z[4],exact,11)
        self.assertGreater(abs(.01*.005/.05-exact),1e-5)
if __name__=='__main__':unittest.main()
