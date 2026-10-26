"""Packet age must reflect a real policy query, including between-query delivery."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'revision8'))
import bootstrap
import unittest
import numpy as np
from kernels import initial_executor,execution_step
from execution import Execution
from comparison import configure_lqr
from core import GAINS


class SubmissionContracts(unittest.TestCase):
    def setUp(self):
        configure_lqr()
        self.estimate=np.array([.03,0.,.005,0.])
        self.gain=GAINS[25]

    def test_default_preserves_every_available_tick(self):
        implicit=initial_executor();explicit=initial_executor()
        for tick in range(30):
            args=(tick*.01,.08,2,.01,self.estimate,0.,25.,.001,self.gain,False)
            a=execution_step(implicit,*args)
            b=execution_step(explicit,*args,True)
            self.assertEqual(a,b)
            np.testing.assert_array_equal(implicit,explicit)

    def test_query_cadence_preserves_timestamp_and_matches_original_object(self):
        for service in [0,2,10]:
            compiled=initial_executor();original=Execution();submissions=0
            for tick in range(30):
                submit=tick%5==0
                a=execution_step(compiled,tick*.01,.08,service,.01,self.estimate,0.,25.,.001,self.gain,False,submit)
                command,info=original.step(tick*.01,.08,service,.01,self.estimate,0.,25.,.001,self.gain,submit_request=submit)
                self.assertEqual(a[0],command);self.assertEqual(a[1],info['gate_weight'])
                self.assertEqual(a[3],info['submitted']);submissions+=a[3]
                if compiled[3]>=0:
                    self.assertEqual(compiled[4],info['observation_timestamp_s'])
                    self.assertAlmostEqual(tick*.01-compiled[4],info['action_age_s'])
                if tick==4 and service in [0,2]:
                    self.assertEqual(compiled[4],0.)
                    self.assertAlmostEqual(info['action_age_s'],.04)
                if service==10:
                    self.assertEqual(a[0],.01);self.assertEqual(a[1],0.)
            self.assertEqual(submissions,3 if service==10 else 6)

    def test_pending_packet_delivers_without_a_new_query(self):
        worker=initial_executor()
        for tick in range(4):
            _,_,_,submitted=execution_step(worker,tick*.01,.08,2,.01,self.estimate,0.,25.,.001,self.gain,False,tick==0)
            self.assertEqual(submitted,tick==0)
        self.assertEqual(worker[3],1.)
        self.assertEqual(worker[4],0.)
        self.assertEqual(worker[7],-1.)
        self.assertEqual(worker[10],1.)

if __name__=='__main__':unittest.main()
