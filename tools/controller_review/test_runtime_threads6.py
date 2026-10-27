"""Validate the thread policy with deliberately conflicting inherited settings."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]

class ThreadPolicy(unittest.TestCase):
    def test_before_numpy_initialization(self):
        env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='8',OMP_NUM_THREADS='8',MKL_NUM_THREADS='8',NUMEXPR_NUM_THREADS='8',NUMBA_CACHE_DIR='/tmp/lans-v6-thread-test-cache')
        code="""import sys,os,json
sys.path.insert(0,'tools/controller_review')
import laptop_full_controller
from threadpoolctl import threadpool_info
assert all(os.environ[k]=='1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'))
pools=threadpool_info()
assert pools and all(p['num_threads']==1 for p in pools),pools
print(json.dumps([{'api':p['internal_api'],'threads':p['num_threads']} for p in pools]))
"""
        result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=env,text=True,capture_output=True,check=True)
        self.assertTrue(json.loads(result.stdout.strip().splitlines()[-1]))
    def test_existing_boot_already_limits_blas(self):
        # Distinguish explicit import-order hardening from an actual speed fix:
        # the earlier common boot already set the three BLAS/OpenMP limits.
        env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='8',OMP_NUM_THREADS='8',MKL_NUM_THREADS='8')
        code="""import sys,os,json
sys.path.insert(0,'tools/reviewer_followup')
import boot
import numpy
from threadpoolctl import threadpool_info
assert all(p['num_threads']==1 for p in threadpool_info())
print('existing boot already enforces one BLAS thread')
"""
        subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=env,text=True,capture_output=True,check=True)

if __name__=='__main__':unittest.main()
