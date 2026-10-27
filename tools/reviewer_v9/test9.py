import boot9
import json
import tempfile
import unittest
import numpy as np
import torch
from model9 import Bridge
from features9 import QueryController,make_observation,NEW
from env9 import Env

class Contracts(unittest.TestCase):
    def test_initial_ppo_logits_preserved_for_new_history(self):
        rng=np.random.default_rng(931);x=rng.normal(0,.2,(512,20)).astype(np.float32);x[:,[14,15,16,17,19]]=0
        for pair,seed in enumerate((701,802,903)):
            with np.load(boot9.ROOT/f'docs/research/reviewer-history-v5/portable-actor/model-{seed}.npz') as z:
                old=np.tanh(np.tanh(((x-z['mean'])/z['std'])@z['w0']+z['b0'])@z['w1']+z['b1'])@z['w2']+z['b2']
            bridge=Bridge('ppo',pair);xx=x.copy();xx[:,list(NEW)]=rng.uniform(-1,1,(len(x),3))
            with torch.no_grad():actual=bridge(torch.from_numpy(xx)).numpy()
            np.testing.assert_array_equal(old.argmax(1),actual.argmax(1));np.testing.assert_allclose(old,actual,rtol=0,atol=1e-4)
    def test_new_slots_are_past_state_and_other_future_slots_zero(self):
        c=QueryController();c.previews=np.zeros(3);c.filtered=.04;c.last_qualified_time=.08
        x=make_observation(np.zeros(6),np.zeros(4),20.,c.previews,c,.1)
        self.assertEqual(x[14],.5);self.assertEqual(x[15],.25);self.assertAlmostEqual(x[19],.4,6);self.assertTrue(np.all(x[[16,17]]==0))
    def test_future_oracle_fields_rejected(self):
        c=QueryController();x=np.zeros(20,np.float32);x[16]=1
        with self.assertRaises(ValueError):c.prepare_query(x,np.zeros(4),0.,20.,np.zeros(3),np.zeros(4))
    def test_masked_training_control(self):
        e=Env(source='legacy_history',case=(20,'dlc220',1,'nominal',1516000999),scenario='nominal',mask_history=True);x,_=e.reset()
        self.assertTrue(np.all(x[list(NEW)]==0));self.assertEqual(e.raw[15],.25);self.assertEqual(e.raw[19],1.)
    def test_runtime_query_equals_training_query(self):
        from runtime9 import controller,observation
        e=Env(source='causal_history',case=(20,'dlc220',1,'nominal',1516000999),scenario='nominal');x,_=e.reset()
        c=controller('history_comp');c.previews=e.ctrl.previews.copy()
        raw=observation(e.state,e.estimate,e.measured_speed,c.previews,c,0.)
        actual,meta=c.prepare_query(raw,e.estimate,e.state[5],e.measured_speed,c.previews,e.gain)
        np.testing.assert_array_equal(x,actual);self.assertEqual(meta,e.query_meta)
    def test_old_abi_rejected(self):
        from runtime9 import episode
        with tempfile.TemporaryDirectory() as d:
            folder=boot9.Path(d);(folder/'manifest.json').write_text(json.dumps(dict(profile='latency_compensated_query_v7')))
            with self.assertRaises(ValueError):episode(None,'nominal',701,'history_comp',1.,folder,folder,budget_guard=True)
    def test_configured_service_is_not_a_query_input(self):
        e=Env(source='causal_history',case=(20,'dlc220',1,'nominal',1516000999),scenario='nominal');e.reset()
        args=(e.raw,e.estimate,e.state[5],e.measured_speed,e.ctrl.previews,e.gain)
        a,m=e.ctrl.prepare_query(*args);e.service=1.;b,n=e.ctrl.prepare_query(*args)
        np.testing.assert_array_equal(a,b);self.assertEqual(m,n)
    def test_future_qualification_history_rejected(self):
        c=QueryController();c.last_qualified_time=.1
        with self.assertRaises(ValueError):make_observation(np.zeros(6),np.zeros(4),20.,np.zeros(3),c,.05)

if __name__=='__main__':torch.set_num_threads(1);unittest.main()
