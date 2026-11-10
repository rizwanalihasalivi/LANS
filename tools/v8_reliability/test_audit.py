"""The independent auditor rejects plausible command/source/metadata corruption."""
import copy,json,math
import pytest
from .verify import episode,sha


def fixture(tmp_path):
    c=dict(id=0,scenario='following',phase=0.,mirror=1,amplitude=1.,speed=8.,stiffness=1.,lateral=0.,heading=0.,delay=0.,network='nominal',network_seed=7)
    rows=[]
    for i in range(120):
        x=(i+1)*.4;nx=32+(i+1)*.2
        rows.append(dict(tick=i,time_s=i*.05,state_before=[i*.4,0.,0.,8.,0.,0.],state_after=[x,0.,0.,8.,0.,0.],
            issued_steering=0.,issued_accel=0.,applied_steering=0.,applied_accel=0.,source='lqr',ego_backup=False,
            ego_age=0.,traffic_age=0.,missing=[],error=0.,heading_error=0.,
            npc_truth={'lead':[nx,0.,0.,4.,0.,0.]},true_clearance=nx-x-4.6,collision=False))
    s=dict(case=c,mode='lqr',actor=0,stage='test',ticks=120,rmse_m=0.,heading_rms=0.,rate_rms=0.,progress_m=48.,
        min_clearance=rows[-1]['true_clearance'],collisions=0,failed=False,ppo_ticks=0,recourse_ticks=0,uncertified_recourse_ticks=0,plan_sha256='frozen')
    return c,rows,s


def save(root,rows,s):
    raw=root/'ticks.jsonl';raw.write_text(''.join(json.dumps(r)+'\n' for r in rows));s=dict(s,raw_sha256=sha(raw))
    (root/'summary.json').write_text(json.dumps(s))


@pytest.mark.parametrize('corruption',['none','fifo','source_age','metadata'])
def test_independent_raw_audit(tmp_path,corruption):
    c,rows,s=fixture(tmp_path)
    if corruption=='fifo':rows[4]['applied_steering']=.001
    if corruption=='source_age':rows[4]['traffic_age']=.05
    if corruption=='metadata':s['case']=dict(c,id=4)
    save(tmp_path,rows,s);job=(tmp_path,c,'lqr',0,'test','frozen')
    if corruption=='none':assert episode(job)['passed']
    else:
        with pytest.raises(AssertionError):episode(job)
