import json
import numpy as np
import pytest
from tools.unified_control_v4.control import gain_table
from tools.thirty_percent.run import save_trace
from tools.thirty_percent.verify import check_trace
from tools.thirty_percent.run_conic import score


def test_joint_quality_is_mean_episode_rms_not_pooled_energy_or_per_cell_limit():
    references=[np.array([1.,1.,1.,10.,1.,1.]) for _ in range(2)]
    values=[np.array([1.,4.,4.,10.,1.,1.]),np.array([1.,.01,.01,10.,1.,1.])]
    result=score(values,references,True)
    assert result['feasible'] and abs(result['heading_mean_ratio']-1.05)<1e-12
    assert result['per_case'][0]['heading_ratio']>1.10


def test_independent_authority_check_rejects_an_invented_baseline_label(tmp_path):
    initial=np.array([0.,.2,0.,10.,0.,0.]);accels=np.zeros(8);npcs=np.zeros((8,1,6));npcs[:,:,0]=80.
    args=(initial,accels,npcs,1.,gain_table(16.,1.),np.array([0.,1.,0.,1.]))
    record=dict(case=dict(scenario='following',mirror=1,phase=0.,amplitude=1.,stiffness=1.))
    path=tmp_path/'raw.jsonl';actions=np.zeros(8);rows,_=save_trace(path,actions,args,record)
    check_trace(record,args,path,actions)
    rows[1]['baseline_steering']+=.02
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    with pytest.raises(AssertionError):check_trace(record,args,path,actions)
