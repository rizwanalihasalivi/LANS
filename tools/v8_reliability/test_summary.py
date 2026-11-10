"""Publication gates use traffic clusters and every-case progress, not tick counts."""
import copy
import pytest
from .summarize import assess,SEEDS,ACTOR_MODES


def records():
    rows=[]
    for i in range(4):
        case=dict(id=i,scenario='following' if i<2 else 'curved',speed=8. if i%2==0 else 16.,cluster_network='nominal')
        for mode in ('lqr','fixed','deterministic','optimized','adaptive','hybrid','v8_common','v8_original','v8_adaptive','cbf'):
            for actor in SEEDS if mode in ACTOR_MODES else (0,):
                rows.append(dict(case=case,mode=mode,actor=actor,rmse_m=.9 if mode=='hybrid' else 1.,heading_rms=1.,rate_rms=1.,progress_m=100.,failed=False,collisions=0,recourse_ticks=0,uncertified_recourse_ticks=0))
    return rows


def test_actor_and_tick_replicates_are_not_extra_bootstrap_clusters():
    report=assess(records())
    assert report['original_gate_passed']
    assert report['comparisons']['lqr']['clusters']==4
    assert report['comparisons']['lqr']['gain_percent']==pytest.approx(10.)
    assert report['comparisons']['lqr']['ci95_percent']==pytest.approx([10.,10.])


def test_a_single_bad_case_progress_is_not_hidden_by_mean_progress():
    rows=records();bad=next(r for r in rows if r['mode']=='hybrid' and r['actor']==42)
    bad['progress_m']=98.
    report=assess(rows)
    assert not report['original_gate_passed'] and 'actor_42_progress' in report['reasons']


def test_quality_is_checked_per_actor():
    rows=records()
    for r in rows:
        if r['mode']=='hybrid' and r['actor']==42:r['heading_rms']=1.11
    report=assess(rows)
    assert 'actor_42_heading_rms' in report['reasons']
