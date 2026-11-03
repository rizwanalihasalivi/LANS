import numpy as np
from tools.unified_control_v4.control import gain_table
from tools.thirty_percent.optimizer import rollout
from tools.thirty_percent.conic import linearize,solve_joint,project_commands


def problem():
    n=16;initial=np.array([0.,.2,.005,10.,0.,0.]);accels=np.zeros(n)
    npcs=np.zeros((n,1,6));npcs[:,:,0]=80.;gains=gain_table(16.,1.);route=np.array([0.,1.,0.,1.])
    args=(initial,accels,npcs,1.,gains,route);values,states,commands,_=rollout(np.zeros(n),*args)
    return dict(initial=initial,accels=accels,npcs=npcs,stiff=1.,gains=gains,route=route,reference=values,
                states=states,commands=commands,trust=.05),args


def test_condensed_geometry_matches_its_nonlinear_linearization_point():
    p,_=problem();d=linearize(p['initial'],p['states'],p['commands'],p['accels'],p['stiff'],p['gains'],p['route'],p['reference'],p['trust'])
    error=d['error_free']+d['error_matrix']@p['commands']
    np.testing.assert_allclose(error,p['states'][:,1],rtol=0,atol=1e-9)


def test_joint_conic_proposal_has_explicit_actuator_limits_and_projects_legally():
    p,args=problem();commands,info=solve_joint([p],False)
    assert info['status']=='Solved'
    assert np.max(abs(commands))<=.5+1e-8
    assert np.max(abs(np.diff(np.r_[0.,commands[0]])))<=.03+1e-8
    actions=project_commands(commands[0],p['initial'],p['accels'],p['stiff'],p['gains'],p['route'])
    assert np.max(abs(actions))<=1.
    values,_,steers,_=rollout(actions,*args)
    assert np.max(abs(np.diff(np.r_[0.,steers])))<=.03+1e-12
    assert values[0]<p['reference'][0]
