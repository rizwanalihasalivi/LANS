"""Compile the emergency kernel in a package-qualified isolated runtime cache.

Startup only. This synthetic rollout never issues a measured command, changes
a policy or enters scientific scores. Reuses the exact production signature.
"""
import json,time
import numpy as np
from tools.unified_control_v4.control import gain_table
from .recovery import margins


def main():
    started=time.perf_counter()
    scores=margins(np.array([0.,.3,0.,12.,0.,0.]),-6.,0.,0.,np.array([0.,0.]),np.empty((0,3)),0.,
        1.,gain_table(16.,1.),np.array([0.,1.,0.,1.]),1.,np.array([[30.,-20.,np.pi/2,8.,0.,0.,0.]]),
        .05,12.,.5,.6,2.3,.5,.6)
    print(json.dumps(dict(startup_s=time.perf_counter()-started,compiled_module=margins.py_func.__module__,
        scored_ticks=0,synthetic_startup_only=True,finite_result=bool(np.isfinite(scores).all()))),flush=True)


if __name__=='__main__':main()
