import math
import numpy as np
import pytest
from integrations.unified_lans.physics import clip_scalar,constrain,Command,Config


def test_scalar_constraints_preserve_frozen_array_commands_including_boundaries():
    rng=np.random.default_rng(111104);cfg=Config()
    for i in range(1000):
        u,a,p=rng.uniform(-.8,.8),rng.uniform(-8,4),rng.uniform(-.5,.5);interval=(None,.001,.05)[i%3]
        dt=cfg.dt if interval is None else interval;step=cfg.steering_rate*dt
        reference=Command(float(np.clip(np.clip(u,p-step,p+step),-.5,.5)),float(np.clip(a,-6.,2.5)))
        assert constrain(Command(u,a),Command(p,0.),cfg,interval)==reference
    for lo,hi in ((-1.,1.),(2.,1.)):
        for value in (-math.inf,lo,-0.,0.,hi,math.inf):assert clip_scalar(value,lo,hi)==np.clip(value,lo,hi)


def test_scalar_optimization_never_turns_nonfinite_commands_into_finite_commands():
    assert math.isnan(clip_scalar(math.nan,-1.,1.))
    assert math.isnan(constrain(Command(0.,0.),Command(math.nan,0.),Config()).steering)
    for value in (math.inf,-math.inf,math.nan):
        with pytest.raises(ValueError):constrain(Command(value,0.),Command(),Config())
