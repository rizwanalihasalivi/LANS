from tools.unified_control_v6.analyze import contrasts


def test_exact_test_uses_fixture_clusters_instead_of_correlated_profile_rows():
    rows=[]
    for fixture in range(16):
        for profile in range(4):
            for variant,failed in [('full',False),('ablated',True)]:
                rows.append(dict(case=dict(id=fixture*4+profile,fixture_id=fixture),
                    variant=variant,failed=failed,rmse_m=.1 if variant=='full' else .2))
    result=contrasts(rows)[0]
    assert result['fixtures']==16 and result['non_tied_fixtures']==16
    assert abs(result['failure_exact_sign_p']-2/2**16)<1e-14
    assert result['failure_increase_percentage_points']==100.
    assert result['failure_increase_ci95_pp']==[100.,100.]


def test_equal_outcomes_are_not_reported_as_equivalence_or_significance():
    rows=[]
    for i in range(16):
        for variant in ['full','a','b','c','d','e']:
            rows.append(dict(case=dict(id=i,fixture_id=i),variant=variant,failed=False,rmse_m=.1))
    result=contrasts(rows)
    assert len(result)==5
    assert all(r['failure_holm_p']==1. and r['non_tied_fixtures']==0 for r in result)
