import numpy as np
from tools.unified_control_v4.control import gain_table
from tools.unified_control_v4.kernels import rollout
from tools.unified_control_v5.control import project
from tools.unified_control_v6.control import refine as original
from tools.unified_control_v6.fast_control import refine,evaluate


def test_fused_kernel_matches_separate_projection_and_scoring_for_varied_states():
    rng=np.random.default_rng(31042111)
    for i in range(96):
        n=20 if i%2 else 40;stiff=float(rng.choice([.8,1.,1.2]));gains=gain_table(16.,stiff)
        route=np.array([i%3,1 if i%2 else -1,11.,1.2],float)
        state=np.array([rng.uniform(0,50),rng.uniform(-.4,.4),rng.uniform(-.03,.03),rng.uniform(5,16),rng.uniform(-.1,.1),rng.uniform(-.02,.02)])
        plan=rng.uniform(-.08,.08,n);warm=rng.uniform(-.08,.08,n);accel=float(rng.uniform(-6,2.5));previous=float(rng.uniform(-.1,.1))
        npcs=np.array([[60.,0.,0.,8.,0.,0.,.1]]) if i%3 else np.empty((0,7))
        projected=project(state,plan,accel,previous,.05,stiff,gains,route,.5,.6,.08,stiff)
        fused,cost,margin=evaluate(state,plan,accel,previous,.05,stiff,gains,route,npcs,2.3,.5,.6,.5,.6,.08,stiff)
        np.testing.assert_array_equal(projected,fused)
        score=rollout(state,projected[0],accel,previous,.05,n*.05,stiff,gains,route,npcs,2.3,.5,.6,.5,.6,stiff,projected)
        np.testing.assert_allclose([cost,margin],score[:2],rtol=0,atol=1e-12)
        args=(state,plan,warm,accel,previous,.05,n*.05,stiff,gains,route,npcs,2.3,.5,.6,.5,.6,.08,stiff)
        np.testing.assert_array_equal(original(*args),refine(*args))
