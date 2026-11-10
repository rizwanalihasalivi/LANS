"""Statistical and safety checks independent of controller implementation."""
import pytest
from .campaign import assess,MODES,ACTOR_MODES,SEEDS,cases


def records():
    rows=[]
    for i in range(2):
        for mode in MODES:
            for seed in SEEDS if mode in ACTOR_MODES else [0]:
                rows.append(dict(case=dict(id=i,scenario='following',speed=8.+8*i,cluster_network='nominal'),
                    mode=mode,actor=seed,rmse_m=.6 if mode=='hybrid' else 1.,heading_rms=.01,
                    rate_rms=.02,progress_m=60.,failed=False))
    return rows


def test_known_paired_gain_and_confidence_includes_strong_old_references():
    result=assess(records())
    for name in ('lqr','legacy_optimized','legacy_adaptive','frozen_hybrid'):
        assert result['comparisons'][name]['gain_percent']==pytest.approx(40.)
        assert result['comparisons'][name]['ci95_percent']==pytest.approx([40.,40.])
    assert result['original_gate_passed'] and result['ci_lower_30_all_references']


def test_one_actor_failure_disqualifies_even_with_good_means():
    rows=records();next(r for r in rows if r['mode']=='hybrid' and r['actor']==43)['failed']=True
    result=assess(rows)
    assert not result['original_gate_passed'] and not result['requested_30_all_references']
    assert 'actor_43_failure' in result['reasons']


def test_incomplete_comparison_rejected_and_case_namespaces_disjoint():
    with pytest.raises(AssertionError):assess(records()[:-1])
    development=cases('development');final=cases('final')
    assert len(development)==32 and len(final)==64
    assert not {c['network_seed'] for c in development}&{c['network_seed'] for c in final}
