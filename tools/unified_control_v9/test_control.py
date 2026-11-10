import numpy as np
from integrations.unified_lans.physics import Config,Route,Command,constrain
from tools.unified_control_v4.kernels import rollout
from .control import Controller
from .calibrate import CANDIDATES,factory


def test_strict_quality_guard_rejects_any_eligible_higher_predicted_heading_or_rate():
    c=Controller(Route('straight'),cfg=Config(horizon=2.),penalty=16.,adaptive=False,mpc=False,guard_factor=1.)
    z=np.array([0.,.3,.005,12.,0.,0.]);base=constrain(Command(c.baseline_fn(z,c.route),0.),c.issued,c.cfg)
    for residual in np.linspace(-.08,.08,17):
        first=constrain(Command(c.baseline_fn(z,c.route)+residual,0.),c.issued,c.cfg)
        _,margin=c.cost(z,first,residual,0.,(),2.)
        if margin>=0 and first.steering!=base.steering:
            for stiff in [.7,1.,1.3]:
                args=(0.,.05,2.,stiff,c._gains,c._route,np.empty((0,7)),2.3,.5,.6,.5,.6,1.)
                a=rollout(z,first.steering,0.,*args);b=rollout(z,base.steering,0.,*args)
                assert a[2]<=b[2]+2e-6 and a[3]<=b[3]+1e-5


def test_factory_preserves_pipeline_mode_and_fixed_controller_roles():
    for candidate in CANDIDATES:
        c=factory(candidate,Route('straight'),'following',Config(),0.,role='optimized',mode='deterministic')
        assert c.mode=='deterministic' and not c.adaptive and c.cfg.horizon==2.
        if hasattr(c,'close'):c.close()
