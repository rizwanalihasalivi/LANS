import numpy as np
from integrations.unified_lans.physics import Config,Command,constrain,Route
from integrations.unified_lans.traffic import Packet
from tools.unified_campaign.study import Clock
from tools.unified_control_v4.control import ScheduledLQR
from tools.unified_control_v7.campaign import make_controller


def test_instrumentation_keyword_factory_preserves_zero_residual_lqr_and_shared_config():
    state=np.array([0.,.2,.005,12.,0.,0.]);route=Route('straight')
    for factor in [None,1.10]:
        c=make_controller(route,cfg=Config(),clock=Clock(),mode='lqr',penalty=16.,
            adaptive=False,mpc=False,selection=dict(horizon=2.,factor=factor))
        c.inbox.ingest(Packet('ego',0,0.,tuple(state)),0.)
        result=c.decide(0.);expected=constrain(Command(ScheduledLQR(16.)(state,route),0.),Command(),Config())
        assert c.cfg.horizon==2. and result['source']=='lqr'
        assert abs(result['issued_steering']-expected.steering)<1e-12
        assert result['issued_accel']==expected.accel
