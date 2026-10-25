"""Regression checks for evidence integrity and unambiguous recorded traces."""
import csv
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.controller_review.report import summarize
from visualize_results import signals, compute_rmse, load_lqr_results, generate_reference_path


class EvidenceContracts(unittest.TestCase):
    def write(self, root, rows):
        path=Path(root)/'episodes.csv'
        with path.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
        return path

    def fixtures(self):
        # Same failed horizon for each candidate, not a misleading survivor-only score.
        return [dict(seed=s,method=m,survived='False',steps=2,scheduled_steps=4,rmse=.5,
                     penalized_rmse=np.sqrt((2*.25+2*6.25)/4))
                for s in (1,2) for m in ('lqr','policy')]

    def test_raw_failure_tails_and_seed_statistics(self):
        with tempfile.TemporaryDirectory() as root:
            table,_=summarize(self.write(root,self.fixtures()))
        self.assertEqual(len(table),2)
        self.assertEqual(table[0]['survived'],0)
        self.assertEqual(table[0]['seed_mean_sd_m'],0.)
        self.assertAlmostEqual(table[0]['mean_episode_rmse_m'],np.sqrt(3.25))

    def test_missing_duplicates_and_wrong_penalties_rejected(self):
        rows=self.fixtures()
        variants=[rows[:-1],rows+[rows[0]],[dict(r,penalized_rmse=.5) for r in rows]]
        with tempfile.TemporaryDirectory() as root:
            for bad in variants:
                with self.assertRaises(ValueError):summarize(self.write(root,bad))

    def test_one_seed_has_no_invented_sd(self):
        with tempfile.TemporaryDirectory() as root:
            table,_=summarize(self.write(root,self.fixtures()[:2]))
        self.assertIsNone(table[0]['seed_mean_sd_m'])

    def test_plot_error_state_is_not_absolute_position(self):
        data=dict(t=[0.,1.],y_ref=[3.,3.],x=np.array([[.1,0,0,0],[.1,0,0,0]]),u=[0.,0.])
        with self.assertRaises(ValueError):signals(data)
        _,actual,_,_,score=signals(data,'error_ey_eydot_epsi_epsidot')
        np.testing.assert_allclose(actual,[3.1,3.1]);self.assertAlmostEqual(score,.1)
        with self.assertRaises(ValueError):compute_rmse([0],[0,1])
        self.assertEqual(generate_reference_path(np.arange(3)).shape,(3,))
        with self.assertRaises(FileNotFoundError):load_lqr_results('/tmp/absent-lans-results.npz')

    def test_retired_reporting_does_not_generate_results(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ('ablation_study_real.py','thesis_summary_table.py','lans_highway.py','proof.py'):
                result=subprocess.run([sys.executable,str(ROOT/name)],cwd=root,capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('retired',result.stderr.lower())
            self.assertEqual(list(Path(root).iterdir()),[])

    def test_auxiliary_retirement_is_explicit(self):
        for name,cls in [('envs.bicycle_env','BicycleEnv'),('envs.lqr_env','LQREnv')]:
            with self.assertRaisesRegex(RuntimeError,'retired'):
                getattr(importlib.import_module(name),cls)()

    def test_incomplete_output_preserves_original_without_guessing(self):
        marker=json.loads((ROOT/'jitter_test_results.json').read_text())
        self.assertFalse(marker['usable_as_experimental_evidence'])
        raw=(ROOT/marker['original_bytes']).read_text()
        with self.assertRaises(json.JSONDecodeError):json.loads(raw)


if __name__ == '__main__':unittest.main()
