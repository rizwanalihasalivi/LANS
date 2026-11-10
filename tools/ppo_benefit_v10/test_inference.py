import json,time
import numpy as np
import pytest
from .core import Env,CONTRACT
from .train import initialize
from .inference import AsyncPolicy,load_policy
from integrations.unified_lans.inference import sha


def bundle(folder):
    folder.mkdir();env=Env()
    try:model,_,_=initialize(42,env);model.save(folder/'policy.zip')
    finally:env.close()
    (folder/'manifest.json').write_text(json.dumps(dict(contract=CONTRACT,policy_sha256=sha(folder/'policy.zip'))))
    return model


def test_actual_worker_preserves_request_identity_and_matches_local_policy(tmp_path):
    folder=tmp_path/'bundle';model=bundle(folder);obs=np.linspace(-1,1,30,dtype=np.float32)
    value,_=model.predict(obs,deterministic=True)
    with AsyncPolicy(folder) as worker:
        assert worker.submit(obs,.1,.15)
        assert not worker.submit(obs,.15,.15)
        deadline=time.monotonic()+10;reply=None
        while reply is None and time.monotonic()<deadline:
            reply=worker.poll()
            if reply is None:time.sleep(.005)
        assert reply is not None and not worker.failed
        assert reply.sequence==1 and reply.observed_s==.1 and reply.submitted_s==.15
        assert reply.residual==pytest.approx(float(value[0])*.08)
        assert reply.wall_observed<=time.monotonic()


def test_contract_hash_and_feature_validation(tmp_path):
    folder=tmp_path/'bundle';bundle(folder)
    record=json.loads((folder/'manifest.json').read_text());record['contract']='old17'
    (folder/'manifest.json').write_text(json.dumps(record))
    with pytest.raises(ValueError,match='contract'):load_policy(folder)
    record['contract']=CONTRACT;record['policy_sha256']='0'*64
    (folder/'manifest.json').write_text(json.dumps(record))
    with pytest.raises(ValueError,match='hash'):load_policy(folder)
