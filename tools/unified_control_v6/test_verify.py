import json,math
import numpy as np
import pytest
from integrations.unified_lans.physics import Config,Command,Route,advance
from integrations.unified_lans.simulation import truth_metrics
from integrations.unified_lans.inference import sha
from integrations.unified_lans.run import clean
from tools.unified_control_v6.verify import check_record


def fixture(tmp_path):
    case=dict(id=0,scenario='following',mirror=1,phase=0.,amplitude=1.,delay=0.,stiffness=1.)
    state=np.array([0.,.1,0.,12.,0.,0.]);other=np.array([50.,0.,0.,8.,0.,0.]);rows=[]
    for i in range(3):
        before=state.copy();state=advance(state,Command(),.05);other[0]+=8*.05
        rows.append(dict(tick=i,time_s=i*.05,state_before=before.tolist(),state_after=state.tolist(),
            npc_truth_after={'lead':other.tolist()},**truth_metrics(state,{'lead':other},Route('straight'),Config()),
            issued_steering=0.,issued_accel=0.,applied_steering=0.,applied_accel=0.,
            source='lqr',ego_backup=False,steering_rate=0.))
    raw=tmp_path/'raw.jsonl';raw.write_text(''.join(json.dumps(clean(r))+'\n' for r in rows))
    record=dict(case=case,ticks=3,expected_ticks=3,raw_sha256=sha(raw),failed=False,
        rmse_m=math.sqrt(sum(r['error']**2 for r in rows)/3),heading_rms=0.,rate_rms=0.,
        progress_m=float(state[0]),min_clearance=min(r['true_clearance'] for r in rows),collisions=0)
    return record,rows,raw


@pytest.mark.parametrize('corruption',['summary_rmse','clearance_truth','physical_fifo'])
def test_verifier_rejects_tampering_even_when_attacker_refreshes_raw_hash(tmp_path,corruption):
    record,rows,raw=fixture(tmp_path);assert check_record(record,raw)==3
    if corruption=='summary_rmse':record['rmse_m']+=.01
    elif corruption=='clearance_truth':rows[1]['true_clearance']+=.1
    else:rows[1]['applied_steering']=.02
    raw.write_text(''.join(json.dumps(clean(r))+'\n' for r in rows));record['raw_sha256']=sha(raw)
    with pytest.raises(AssertionError):check_record(record,raw)
