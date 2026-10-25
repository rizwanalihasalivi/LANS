"""Read-only root/controller audit. Writes only audit JSON beside this script."""
import ast,csv,importlib,json,math,sys,subprocess
from pathlib import Path
from collections import defaultdict
ROOT=Path('/workspace/LANS');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT))
import numpy as np
import torch
torch.set_num_threads(1)
from controllers.policy_bundle import PolicyBundle
from controllers.lans_controller import LANSController
from envs.path_tracking_env import PathTrackingEnv
from tools.controller_review.compare import run
result={}
for module in ('envs.bicycle_env','envs.lqr_env'):
    try: importlib.import_module(module);result[module]='import ok'
    except Exception as exc: result[module]=f'{type(exc).__name__}: {exc}'
try:json.loads((ROOT/'jitter_test_results.json').read_text());result['jitter_json']='valid'
except Exception as exc:result['jitter_json']=str(exc)
result['missing_claim_inputs']={str(p):p.exists() for p in [ROOT/'results/optimized/victory_config.json',ROOT/'lqr_run_results.npz']}
artifact=ROOT/'integrations/webots/results/controller-remediation'
bundle=PolicyBundle(artifact/'root-smoke')
result['model']={'steps':bundle.model.num_timesteps,'seed':bundle.model.seed,'obs_rms_count':bundle.normalizer.obs_rms.count,'normalizer_frozen':not bundle.normalizer.training}
episodes=list(csv.DictReader((artifact/'root-comparison/episodes.csv').open()))
traces=list(csv.DictReader((artifact/'root-comparison/traces.csv').open()))
group=defaultdict(list)
for row in traces:group[tuple(row[k] for k in ('method','seed','speed','delay_ms'))].append(row)
diffs=[];kinematic=[]
for row in episodes:
    rows=group[tuple(row[k] for k in ('method','seed','speed','delay_ms'))]
    rmse=math.sqrt((sum(float(r['error'])**2 for r in rows)+(1000-len(rows))*6.25)/1000)
    diffs.append(abs(rmse-float(row['penalized_rmse'])))
    kinematic.extend(abs(float(r['error'])-(float(r['y_phys'])-float(r['y_ref']))) for r in rows)
result['stored_root']={'episodes':len(episodes),'trace_rows':len(traces),'survived':sum(r['survived']=='True' for r in episodes),'max_recomputed_rmse_diff':max(diffs),'max_geometry_identity_diff':max(kinematic)}
result['fresh_runs']=[]
for method,delay in [('lqr',0),('residual',0),('residual',2),('residual',10)]:
    row,_=run(method,101,25,delay,bundle if method=='residual' else None)
    original=next(r for r in episodes if (r['method'],r['seed'],r['speed'],r['delay_ms'])==(method,'101','25',str(delay*10)))
    row['stored_difference']=row['penalized_rmse']-float(original['penalized_rmse'])
    result['fresh_runs'].append(row)
env=PathTrackingEnv('eval',25);obs,_=env.reset(seed=1,options={'lateral_error':.15,'heading_error':.01})
c=LANSController(25,policy_bundle=artifact/'root-smoke');observation_diff=[];command_diff=[]
for i in range(1000):
    x,y,psi,vy,r=env.physical
    command,info=c.step(y,env._get_reference_y(x),psi,env._get_reference_heading(x),vy,r,env.curvature(),preview_y=[env._get_reference_y(x+j*env.vx*env.dt) for j in range(1,5)])
    expected,_=bundle.predict(obs)
    u=float(np.clip(env.lqr_control(env.state,env.curvature())+.08*float(expected.item()),-.5,.5))
    observation_diff.append(float(np.max(np.abs(info['observation']-obs))));command_diff.append(abs(u-command))
    obs,_,done,trunc,_=env.step([command])
    if done or trunc:break
result['deployment_parity']={'steps':len(observation_diff),'max_obs_diff':max(observation_diff),'max_command_diff':max(command_diff)}
# Parse definitions without triggering import-time simulations/plots.
module=ast.parse((ROOT/'visualize_results.py').read_text())
defs=ast.Module(body=[n for n in module.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))],type_ignores=[])
from scenarios.double_lane_change import double_lane_change
namespace={'VX':25,'double_lane_change':double_lane_change}
exec(compile(defs,'visualize_results.py','exec'),namespace)
try:namespace['generate_reference_path'](np.array([0.,1.]));result['visualizer_reference']='ok'
except Exception as exc:result['visualizer_reference']=f'{type(exc).__name__}: {exc}'
tests=subprocess.run([sys.executable,'-B',str(ROOT/'tests/test_controller_remediation.py'),'-v'],cwd=ROOT,text=True,capture_output=True)
result['existing_contract_tests']={'returncode':tests.returncode,'stdout':tests.stdout,'stderr':tests.stderr}
(OUT/'diagnostics.json').write_text(json.dumps(result,indent=2,default=float)+'\n')
print(json.dumps(result,indent=2,default=float))
