from integrations.unified_lans.physics import Route,Config
from .aligned import Controller


def test_uninformative_observations_do_not_repeatedly_blend_feedback_toward_nominal():
    c=Controller(Route('straight'),cfg=Config(horizon=2.),penalty=16.,adaptive=True,mpc=False,feedback_weight=.5)
    c.stiffness_estimate=1.2;c.feedback_stiffness=1.2
    c.update_model();assert c.feedback_stiffness==1.1
    for _ in range(10):c.update_model();assert c.feedback_stiffness==1.1
