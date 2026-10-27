import boot5
import unittest
import numpy as np
import torch
from history5 import Bridge,HistoryEnv
from causal_student import load_causal


class Contracts(unittest.TestCase):
    def test_legacy_logits_preserved_for_arbitrary_history(self):
        torch.set_num_threads(1);rng=np.random.default_rng(5731)
        for pair in range(3):
            for kind in ('student','ppo'):
                seed=(701,802,903)[pair]
                folder=boot5.ROOT/(f'docs/research/causal-interface-2026-10-26/models/{seed}' if kind=='student' else f'docs/research/reviewer-aligned-v3/export/{seed}')
                original=load_causal(folder);bridge=Bridge(kind,pair)
                x=rng.normal(size=(512,20)).astype(np.float32)*original.std.numpy()+original.mean.numpy();x[:,[14,15,16,17,19]]=0.
                with torch.no_grad():expected=original(torch.from_numpy(x)).numpy()
                x[:,14]=rng.uniform(-1,1,len(x))
                with torch.no_grad():actual=bridge(torch.from_numpy(x)).numpy()
                np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-6)
                np.testing.assert_array_equal(actual.argmax(1),expected.argmax(1))
    def test_history_is_actual_past_filter_and_future_fields_zero(self):
        e=HistoryEnv(case=(20,'dlc220',1,'nominal',1416000901));e.reset();e.ctrl.filtered=.04;e._history()
        self.assertEqual(float(e.obs[14]),.5)
        e.ctrl.pending=(10.,(99,0.,-.08));e._history();self.assertEqual(float(e.obs[14]),.5)
        self.assertTrue(np.all(e.obs[[15,16,17,19]]==0))
    def test_filter_alias_is_disambiguated_and_ablation_masks_it(self):
        a=HistoryEnv(case=(20,'dlc220',1,'nominal',1416000902));b=HistoryEnv(case=(20,'dlc220',1,'nominal',1416000902));a.reset();b.reset()
        a.ctrl.filtered=-.06;b.ctrl.filtered=.06;a._history();b._history()
        self.assertNotEqual(a.obs[14],b.obs[14]);np.testing.assert_array_equal(np.delete(a.obs,14),np.delete(b.obs,14))
        a.expose_history=False;a._history();self.assertEqual(a.obs[14],0.)
    def test_realistic_delivery_and_training_namespace(self):
        a=HistoryEnv(seed=4701);b=HistoryEnv(seed=4701,history=False);x,ia=a.reset();y,ib=b.reset()
        self.assertEqual(ia,ib);self.assertGreaterEqual(ia['noise_id'],1406000000);self.assertGreaterEqual(a.service,.01)
        np.testing.assert_array_equal(x,y)
        for e in (a,b):
            r=e.step(4)[4];self.assertEqual(r['packet_seq'],-1);self.assertEqual(r['command'],r['baseline'])
    def test_stale_response_cannot_preserve_history_or_authority(self):
        e=HistoryEnv(case=(20,'dlc220',1,'delay100',1416000903));e.reset()
        for _ in range(30):
            obs,_,_,_,row=e.step(4);self.assertEqual(row['command'],row['baseline']);self.assertEqual(obs[14],0.)


if __name__=='__main__':unittest.main()
