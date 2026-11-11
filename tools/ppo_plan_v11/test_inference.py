import json,time
import numpy as np
import pytest
from stable_baselines3 import PPO
from integrations.unified_lans.inference import sha
from tools.unified_control_v4.calibrate import cases
from tools.unified_control_v9.learning import setup as build_pipeline
from tools.ppo_benefit_v10.core import PARAMS
from .control import PlanProposal
from .learning import Env,CONTRACT
from .inference import InferenceOwner,AsyncPlan,load_policy


def test_worker_matches_local_eight_knot_output_and_preserves_times(tmp_path):
    env=Env();model=PPO('MlpPolicy',env,n_steps=8,batch_size=4,seed=42,device='cpu')
    model.save(tmp_path/'policy.zip');(tmp_path/'manifest.json').write_text(json.dumps(dict(contract=CONTRACT,policy_sha256=sha(tmp_path/'policy.zip'))))
    query=np.linspace(-1,1,40,dtype=np.float32);expected,_=model.predict(query,deterministic=True)
    with AsyncPlan(tmp_path) as worker:
        assert worker.submit(query,.1,.15) and not worker.submit(query,.1,.15)
        deadline=time.monotonic()+10;reply=None
        while reply is None and time.monotonic()<deadline:
            reply=worker.poll()
            if reply is None:time.sleep(.005)
        assert reply is not None and not worker.failed and reply.observed_s==.1 and reply.submitted_s==.15
        assert isinstance(reply.knots,tuple);np.testing.assert_allclose(reply.knots,expected,rtol=0,atol=1e-7)
    env.close()
    record=json.loads((tmp_path/'manifest.json').read_text());record['contract']='old-scalar'
    (tmp_path/'manifest.json').write_text(json.dumps(record))
    with pytest.raises(ValueError,match='contract'):load_policy(tmp_path)


def test_owner_defensively_copies_mutable_payload():
    c,clock,*_=build_pipeline(cases()[0],'deterministic',InferenceOwner,PARAMS,grid=True)
    values=[0.]*8;p=PlanProposal(1,0.,0.,0.,values)
    assert c.accept_plan(p,0.);values[0]=100.
    assert c.plan_proposal.knots==(0.,)*8 and isinstance(c.plan_proposal.knots,tuple)
