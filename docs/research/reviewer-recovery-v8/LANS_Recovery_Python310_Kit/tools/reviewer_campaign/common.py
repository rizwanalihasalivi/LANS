"""Imports for an isolated reviewer-response campaign; legacy sources stay frozen."""
from pathlib import Path
import os
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RESEARCH = ROOT / 'integrations/webots/research'
for name in ('revision9', 'revision8', 'revision7', 'revision5', 'revision4', 'revision2'):
    sys.path.append(str(RESEARCH / name))
sys.path.append(str(RESEARCH))
sys.path.append(str(ROOT / 'tools/controller_review'))
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
os.environ.setdefault('MPLCONFIGDIR', '/tmp/lans-campaign-mpl')
os.environ.setdefault('NUMBA_CACHE_DIR', '/tmp/lans-campaign-numba')
# TensorBoard explicitly supports a no-TensorFlow mode. This CPU Torch campaign
# does not use TensorFlow; avoid its unrelated multi-minute startup/import cost.
sys.modules.setdefault('tensorboard.compat.notf', types.ModuleType('tensorboard.compat.notf'))
